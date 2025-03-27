import tkinter as tk
from tkinter import ttk
from bot_logic_FULL import analyze_all, plot_ai_decision_graph, calculate_confidence_score, check_price_trigger, save_pending_trade
from portfolio_FULL import get_portfolio
from news_sentiment import get_overall_sentiment
from logger_FULL import log_trade
from scale_in_tracker import (
    record_trade_step, get_position_state, reset_position,
    record_last_sell_time, can_enter_new_buy
)
import trader
from trader import execute_trade
import pandas as pd
import glob
import json
import os


# ----- Globális állapot -----
auto_running = False
after_id = None
if trader.LIVE_TRADING == False:  # Állítsd True-ra éles kereskedéshez!
    pass


# --- GUI inicializálás ---
root = tk.Tk()
root.title("AI CryptoBot GUI")
root.geometry("650x700")

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
live_trading_var = tk.BooleanVar(value=trader.LIVE_TRADING)




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
    print("⏱️ Automatikus frissítés elindult.")
    print("▶️ Pár:", pair)

    
    amount = float(amount_var.get())
    interval = int(interval_var.get())

    result = analyze_all(pair)
    print("📦 Eredmény:", result)

    pair = pair_var.get()
    amount = float(amount_var.get())
    interval = int(interval_var.get())

    result = analyze_all(pair)
    sentiment = get_overall_sentiment()
    portfolio = get_portfolio()

    # GUI frissítés
    price_var.set(f"{result['price']:.2f} EUR")
    rsi_var.set(f"{result['rsi']:.2f}")
    ai_var.set("⬆️" if result['ai_prediction'] == 1 else "⬇️")
    rsi_signal_var.set(result['rsi_signal'])
    sentiment_var.set(sentiment)
    portfolio_var.set(", ".join(f"{k}: {v}" for k, v in portfolio.items() if float(v) > 0))

    score = 0
    if result['rsi_signal'] == "BUY":
        score += 0.2
    elif result['rsi_signal'] == "SELL":
        score -= 0.2
    if result['ai_prediction'] == 1:
        score += 0.5
    else:
        score -= 0.5
    if sentiment == "positive":
        score += 0.3
    elif sentiment == "negative":
        score -= 0.3

    # --- Confidence kiszámítása ---
    confidence = calculate_confidence_score(result['rsi_signal'], result['ai_prediction'], sentiment)

    # --- Függő jelzés kezelése ---
    price = result['price']
    signal_type = "BUY" if score >= 0.5 and float(portfolio.get('ZEUR', 0)) >= amount else (
                  "SELL" if score <= -0.5 and float(portfolio.get(pair[:3], 0)) > 0 else None)

    if signal_type and not check_price_trigger(signal_type, price, result.get('df', pd.DataFrame())):
        pending_signal_var.set(f"{signal_type} – Trigger figyelés aktív")
        save_pending_trade(pair, signal_type, confidence, price)
        decision = "⏳ Függőben"
    else:
        pending_signal_var.set("—")
        
        # Legutóbbi élő kereskedés betöltése
    last_trade_var.set(load_last_live_trade())


# --- Eladási logika ---
    if score <= -0.5 and float(portfolio.get(pair[:3], 0)) > 0:
        reset_position(pair)
        record_last_sell_time(pair)  # új: eladás időpont mentése
        decision = "ELADÁS"
        log_trade(pair, "SELL", result, sentiment, amount)
        if trader.LIVE_TRADING:
            execute_trade("sell", pair, amount)
            print("💰 Valós ELADÁS végrehajtva.")


    # --- Scale-in pozíciókezelés ---
    if score >= 0.5 and float(portfolio.get('ZEUR', 0)) >= amount * 0.25:

        # Csak akkor vásároljunk újra, ha eladás után új vételi jelzés érkezett
        from datetime import datetime
        if can_enter_new_buy(pair, datetime.now()):
            steps_done = get_position_state(pair)["steps"]
            if steps_done < 4:
                step = record_trade_step(pair, amount)
                decision = f"VÉTEL (lépés {step}/4)"
                
                              
                buy_amount = round(amount * 0.25, 2)
                log_trade(pair, "BUY", result, sentiment, buy_amount)
                if trader.LIVE_TRADING:
                    execute_trade("buy", pair, buy_amount)
                    print("💰 Valós VÉTEL végrehajtva.")
            else:
                decision = "MÁR TELJES POZÍCIÓ"
        else:
            decision = "⏸️ Eladás után várakozás – új vételi jelzésre várunk"

    final_decision_var.set(decision)
    
    if trader.LIVE_TRADING and ("VÉTEL" in decision or "ELADÁS" in decision):
        final_decision_var.set(f"{decision} ✅ [ÉLŐ]")
    
    from datetime import datetime
    if not can_enter_new_buy(pair, datetime.now()):
        sell_waiting_var.set("Várakozás új vételi jelzésre - ⛔")
    else:
        sell_waiting_var.set("Új belépés engedélyezett - ✅")

    
    from datetime import datetime
    timestamp_full_var.set("Frissítve: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    # Skálázott belépés állapota
    steps = get_position_state(pair)["steps"]
    scalein_var.set(f"{steps}/4 lépés teljesítve")

   
    # 🔄 Trigger szint frissítése, ha van aktív pozíció
    if score >= 0.5:
        update_trigger_price(pair, price)


    if auto_running:
        after_id = root.after(interval * 60 * 1000, update_data)

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

# --- Grafikon gomb ---
def plot_graph():
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
        print("📉 Hiba a grafikon megjelenítéskor:", e)

def toggle_live_trading():
    trader.save_live_trading_setting(live_trading_var.get())
    print("💾 LIVE_TRADING mentve:", live_trading_var.get())



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
ttk.Label(frame_controls, textvariable=final_decision_var, font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="w")

start_button = ttk.Button(frame_controls, text="▶️ Indítás", command=toggle_auto)
start_button.grid(row=1, column=0, pady=5, sticky="w")

ttk.Button(frame_controls, text="📈 Grafikon megjelenítése", command=plot_graph).grid(row=1, column=1, pady=5, sticky="w")
ttk.Button(frame_controls, text="Kilépés", command=root.destroy).grid(row=1, column=2, pady=5, sticky="e")


update_data()

root.mainloop()
