"""AI components: verification logic and graceful fallbacks (offline)."""

import pandas as pd

from src import news_events
from src.news import classify_news_events
from src.peer_selection import add_similarity
from src.thesis import verify_thesis, write_thesis


FACTS = {
    "current_price_inr": 2076,
    "fair_value_range_inr": "2050 to 3500",
    "upside_to_base_percent": 30,
    "confidence": "High (77/100)",
}

DISCLAIMER = " This is an analytical assessment, not investment advice."


def test_thesis_with_fact_numbers_passes():
    text = (
        "Trading at ₹2,076 against a fair-value range of ₹2,050 to ₹3,500, "
        "the base case implies about 30% upside, with confidence 77/100."
        + DISCLAIMER
    )
    ok, problems = verify_thesis(text, FACTS)
    assert ok, problems


def test_invented_number_is_rejected():
    text = "Revenue should grow 18% next year." + DISCLAIMER
    ok, problems = verify_thesis(text, FACTS)
    assert not ok
    assert any("18" in p for p in problems)


def test_advice_language_and_missing_disclaimer_rejected():
    ok, problems = verify_thesis("You should buy this stock at ₹2,076.", FACTS)
    assert not ok
    assert any("Forbidden" in p for p in problems)
    assert any("disclaimer" in p for p in problems)


def test_small_counting_numbers_allowed():
    text = "Three risks stand out across 2 valuation approaches." + DISCLAIMER
    assert verify_thesis(text, FACTS)[0]


def test_thesis_unavailable_without_llm():
    assert write_thesis({"company_profile": {}})["available"] is False


def test_news_events_skipped_without_llm():
    news = pd.DataFrame({"Headline": ["X"], "Date": [pd.Timestamp.now(tz="UTC")]})
    assert classify_news_events("Co", news) is None


def test_event_summary_separates_material_from_noise():
    news = pd.DataFrame({"Headline": ["Q2 profit up 20%", "Shares rise 2%", "SEBI penalty"]})
    classified = [
        {"event_type": "earnings", "direction": "positive"},
        {"event_type": "price_move", "direction": "neutral"},
        {"event_type": "regulatory_legal", "direction": "negative"},
    ]

    summary = news_events.summarize_events(news, classified)

    assert summary["catalysts"] == ["[earnings] Q2 profit up 20%"]
    assert summary["risks"] == ["[regulatory_legal] SEBI penalty"]
    assert abs(summary["noise_share"] - 1 / 3) < 1e-9


def test_similarity_failure_falls_back_to_market_cap(monkeypatch):
    import src.embeddings as embeddings

    def broken(*args, **kwargs):
        raise RuntimeError("no model")

    monkeypatch.setattr(embeddings, "similarity_to", broken)

    peers = pd.DataFrame({"Ticker": ["A.NS"], "Summary": ["bank"]})

    data, note = add_similarity(peers, "a bank")

    assert "Similarity" not in data.columns
    assert "market cap" in note


def test_thesis_contradicting_stance_is_rejected():
    text = "An attractive opportunity at ₹2,076." + DISCLAIMER
    ok, problems = verify_thesis(text, FACTS, stance="WATCH")
    assert not ok
    assert any("stance" in p for p in problems)


def test_neutral_material_events_are_reported():
    news = pd.DataFrame({"Headline": ["Board meeting to consider results"]})
    summary = news_events.summarize_events(
        news, [{"event_type": "earnings", "direction": "neutral"}]
    )
    assert summary["other_material"] == ["[earnings] Board meeting to consider results"]


def test_syndicated_rewrites_are_deduplicated():
    from src.news import deduplicate_news

    news = pd.DataFrame({
        "Headline": [
            "Infosys bags multi-year deal from Danske Bank worth $454 million - ET",
            "Infosys bags $454 million multi-year deal from Danske Bank - Business Standard",
            "TCS wins $500 million deal from European bank - Moneycontrol",
        ],
        "Date": pd.to_datetime(["2026-10-08", "2026-10-08", "2026-10-07"], utc=True),
    })

    assert len(deduplicate_news(news)) == 2


def test_skipped_headlines_are_reasked(monkeypatch):
    calls = []

    def fake_batch(company, headlines, version):
        calls.append(len(headlines))
        if len(headlines) > 1:          # model skips the second headline
            return [{"event_type": "earnings", "direction": "positive"}, None]
        return [{"event_type": "management", "direction": "neutral"}]

    monkeypatch.setattr(news_events, "_classify_batch", fake_batch)

    result = news_events.classify_headlines("Co", ["a", "b"])

    assert result[1]["event_type"] == "management"
    assert calls == [2, 1]


def test_same_story_listed_once(monkeypatch):
    # Word-overlap rule only (no embedding model in unit tests).
    monkeypatch.setattr(news_events, "_embedding", lambda headline: None)

    news = pd.DataFrame({"Headline": [
        "HDFC Bank Limited Securities Fraud Class Action Result of - GlobeNewswire",
        "HDFC Bank Limited Class Action Reminder about Securities Fraud - Robbins LLP",
        "SEBI fines HDFC Bank over disclosure lapse - ET",
    ]})
    negative = {"event_type": "regulatory_legal", "direction": "negative"}

    summary = news_events.summarize_events(news, [negative] * 3)

    assert len(summary["risks"]) == 2
