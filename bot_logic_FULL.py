import krakenex
import pandas as pd
import os
import joblib
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


MODEL_FILE = "model.pkl"
FEATURES_FILE = "features.csv"

def get_ohlc_data(pair="SOLEUR", interval=60):
    k = krakenex.API()
    k.load_key('kraken.key')
    data = k.query_public('OHLC', {'pair': pair, 'interval': interval})

    ohlc_key = [k for k in data['result'].keys() if k != 'last'][0]
    raw = data['result'][ohlc_key]

    df = pd.DataFrame(raw, columns=[
        'time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
    ])
    for col in ['open', 'high', 'low', 'close', 'vwap', 'volume']:
        df[col] = df[col].astype(float)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def prepare_data(df):
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    df['ema20'] = EMAIndicator(close=df['close'], window=20).ema_indicator()
    df['ema50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
    df['ema_diff'] = (df['ema20'] - df['ema50']) / df['ema50']
    df['return'] = df['close'].pct_change()
    df['volatility'] = df['close'].rolling(window=10).std()
    df['future_close'] = df['close'].shift(-1)
    df['target'] = (df['future_close'] > df['close']).astype(int)
    df = df.dropna()
    return df

def analyze_all(pair):
    df = get_ohlc_data(pair)
    df = prepare_data(df)

    # Jellemzők és cél
    feature_cols = ['rsi', 'ema20', 'ema50', 'ema_diff', 'return', 'volatility']
    X_new = df[feature_cols]
    y_new = df['target']

    # Előző adat betöltése, hozzáfűzés
    if os.path.exists(FEATURES_FILE):
        df_old = pd.read_csv(FEATURES_FILE, parse_dates=['time'], index_col='time')
        df_all = pd.concat([df_old, df], axis=0)
        df_all = df_all[~df_all.index.duplicated(keep='last')]
    else:
        df_all = df.copy()

    df_all.to_csv(FEATURES_FILE)

    X = df_all[feature_cols]
    y = df_all['target']

    # Modell betöltése vagy új létrehozása
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
    else:
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_split=4,
            min_samples_leaf=2,
            random_state=42
        )

    # Tanítás friss adattal
    X_train, X_test, y_train, y_test = train_test_split(X, y, shuffle=False, test_size=0.2)
    model.fit(X_train, y_train)
    joblib.dump(model, MODEL_FILE)

    # AI predikció
    ai_pred = model.predict(X.iloc[[-1]])[0]

    # RSI alapú jelzés
    close = df['close'].iloc[-1]
    rsi_value = df['rsi'].iloc[-1]
    ema = df['ema20'].iloc[-1]

    if rsi_value < 30 and close > ema:
        signal = "BUY"
    elif rsi_value > 70 or close < ema:
        signal = "SELL"
    else:
        signal = "HOLD"

    levels = detect_support_resistance(df)


    return {
        'price': close,
        'rsi': rsi_value,
        'rsi_signal': signal,
        'ai_prediction': ai_pred,
        'df': df,  
        "support_resistance": levels
    }


import matplotlib.pyplot as plt

def plot_ai_decision_graph(df):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df["Dátum"], df["close"], label="Árfolyam", linewidth=1.5)

    # Döntések megjelölése
    for i in range(len(df)):
        if "VÉTEL" in df["Akció"].iloc[i]:
            ax.plot(df["Dátum"].iloc[i], df["close"].iloc[i], "g^", markersize=10, label="Vétel" if i == 0 else "")
        elif df["Akció"].iloc[i] == "ELADÁS":
            ax.plot(df["Dátum"].iloc[i], df["close"].iloc[i], "rv", markersize=10, label="Eladás" if i == 0 else "")

    # Támasz / Ellenállás szintek detektálása
    close_prices = df["close"].values
    levels = []

    def is_support(i):
        return close_prices[i] < close_prices[i - 1] and close_prices[i] < close_prices[i + 1]

    def is_resistance(i):
        return close_prices[i] > close_prices[i - 1] and close_prices[i] > close_prices[i + 1]

    for i in range(2, len(close_prices) - 2):
        if is_support(i):
            levels.append(("support", df["Dátum"].iloc[i], close_prices[i]))
        elif is_resistance(i):
            levels.append(("resistance", df["Dátum"].iloc[i], close_prices[i]))

    for level in levels:
        if level[0] == "support":
            ax.hlines(level[2], df["Dátum"].iloc[0], df["Dátum"].iloc[-1], linestyles='dotted', colors='green', label="Támasz" if level == levels[0] else "")
        else:
            ax.hlines(level[2], df["Dátum"].iloc[0], df["Dátum"].iloc[-1], linestyles='dotted', colors='red', label="Ellenállás" if level == levels[0] else "")

    ax.set_title("📈 AI CryptoBot – Döntések és technikai szintek")
    ax.set_ylabel("Árfolyam (EUR)")
    ax.legend(loc="upper left")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def check_price_trigger(signal_type, current_price, df):
    """
    Árfolyam megerősítő trigger logika.
    Csak akkor ad zöld utat a kereskedéshez, ha az ár meghalad egy kulcsszintet.
    
    - BUY esetén: ha az ár > előző gyertya maximum
    - SELL esetén: ha az ár < előző gyertya minimum
    """

    if len(df) < 2:
        return False  # nincs elég adat

    prev_high = df['high'].iloc[-2]
    prev_low = df['low'].iloc[-2]

    if signal_type == "BUY" and current_price > prev_high:
        return True
    elif signal_type == "SELL" and current_price < prev_low:
        return True
    else:
        return False

import csv
from datetime import datetime

def init_pending_file():
    if not os.path.exists("pending_trades.csv"):
        with open("pending_trades.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Idő", "Coin pár", "Jelzés", "Bizalom (%)", "Trigger ár"])

def save_pending_trade(pair, signal_type, confidence, trigger_price):
    """
    Ment egy függőben lévő jelzést a pending_trades.csv fájlba.
    """
    with open("pending_trades.csv", mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(timespec='seconds'),
            pair,
            signal_type,
            round(confidence * 100, 1),
            trigger_price
        ])

def calculate_confidence_score(rsi_signal, ai_prediction, sentiment):
    score = 0.0

    if rsi_signal == "BUY":
        score += 0.2
    elif rsi_signal == "SELL":
        score -= 0.2

    if ai_prediction == 1:
        score += 0.5
    else:
        score -= 0.5

    if sentiment == "positive":
        score += 0.3
    elif sentiment == "negative":
        score -= 0.3

    normalized_score = (score + 1) / 2
    return max(0, min(normalized_score, 1))
    
    
def detect_support_resistance(df, window=5, sensitivity=0.005):
    support = []
    resistance = []

    for i in range(window, len(df) - window):
        low_slice = df['low'][i - window:i + window + 1]
        high_slice = df['high'][i - window:i + window + 1]

        current_low = df['low'].iloc[i]
        current_high = df['high'].iloc[i]

        if current_low == min(low_slice):
            if not any(abs(current_low - lvl) < sensitivity * current_low for lvl in support):
                support.append(current_low)

        if current_high == max(high_slice):
            if not any(abs(current_high - lvl) < sensitivity * current_high for lvl in resistance):
                resistance.append(current_high)

    return {
        "support": sorted(support),
        "resistance": sorted(resistance)
    }

