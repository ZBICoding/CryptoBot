import schedule
import time
import threading
from datetime import datetime
from bot_logic_FULL import analyze_all

# Napi retrain hívása egy alapértelmezett párral (vagy többel is, ha szeretnél)
def retrain_models():
    print(f"🧠 Újratanítás indítása: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        for pair in ["SOLEUR", "BTCEUR", "ETHEUR", "DOTEUR", "XRPEUR"]:
            analyze_all(pair)
        print("✅ AI modellek napi újratanítása sikeresen lefutott.")
    except Exception as e:
        print("❌ Hiba a napi retrain során:", e)

# Időzítő indítása külön szálon, hogy ne akadályozza a GUI-t
def start_daily_retraining():
    schedule.every().day.at("04:00").do(retrain_models)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # percenként ellenőrzés

    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
