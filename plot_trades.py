def plot_trades():

    import pandas as pd
    import matplotlib.pyplot as plt

    # CSV fájl neve
    log_file = "trades_2025_03_25.csv"

    # Adatok betöltése
    df = pd.read_csv(log_file, parse_dates=["Dátum"])

    # Színkód a döntésekhez
    decision_colors = df["Akció"].map({
        "VÉTEL": "green",
        "ELADÁS": "red",
        "NINCS JELZÉS": "gray"
    }).fillna("blue")

    # Hírhangulat színek
    sentiment_colors = df["Hírhangulat"].map({
        "positive": "blue",
        "neutral": "gray",
        "negative": "brown"
    }).fillna("gray")
    
    # AI predikció numerikusan
    ai_numeric = df["AI_predikció"].map({"⬆️": 1, "⬇️": 0}).fillna(0)
    
    # Ábra létrehozása
    fig, axs = plt.subplots(3, 1, figsize=(14, 12), sharex=True, gridspec_kw={'height_ratios': [2, 1, 1]})
    
    # 1. panel: Árfolyam + döntések + hírhangulat
    axs[0].plot(df["Dátum"], df["Záróár"], label="Záróár (EUR)", color="black", linewidth=2)
    axs[0].scatter(df["Dátum"], df["Záróár"], c=decision_colors, s=120, edgecolors="k", label="Kereskedési döntés", marker="o")
    axs[0].scatter(df["Dátum"], df["Záróár"], c=sentiment_colors, marker="x", s=100, label="Hírhangulat")
    axs[0].set_ylabel("Záróár (EUR)")
    axs[0].set_title("Árfolyam, döntések és hírhangulat")
    axs[0].legend()
    axs[0].grid(True)
    
    # 2. panel: RSI
    axs[1].plot(df["Dátum"], df["RSI"], label="RSI", color="orange", linestyle='--')
    axs[1].axhline(70, color="red", linestyle="dotted", alpha=0.5)
    axs[1].axhline(30, color="green", linestyle="dotted", alpha=0.5)
    axs[1].set_ylabel("RSI")
    axs[1].set_title("RSI indikátor")
    axs[1].legend()
    axs[1].grid(True)
    
    # 3. panel: AI predikció
    axs[2].plot(df["Dátum"], ai_numeric, label="AI predikció (⬆️=1, ⬇️=0)", color="blue", linestyle='dotted', marker='o')
    axs[2].set_ylabel("AI predikció")
    axs[2].set_ylim(-0.1, 1.1)
    axs[2].set_title("AI előrejelzés")
    axs[2].legend()
    axs[2].grid(True)
    
    # Közös X tengely
    plt.xlabel("Idő")
    plt.tight_layout()
    plt.show()

