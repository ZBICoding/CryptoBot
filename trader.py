import krakenex
import json
import os

SETTINGS_FILE = "settings.json"

# 🔁 Betöltés fájlból
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 🔐 Alapértelmezett érték
SETTINGS = load_settings()
LIVE_TRADING = load_live_trading_setting()

def save_live_trading_setting(value):
    SETTINGS["live_trading"] = value
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(SETTINGS, f, indent=2)


# ✅ Konfigurációs kapcsoló
LIVE_TRADING = False 

# Minimum kereskedési összeg
MIN_TRADE_EUR = 5.0  

def execute_trade(pair, action, volume, price=None):
    if not pair.endswith("EUR"):
        raise ValueError("A párnak EUR-ban kell végződnie.")

    # Minimum érték ellenőrzés
    if float(volume) < MIN_TRADE_EUR / 2:  # mivel 0.25 * amount lehet
        print(f"⛔ A megadott mennyiség túl alacsony ({volume}).")
        return {"error": ["Minimum érték alatt."]}

    k = krakenex.API()
    k.load_key("kraken.key")

    # Elérhető egyenleg lekérdezése
    balance_resp = k.query_private("Balance")
    if balance_resp.get("error"):
        print("❌ Egyenleglekérdezés hiba:", balance_resp["error"])
        return balance_resp

    base_currency = pair[:3]
    quote_currency = "ZEUR"

    # Egyenlegellenőrzés
    balance = balance_resp.get("result", {})
    if action.lower() == "buy":
        available = float(balance.get(quote_currency, 0))
        if available < float(volume):
            print(f"⛔ Nincs elég {quote_currency} az egyenlegen. Elérhető: {available}")
            return {"error": ["Nincs elég fedezet."]}
    else:
        available = float(balance.get(base_currency, 0))
        if available < float(volume):
            print(f"⛔ Nincs elég {base_currency} eladásra. Elérhető: {available}")
            return {"error": ["Nincs elég coin eladásra."]}

    # Kereskedési hívás
    params = {
        "pair": pair,
        "type": action.lower(),
        "ordertype": "market",
        "volume": str(volume)
    }

    if price:
        params["ordertype"] = "limit"
        params["price"] = str(price)

    response = k.query_private("AddOrder", params)

    if response["error"]:
        print("❌ Kraken trade hiba:", response["error"])
    else:
        print(f"✅ Sikeres {action.upper()} rendelés:", response["result"])

    return response

    LIVE_SETTINGS_FILE = "live_settings.json"

    def save_live_trading_setting(enabled: bool):
        with open(LIVE_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"LIVE_TRADING": enabled}, f)

    def load_live_trading_setting() -> bool:
        if os.path.exists(LIVE_SETTINGS_FILE):
            try:
                with open(LIVE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("LIVE_TRADING", False)
            except Exception as e:
                print("⚠️ Hiba a live_settings.json betöltésekor:", e)
        return False  # alapértelmezett érték