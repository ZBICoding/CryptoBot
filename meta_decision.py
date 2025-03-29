# meta_decision.py

def make_final_decision(rsi_signal, ai_prediction, sentiment, confidence, trigger_ok):
    """
    Meta-döntéshozatal több forrás alapján.

    Paraméterek:
    - rsi_signal: "BUY", "SELL", "HOLD"
    - ai_prediction: 0 (le) vagy 1 (fel)
    - sentiment: "positive", "negative", "neutral"
    - confidence: 0.0 - 1.0 közötti bizalmi szint
    - trigger_ok: árfolyam megerősítő trigger teljesült-e

    Visszaadott érték: "BUY", "SELL", vagy None
    """

    # Szabály alapú súlyozás
    if not trigger_ok:
        return None  # ha az ár nem lépett át kulcsszintet

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

    # Bizalom alapján normalizált score-hoz igazítva
    score *= confidence

    # Végső döntés küszöbérték alapján
    if score > 0.4:
        return "BUY"
    elif score < -0.4:
        return "SELL"
    else:
        return None
