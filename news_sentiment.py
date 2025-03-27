import feedparser
from textblob import TextBlob

# Például Cointelegraph RSS feed (angol hírek)
RSS_FEED_URL = "https://cointelegraph.com/rss"

def get_latest_news(max_articles=5):
    feed = feedparser.parse(RSS_FEED_URL)
    entries = feed.entries[:max_articles]
    news_list = [(entry.title, entry.link) for entry in entries]
    return news_list

def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        return "positive", polarity
    elif polarity < -0.1:
        return "negative", polarity
    else:
        return "neutral", polarity

def get_overall_sentiment():
    news = get_latest_news()
    sentiment_scores = []
    print("📰 Legfrissebb hírek és hangulatuk:\n")

    for title, link in news:
        sentiment, score = analyze_sentiment(title)
        sentiment_scores.append(score)
        print(f"• {title}\n  → {sentiment.upper()} (score: {score:.2f})")

    if not sentiment_scores:
        return "neutral"

    avg_score = sum(sentiment_scores) / len(sentiment_scores)

    if avg_score > 0.1:
        return "positive"
    elif avg_score < -0.1:
        return "negative"
    else:
        return "neutral"
