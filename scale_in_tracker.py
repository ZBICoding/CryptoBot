import json
import os
from datetime import datetime

TRACK_FILE = "open_positions.json"

def load_positions():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_positions(data):
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def record_trade_step(pair, total_amount):
    data = load_positions()
    entry = data.get(pair, {"steps": 0, "amount": 0, "timestamp": str(datetime.now())})

    if entry["steps"] < 4:
        entry["steps"] += 1
        entry["amount"] += round(total_amount * 0.25, 4)
        entry["timestamp"] = str(datetime.now())
        data[pair] = entry
        save_positions(data)
        return entry["steps"]
    else:
        return 4  # már teljesen beléptünk

def reset_position(pair):
    data = load_positions()
    if pair in data:
        del data[pair]
        save_positions(data)

# ✅ Eladás időpontjának mentése
def record_last_sell_time(pair):
    data = load_positions()
    entry = data.get(pair, {"steps": 0, "amount": 0, "timestamp": str(datetime.now())})
    entry["last_sell_time"] = str(datetime.now())
    data[pair] = entry
    save_positions(data)

# ✅ Csak akkor enged új vásárlást, ha az eladás óta eltelt időnél frissebb a jelzés
def can_enter_new_buy(pair, current_time):
    data = load_positions()
    entry = data.get(pair, {})
    last_sell = entry.get("last_sell_time")
    if last_sell:
        try:
            return datetime.fromisoformat(str(current_time)) > datetime.fromisoformat(last_sell)
        except:
            return True  # ha formázási hiba van, inkább engedjük
    return True  # nincs előző eladás, szabad a vásárlás


def get_position_state(pair):
    data = load_positions()
    return data.get(pair, {"steps": 0, "amount": 0})

# ✅ ÚJ: Trigger szint mentése
def save_trigger_level(pair, level):
    data = load_positions()
    entry = data.get(pair, {"steps": 0, "amount": 0, "timestamp": str(datetime.now())})
    entry["trigger_level"] = round(level, 4)
    data[pair] = entry
    save_positions(data)

# ✅ ÚJ: Trigger szint lekérdezése
def get_trigger_level(pair):
    data = load_positions()
    entry = data.get(pair, {})
    return entry.get("trigger_level", None)

# ✅ ÚJ: Trigger újrakalibrálása, ha az ár jelentősen elmozdult
def recalibrate_trigger(pair, direction, current_price, tolerance=0.02):
    """
    direction: "BUY" vagy "SELL"
    tolerance: 2% elmozdulás után kalibrál újra
    """
    old = get_trigger_level(pair)
    if old is None:
        return  # nincs mit újrakalibrálni

    diff = abs(current_price - old) / old
    if diff >= tolerance:
        new_trigger = round(current_price * (0.99 if direction == "BUY" else 1.01), 4)
        save_trigger_level(pair, new_trigger)
        print(f"♻️ Trigger újrakalibrálva: {pair} új szint: {new_trigger}")

def update_trigger_price(pair, new_price):
    data = load_positions()
    if pair in data:
        data[pair]["trigger_price"] = round(new_price, 4)
        data[pair]["last_updated"] = str(datetime.now())
        save_positions(data)
