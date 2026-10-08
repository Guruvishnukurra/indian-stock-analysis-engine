import re
from urllib.parse import quote_plus

import feedparser
import numpy as np
import pandas as pd

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


_FINBERT_PIPELINE = None


def get_finbert_pipeline():
    """Load FinBERT once per session (loading is slow)."""

    global _FINBERT_PIPELINE

    if _FINBERT_PIPELINE is None:

        from transformers import pipeline

        _FINBERT_PIPELINE = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert"
        )

    return _FINBERT_PIPELINE


def _normalize_headline(headline):
    """
    Google News appends " - Publisher" to titles. Syndicated
    copies of one story differ only in that suffix or in
    punctuation, so normalise before de-duplicating.
    """

    text = re.sub(r"\s+-\s+[^-]+$", "", str(headline))

    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


# Jaccard overlap of meaningful words above which two headlines are
# treated as the same story.
NEAR_DUPLICATE = 0.6

STOPWORDS = {
    "the", "and", "for", "with", "its", "after", "ahead", "from", "into",
    "over", "share", "shares", "stock", "stocks", "price", "today", "says",
    "here", "why", "what", "how", "this", "that", "are", "has", "was",
}


def deduplicate_news(news):
    """
    Remove syndicated/duplicate headlines so one story
    reprinted by ten outlets is not counted ten times.
    """

    if news.empty:
        return news

    data = news.copy()

    data["_key"] = data["Headline"].map(_normalize_headline)

    data = data.sort_values("Date", ascending=False)

    data = data.drop_duplicates(subset="_key", keep="first")

    # Near-duplicates: syndicated rewrites of one story share most of
    # their meaningful words even when the wording differs.
    kept, kept_tokens = [], []

    for index, key in data["_key"].items():

        tokens = {w for w in key.split() if len(w) > 2 and w not in STOPWORDS}

        duplicate = any(
            tokens and other
            and len(tokens & other) / len(tokens | other) >= NEAR_DUPLICATE
            for other in kept_tokens
        )

        if not duplicate:
            kept.append(index)
            kept_tokens.append(tokens)

    return data.loc[kept].drop(columns="_key").reset_index(drop=True)


def fetch_news(ticker, company_name, limit=100):
    """
    Fetch recent news using Google News RSS.
    """

    query = f"{company_name} stock"

    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query)}"
        "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    feed = feedparser.parse(rss_url)

    news_data = []

    for entry in feed.entries[:limit]:

        news_data.append({
            "Date": entry.get("published", ""),
            "Headline": entry.get("title", ""),
            "URL": entry.get("link", "")
        })

    news = pd.DataFrame(news_data)

    if not news.empty:
        news["Date"] = pd.to_datetime(
            news["Date"],
            errors="coerce",
            utc=True
        )

    return news


def calculate_vader_sentiment(news):
    """
    Calculate VADER sentiment for each headline.
    """

    data = news.copy()

    analyzer = SentimentIntensityAnalyzer()

    data["VADER_Score"] = data["Headline"].apply(
        lambda headline:
        analyzer.polarity_scores(headline)["compound"]
    )

    return data


def calculate_recency_weighted_vader(news, half_life_days=7):
    """
    Calculate recency-weighted VADER sentiment.

    More recent headlines receive greater weight.
    """

    data = news.copy()

    data = data.dropna(
        subset=["Date", "VADER_Score"]
    )

    if data.empty:
        return np.nan

    now = pd.Timestamp.now(tz="UTC")

    age_days = (
        now - data["Date"]
    ).dt.total_seconds() / 86400

    weights = (
        0.5 ** (age_days / half_life_days)
    )

    weighted_score = (
        data["VADER_Score"] * weights
    ).sum() / weights.sum()

    return weighted_score


def calculate_finbert_sentiment(news):
    """
    Calculate FinBERT sentiment for news headlines.

    Returns a signed score:
        positive -> positive value
        negative -> negative value
        neutral  -> near zero
    """

    data = news.copy()

    sentiment_model = get_finbert_pipeline()

    results = sentiment_model(
        data["Headline"].tolist(),
        truncation=True
    )

    signed_scores = []

    for result in results:

        label = result["label"].lower()
        score = result["score"]

        if label == "positive":
            signed_score = score

        elif label == "negative":
            signed_score = -score

        else:
            signed_score = 0.0

        signed_scores.append(signed_score)

    data["FinBERT_Score"] = signed_scores

    return data


def calculate_recency_weighted_finbert(
    news,
    half_life_days=7
):
    """
    Calculate recency-weighted FinBERT sentiment.
    """

    data = news.copy()

    data = data.dropna(
        subset=["Date", "FinBERT_Score"]
    )

    if data.empty:
        return np.nan

    now = pd.Timestamp.now(tz="UTC")

    age_days = (
        now - data["Date"]
    ).dt.total_seconds() / 86400

    weights = (
        0.5 ** (age_days / half_life_days)
    )

    weighted_score = (
        data["FinBERT_Score"] * weights
    ).sum() / weights.sum()

    return weighted_score


def calculate_news_score(
    vader_score,
    finbert_score
):
    """
    Convert VADER and FinBERT sentiment into
    a 0-100 news score.
    """

    components = [
        (score + 1) / 2 * 100
        for score in (vader_score, finbert_score)
        if pd.notna(score)
    ]

    # No sentiment available: report unavailable, not neutral.
    if not components:
        return None

    score = sum(components) / len(components)

    return max(0, min(100, score))


def label_news_score(news_score):

    if news_score is None or pd.isna(news_score):
        return "Unavailable"

    if news_score >= 60:
        return "Positive"

    if news_score <= 40:
        return "Negative"

    return "Neutral"


# Event types whose sentiment says something about the company itself.
SENTIMENT_EVENT_TYPES = {
    "earnings", "order_contract", "corporate_action", "m_and_a",
    "regulatory_legal", "management", "rating_target",
}

MIN_MATERIAL_FOR_SENTIMENT = 3


def classify_news_events(company_name, news):
    """
    Material-event tagging with the local LLM (if available).
    Returns None when the model is unavailable.
    """

    from src.llm import llm_available
    from src.news_events import classify_headlines, summarize_events

    if news.empty or not llm_available():
        return None

    recent = news.sort_values("Date", ascending=False).head(40)

    classifications = classify_headlines(
        company_name, recent["Headline"].tolist()
    )

    if classifications is None:
        return None

    summary = summarize_events(recent, classifications)

    summary["classified"] = [
        (headline, (event or {}).get("event_type"))
        for headline, event in zip(recent["Headline"], classifications)
    ]

    summary["accuracy_note"] = (
        "AI-tagged by a local LLM: 90% material-vs-noise accuracy and "
        "69% direction accuracy on 60 held-out headlines "
        "(labels not yet human-verified)."
    )

    return summary


def analyze_news(
    ticker,
    company_name,
    limit=100,
    use_finbert=True,
    use_llm_events=True
):
    """
    Run the complete news sentiment pipeline.

    Sentiment is descriptive context, not a trading signal.
    Never raises: any failure yields an "Unavailable" result.
    """

    empty_result = {
        "news": pd.DataFrame(),
        "vader_score": np.nan,
        "finbert_score": np.nan,
        "news_score": None,
        "label": "Unavailable",
        "article_count": 0,
        "duplicates_removed": 0,
        "top_positive": [],
        "top_negative": [],
        "events": None,
        "warnings": [],
    }

    try:
        news = fetch_news(
            ticker,
            company_name,
            limit
        )
    except Exception as error:
        empty_result["warnings"].append(f"News fetch failed: {error}")
        return empty_result

    if news.empty:
        empty_result["warnings"].append("No recent news found.")
        return empty_result

    raw_count = len(news)

    news = deduplicate_news(news)

    warnings = []

    news = calculate_vader_sentiment(news)

    vader_score = calculate_recency_weighted_vader(
        news
    )

    finbert_score = np.nan

    if use_finbert:
        try:
            news = calculate_finbert_sentiment(news)
            finbert_score = calculate_recency_weighted_finbert(
                news
            )
        except Exception as error:
            warnings.append(
                f"FinBERT unavailable ({error}); using VADER only."
            )

    news_score = calculate_news_score(
        vader_score,
        finbert_score
    )

    score_column = (
        "FinBERT_Score"
        if "FinBERT_Score" in news.columns
        else "VADER_Score"
    )

    ranked = news.sort_values(score_column)

    top_negative = ranked[ranked[score_column] < -0.3].head(3)
    top_positive = ranked[ranked[score_column] > 0.3].tail(3)[::-1]

    events = None

    if use_llm_events:
        try:
            events = classify_news_events(company_name, news)
        except Exception as error:
            warnings.append(f"News event tagging failed: {error}")

    sentiment_basis = f"all {len(news)} de-duplicated headlines"

    if events and events.get("classified"):

        material = {
            headline for headline, event_type in events["classified"]
            if event_type in SENTIMENT_EVENT_TYPES
        }

        subset = news[news["Headline"].isin(material)]

        if len(subset) >= MIN_MATERIAL_FOR_SENTIMENT:

            vader_score = calculate_recency_weighted_vader(subset)

            finbert_score = (
                calculate_recency_weighted_finbert(subset)
                if "FinBERT_Score" in subset.columns
                else np.nan
            )

            news_score = calculate_news_score(vader_score, finbert_score)

            sentiment_basis = (
                f"{len(subset)} material-event headlines "
                "(price-move commentary and off-topic items excluded)"
            )

        else:
            sentiment_basis += (
                f" (only {len(subset)} material headlines; too few to use alone)"
            )

    return {
        "news": news,
        "events": events,
        "sentiment_basis": sentiment_basis,
        "raw_article_count": raw_count,
        "vader_score": vader_score,
        "finbert_score": finbert_score,
        "news_score": news_score,
        "label": label_news_score(news_score),
        "article_count": len(news),
        "duplicates_removed": raw_count - len(news),
        "top_positive": top_positive["Headline"].tolist(),
        "top_negative": top_negative["Headline"].tolist(),
        "warnings": warnings,
    }
