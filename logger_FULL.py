import csv
import os
from datetime import datetime

def log_trade(pair, action, result, sentiment, amount):
    today = datetime.now().strftime("%Y_%m_%d")
    filename = f"trades_{today}.csv"
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        if not file_exists:
            writer.writerow([
                "Dátum", "Pár", "Akció", "Záróár", "RSI", "RSI_jelzés",
                "AI_predikció", "Hírhangulat", "Összeg_EUR"
            ])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            pair,
            action,
            f"{result['price']:.2f}",
            f"{result['rsi']:.2f}",
            result['rsi_signal'],
            "⬆️" if result['ai_prediction'] == 1 else "⬇️",
            sentiment,
            amount
        ])
