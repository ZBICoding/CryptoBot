import pandas as pd
from sklearn.linear_model import LogisticRegression
import joblib
import os

META_MODEL_FILE = "meta_model.pkl"

# Tanító adat hozzáadása
def update_meta_training_data(rsi_signal, ai_prediction, sentiment, actual_trade):
    data = {
        "RSI": 1 if rsi_signal == "BUY" else (-1 if rsi_signal == "SELL" else 0),
        "AI": ai_prediction,
        "Sentiment": 1 if sentiment == "positive" else (-1 if sentiment == "negative" else 0),
        "ActualTrade": actual_trade  # 1 ha helyes vétel volt, 0 ha nem hozott hasznot
    }

    df = pd.DataFrame([data])
    file_exists = os.path.exists("meta_training.csv")
    df.to_csv("meta_training.csv", mode="a", index=False, header=not file_exists)

# Modell tanítása
def train_meta_model():
    if not os.path.exists("meta_training.csv"):
        print("⚠️ Nincs tanító adat a meta modellhez.")
        return

    df = pd.read_csv("meta_training.csv")
    X = df[["RSI", "AI", "Sentiment"]]
    y = df["ActualTrade"]

    model = LogisticRegression()
    model.fit(X, y)

    joblib.dump(model, META_MODEL_FILE)
    print("✅ Meta modell betanítva.")

# Predikció meta modell alapján
def predict_meta_decision(rsi_signal, ai_prediction, sentiment):
    if not os.path.exists(META_MODEL_FILE):
        return None  # nincs modell

    model = joblib.load(META_MODEL_FILE)
    X = pd.DataFrame([{
        "RSI": 1 if rsi_signal == "BUY" else (-1 if rsi_signal == "SELL" else 0),
        "AI": ai_prediction,
        "Sentiment": 1 if sentiment == "positive" else (-1 if sentiment == "negative" else 0),
    }])

    pred = model.predict(X)[0]
    return pred  # 1: vétel indokolt, 0: nem
