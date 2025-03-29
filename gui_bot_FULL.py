import tkinter as tk
from tkinter import ttk
from bot_logic_FULL import analyze_all, plot_ai_decision_graph, calculate_confidence_score, check_price_trigger, save_pending_trade, classify_confidence
from portfolio_FULL import get_portfolio
from news_sentiment import get_overall_sentiment
from logger_FULL import log_trade
from scale_in_tracker import (
    record_trade_step, get_position_state, reset_position,
    record_last_sell_time, can_enter_new_buy, update_trigger_price
)
import trader
from trader import execute_trade
import pandas as pd
import glob
import json
import os
import plot_trades
from decision_model import predict_meta_decision
import scheduler
from meta_decision import make_final_decision
from decision_model import update_meta_training_data as log_meta_training_data


last_decision_info = {}


# ----- Globális állapot -----
auto_running = False
after_id = None
if trader.LIVE_TRADING == False:  # Állítsd True-ra éles kereskedéshez!
    pass


# --- GUI inicializálás ---
root = tk.Tk()
root.title("AI CryptoBot GUI")

# 🔁 Automatikus napi modell újratanítás elindítása
scheduler.start_daily_retraining()

# --- Tkinter változók ---
pair_var = tk.StringVar(value="SOLEUR")
amount_var = tk.StringVar(value="5")
interval_var = tk.StringVar(value="15")
timestamp_full_var = tk.StringVar()


price_var = tk.StringVar()
rsi_var = tk.StringVar()
ai_var = tk.StringVar()
rsi_signal_var = tk.StringVar()
sentiment_var = tk.StringVar()
pending_signal_var = tk.StringVar()
portfolio_var = tk.StringVar()
final_decision_var = tk.StringVar()
scalein_var = tk.StringVar()
sell_waiting_var = tk.StringVar()
last_trade_var = tk.StringVar()
live_trading_var = tk.BooleanVar(value=trader.load_live_trading_setting())
confidence_text_var = tk.StringVar()



# --- Utolsó élő kereskedés betöltése ---
def load_last_live_trade():
    if os.path.exists("last_live_trade.json"):
        try:
            with open("last_live_trade.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                time = data.get("time", "—")
                pair = data.get("pair", "")
                action = data.get("action", "")
                amount = data.get("amount", "")
                return f"{time} – {pair} {action} {amount} EUR"
        except Exception as e:
            return f"Hiba betöltéskor: {e}"
    return "—"

# --- Döntéshozó függvény ---
def update_data():
    global after_id

    decision = "NINCS DÖNTÉS"

    pair = pair_var.get()
    amount = float(amount_var.get())
    interval = int(interval_var.get())

    print("⏱️ Automatikus frissítés elindult.")
    print("▶️ Pár:", pair)

    # Élő figyelmeztetés
    if live_trading_var.get():
        live_warning_var.set("⚠️ FIGYELEM: ÉLŐ KERESKEDÉS ENGEDÉLYEZVE!")
    else:
        live_warning_var.set("")

    # Elemzés
    result = analyze_all(pair)
    sentiment = get_overall_sentiment()
    portfolio = get_portfolio()

    rsi_signal = result['rsi_signal']
    ai_prediction = result['ai_prediction']
    price = result['price']

    meta_pred = predict_meta_decision(result['rsi_signal'], result['ai_prediction'], sentiment)

    # GUI frissítés
    price_var.set(f"{price:.2f} EUR")
    rsi_var.set(f"{result['rsi']:.2f}")
    ai_var.set("⬆️" if ai_prediction == 1 else "⬇️")
    rsi_signal_var.set(rsi_signal)
    sentiment_var.set(sentiment)
    portfolio_var.set(", ".join(f"{k}: {v}" for k, v in portfolio.items() if float(v) > 0))
    last_trade_var.set(load_last_live_trade())

    # Confidence kiszámítása
    confidence = calculate_confidence_score(rsi_signal, ai_prediction, sentiment)
    confidence_level = classify_confidence(confidence)
    confidence_text_var.set(f"Bizalom: {confidence_level} ({round(confidence*100)}%)")

    # Trigger ellenőrzés
    trigger_ok = check_price_trigger("BUY", price, result.get('df', pd.DataFrame())) or \
                 check_price_trigger("SELL", price, result.get('df', pd.DataFrame()))

    # Meta modell predikció vagy fallback döntés
    meta_pred = predict_meta_decision(rsi_signal, ai_prediction, sentiment)
    if meta_pred is None:
        signal_type = make_final_decision(rsi_signal, ai_prediction, sentiment, confidence, trigger_ok)
    else:
        signal_type = "BUY" if meta_pred == 1 and trigger_ok else None

    # Függő jelzés kezelése
    if signal_type and not check_price_trigger(signal_type, price, result.get('df', pd.DataFrame())):
        pending_signal_var.set(f"{signal_type} – Trigger figyelés aktív")
        save_pending_trade(pair, signal_type, confidence, price)
        decision = "⏳ Függőben"
    else:
        pending_signal_var.set("—")

    # --- ELADÁS ---
    if signal_type == "SELL" and float(portfolio.get(pair[:3], 0)) > 0:
        reset_position(pair)
        record_last_sell_time(pair)
        decision = "ELADÁS"
        log_trade(pair, "SELL", result, sentiment, amount)
        if trader.LIVE_TRADING:
            execute_trade("sell", pair, amount)
        log_meta_training_data(pair, rsi_signal, ai_prediction, sentiment, "SELL")

    # --- VÉTEL (scale-in) ---
    if signal_type == "BUY" and float(portfolio.get('ZEUR', 0)) >= amount * 0.25:
        from datetime import datetime
        if can_enter_new_buy(pair, datetime.now()):
            steps_done = get_position_state(pair)["steps"]
            if steps_done < 4:
                if confidence_level == "nagyon erős":
                    step_fraction = 0.5
                elif confidence_level == "erős":
                    step_fraction = 0.35
                elif confidence_level == "közepes":
                    step_fraction = 0.25
                elif confidence_level == "gyenge":
                    step_fraction = 0.15
                else:
                    step_fraction = 0.1

                buy_amount = round(amount * step_fraction, 2)
                step = record_trade_step(pair, amount)
                decision = f"VÉTEL ({confidence_level}, lépés {step}/4)"

                log_trade(pair, "BUY", result, sentiment, buy_amount)
                if trader.LIVE_TRADING:
                    execute_trade("buy", pair, buy_amount)
                log_meta_training_data(pair, rsi_signal, ai_prediction, sentiment, "BUY")
            else:
                decision = "MÁR TELJES POZÍCIÓ"
        else:
            decision = "⏸️ Eladás után várakozás – új vételi jelzésre várunk"

    final_decision_var.set(decision)
    if trader.LIVE_TRADING and ("VÉTEL" in decision or "ELADÁS" in decision):
        final_decision_var.set(f"{decision} ✅ [ÉLŐ]")

    # Eladás utáni újra belépés info
    from datetime import datetime
    sell_waiting_var.set("Új belépés engedélyezett - ✅" if can_enter_new_buy(pair, datetime.now()) else "Várakozás új vételi jelzésre - ⛔")

    # Időbélyeg frissítés
    timestamp_full_var.set("Frissítve: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Skálázott állapot
    steps = get_position_state(pair)["steps"]
    scalein_var.set(f"{steps}/4 lépés teljesítve")

    # Trigger ár frissítése
    if signal_type == "BUY":
        update_trigger_price(pair, price)

    # Következő automatikus ciklus
    if auto_running:
        after_id = root.after(interval * 60 * 1000, update_data)

    # 🧠 Részletes döntési információ mentése
    global last_decision_info
    last_decision_info = {
        "Pár": pair,
        "Árfolyam": f"{price:.4f} EUR",
        "RSI": f"{result['rsi']:.2f}",
        "RSI jelzés": rsi_signal,
        "AI predikció": "⬆️" if ai_prediction == 1 else "⬇️",
        "Hírhangulat": sentiment,
        "Confidence érték": f"{round(confidence * 100)}%",
        "Confidence szint": confidence_level,
        "Trigger szint elérve": "Igen" if trigger_ok else "Nem",
        "Meta modell döntés": "BUY" if meta_pred == 1 else ("NEM" if meta_pred == 0 else "Nincs modell"),
        "Végső döntés": decision,
        "Eladás utáni belépés engedélyezett": "Igen" if can_enter_new_buy(pair, datetime.now()) else "Nem"
    }

# --- Start/Stop vezérlés ---
def toggle_auto():
    global auto_running, after_id
    auto_running = not auto_running
    if auto_running:
        start_button.config(text="⏹️ Leállítás")
        update_data()
    else:
        if after_id:
            root.after_cancel(after_id)
        start_button.config(text="▶️ Indítás")

# --- Grafikon gombok ---
    # AI döntések + technikai szintek (1 panel)
def plot_ai_graph():
    try:
        df_feat = pd.read_csv("features.csv", parse_dates=["time"], index_col="time")
        trade_files = sorted(glob.glob("trades_*.csv"), reverse=True)
        if trade_files:
            df_trades = pd.read_csv(trade_files[0], parse_dates=["Dátum"])
            df_trades.set_index("Dátum", inplace=True)
            df_combined = df_feat.join(df_trades[["Akció", "Hírhangulat", "AI_predikció"]], how="left")
            df_combined["Akció"] = df_combined["Akció"].fillna("NINCS JELZÉS")
            df_combined["AI_predikció"] = df_combined["AI_predikció"].fillna("⬇️")
            df_combined["Hírhangulat"] = df_combined["Hírhangulat"].fillna("neutral")
            df_combined = df_combined.reset_index().rename(columns={"time": "Dátum"})
        else:
            df_combined = df_feat.reset_index().rename(columns={"time": "Dátum"})
            df_combined["Akció"] = "NINCS JELZÉS"
            df_combined["AI_predikció"] = "⬇️"
            df_combined["Hírhangulat"] = "neutral"
        plot_ai_decision_graph(df_combined)
    except Exception as e:
        print("📉 Hiba az AI döntési grafikon megjelenítésekor:", e)


    # Teljes hárompaneles grafikon
def plot_full_graph():
    try:
        plot_trades.plot_trades()
    except Exception as e:
        print("📉 Hiba a teljes hárompaneles grafikon megjelenítésekor:", e)


def toggle_live_trading():
    trader.save_live_trading_setting(live_trading_var.get())
    # Figyelmeztetés frissítése
    if live_trading_var.get():
        live_warning_var.set("⚠️ FIGYELEM: ÉLŐ KERESKEDÉS ENGEDÉLYEZVE!")
    else:
        live_warning_var.set("")


def show_decision_insight():
    from tkinter import Toplevel, Text, Scrollbar, RIGHT, Y, END

    result = analyze_all(pair_var.get())
    sentiment = get_overall_sentiment()
    confidence = calculate_confidence_score(result['rsi_signal'], result['ai_prediction'], sentiment)
    trigger_price = None

    # META predikció és confidence
    meta_decision = predict_meta_decision(result['rsi_signal'], result['ai_prediction'], sentiment)
    meta_score = round(confidence * 100, 1)

    # Trigger kalkuláció
    df = result.get('df', pd.DataFrame())
    if len(df) >= 2:
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        if result['ai_prediction'] == 1:
            trigger_price = prev_high
        else:
            trigger_price = prev_low

    # Ablak létrehozása
    win = Toplevel(root)
    win.title("📊 Aktuális döntés részletei")
    win.geometry("650x500")

    scrollbar = Scrollbar(win)
    scrollbar.pack(side=RIGHT, fill=Y)

    text = Text(win, wrap="word", yscrollcommand=scrollbar.set)
    text.pack(expand=True, fill="both")
    scrollbar.config(command=text.yview)

    # Megjelenítendő információk
    text.insert(END, f"🟡 Árfolyam: {result['price']:.2f} EUR\n")
    text.insert(END, f"🔁 RSI érték: {result['rsi']:.2f}\n")
    text.insert(END, f"📈 RSI jelzés: {result['rsi_signal']}\n")
    text.insert(END, f"🤖 AI predikció: {'⬆️' if result['ai_prediction'] == 1 else '⬇️'}\n")
    text.insert(END, f"📰 Hírhangulat: {sentiment}\n")
    text.insert(END, f"🔐 Confidence score (META): {meta_score}%\n")
    if trigger_price:
        text.insert(END, f"📍 Trigger szint: {trigger_price:.4f} EUR\n")
    else:
        text.insert(END, f"📍 Trigger szint: nincs adat\n")

    text.insert(END, "\n📌 Technikai mutatók:\n")
    text.insert(END, f"  - EMA20: {result['df']['ema20'].iloc[-1]:.4f}\n")
    text.insert(END, f"  - EMA50: {result['df']['ema50'].iloc[-1]:.4f}\n")
    text.insert(END, f"  - EMA diff: {result['df']['ema_diff'].iloc[-1]:.4f}\n")
    text.insert(END, f"  - Return: {result['df']['return'].iloc[-1]:.4f}\n")
    text.insert(END, f"  - Volatility: {result['df']['volatility'].iloc[-1]:.4f}\n")

    text.insert(END, "\n🧠 META döntés: ")
    if meta_decision == 1:
        text.insert(END, "VÉTEL ✅")
    elif meta_decision == 0:
        text.insert(END, "NINCS VÉTEL 🚫")
    else:
        text.insert(END, "Nincs elérhető META modell")

    text.config(state="disabled")




# --- GUI elrendezés (LabelFrame szekciók) ---
ttk.Label(root, text="⚙️ Beállítások", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
frame_settings = ttk.Frame(root)
frame_settings.pack(fill="x", padx=10)

    # --- Frissítés gomb ---
ttk.Button(frame_settings, text="🔄 Kézi frissítés", command=update_data).grid(row=3, column=0, columnspan=2, pady=10)

ttk.Label(frame_settings, text="Coin pár:").grid(row=0, column=0, sticky="w")
ttk.Combobox(frame_settings, textvariable=pair_var, values=["SOLEUR", "BTCEUR", "ETHEUR", "DOTEUR", "XRPEUR"]).grid(row=0, column=1)

ttk.Label(frame_settings, text="Kereskedési összeg (EUR):").grid(row=1, column=0, sticky="w")
ttk.Entry(frame_settings, textvariable=amount_var).grid(row=1, column=1)

ttk.Label(frame_settings, text="Időzítés (perc):").grid(row=2, column=0, sticky="w")
ttk.Combobox(frame_settings, textvariable=interval_var, values=["5", "10", "15", "30", "60"]).grid(row=2, column=1)

    # Élő kereskedés checkbox
ttk.Checkbutton(
    frame_settings,
    text="Élő kereskedés engedélyezése",
    variable=live_trading_var,
    command=lambda: toggle_live_trading()
).grid(row=0, column=4, columnspan=2, sticky="w")

# --- Technikai szekció ---
frame_tech = ttk.LabelFrame(root, text="📊 Technikai adatok", padding=10)
frame_tech.pack(fill="x", padx=10, pady=5)
frame_tech.columnconfigure(3, weight=1)

ttk.Label(frame_tech, textvariable=confidence_text_var).grid(row=4, column=0, columnspan=2, sticky="w")

for i, (label, var) in enumerate([
    ("Előző óra záróárfolyama", price_var), ("RSI", rsi_var),
    ("AI előrejelzés", ai_var), ("RSI jelzés", rsi_signal_var)
]):
    ttk.Label(frame_tech, text=label + ":").grid(row=i, column=0, sticky="w")
    ttk.Label(frame_tech, textvariable=var).grid(row=i, column=1, sticky="w")

ttk.Label(frame_tech, textvariable=timestamp_full_var, anchor="e").grid(
    row=0, column=0, columnspan=4, sticky="e", padx=(0, 10)
)

# --- Sentiment szekció ---
frame_sentiment = ttk.LabelFrame(root, text="🗞️ Hírek és függő jelek", padding=10)
frame_sentiment.pack(fill="x", padx=10, pady=5)

ttk.Label(frame_sentiment, text="Hírhangulat:").grid(row=0, column=0, sticky="w")
ttk.Label(frame_sentiment, textvariable=sentiment_var).grid(row=0, column=1, sticky="w")
ttk.Label(frame_sentiment, text="📌 Függő jelzés:").grid(row=1, column=0, sticky="w")
ttk.Label(frame_sentiment, textvariable=pending_signal_var).grid(row=1, column=1, sticky="w")

# --- Portfólió szekció ---
frame_portfolio = ttk.LabelFrame(root, text="💼 Portfólió", padding=10)
frame_portfolio.pack(fill="x", padx=10, pady=5)
ttk.Label(frame_portfolio, textvariable=portfolio_var, wraplength=580).pack(anchor="w")

# --- Scale-in szekció ---
frame_scale = ttk.LabelFrame(root, text="📈 Skálázott belépés", padding=10)
frame_scale.pack(fill="x", padx=10, pady=5)
ttk.Label(frame_scale, text="Lépések száma:").grid(row=0, column=0, sticky="w")
ttk.Label(frame_scale, textvariable=scalein_var).grid(row=0, column=1, sticky="w")

# --- Eladás utáni belépési állapot ---
frame_waiting = ttk.LabelFrame(root, text="🔁 Eladás utáni státusz", padding=10)
frame_waiting.pack(fill="x", padx=10, pady=5)
ttk.Label(frame_waiting, textvariable=sell_waiting_var, font=("Arial", 10, "italic")).grid(row=0, column=0, sticky="w")

frame_waiting.columnconfigure(0, weight=1)

    # --- Legutóbbi valós kereskedés ---
ttk.Label(frame_waiting, text="Legutóbbi valós kereskedés:").grid(row=0, column=1, sticky="w")
ttk.Label(frame_waiting, textvariable=last_trade_var, font=("Arial", 10), anchor="e", justify="right").grid(row=0, column=2, sticky="e", padx=(10, 0))


# --- Vezérlés szekció ---
frame_controls = ttk.LabelFrame(root, text="🎮 Vezérlés", padding=10)
frame_controls.pack(fill="x", padx=10, pady=5)

ttk.Label(frame_controls, text="Végső döntés:").grid(row=0, column=0, sticky="w")
ttk.Label(frame_controls, textvariable=final_decision_var, font=("Arial", 10, "bold")).grid(row=0, column=1, sticky="w")

start_button = ttk.Button(frame_controls, text="▶️ Indítás", command=toggle_auto)
start_button.grid(row=2, column=0, pady=5, sticky="w")

ttk.Button(frame_controls, text="📊 AI döntések", command=plot_ai_graph).grid(row=1, column=2, pady=5, sticky="w")
ttk.Button(frame_controls, text="📉 Teljes grafikon", command=plot_full_graph).grid(row=1, column=3, pady=5, sticky="w")
ttk.Button(frame_controls, text="📋 Döntés részletei", command=show_decision_insight).grid(row=1, column=4, columnspan=2, sticky="w", pady=(5, 0))

ttk.Button(frame_controls, text="Kilépés", command=root.destroy).grid(row=2, column=5, pady=5, sticky="w")


live_warning_var = tk.StringVar()

# Élő kereskedés figyelmeztetés label
warning_label = ttk.Label(root, textvariable=live_warning_var, foreground="red", font=("Arial", 10, "bold"))
warning_label.pack(pady=(0, 10))


update_data()

# Automatikus méretezés a tartalomhoz
root.update()
root.minsize(root.winfo_width(), root.winfo_height())

root.mainloop()
