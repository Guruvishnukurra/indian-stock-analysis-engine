"""
News event classification with a local language model.

Sentiment alone is not a signal. This module tags each headline
with WHAT happened, so material events (results, orders,
regulatory action, management change, ...) can be separated
from noise such as daily price-move commentary.

Accuracy is measured against hand-checked labels
(scripts/evaluate_news_events.py) before being relied on.
"""

import hashlib

from src.cache import DAY, cached
from src.llm import LLM_MODEL, chat_json


EVENT_TYPES = {
    "earnings": "Quarterly/annual results, profit, revenue, margins, guidance",
    "order_contract": "New orders, contracts, deals won, partnerships, launches",
    "corporate_action": "Dividend, buyback, bonus, split, fund raising, QIP, rights issue",
    "m_and_a": "Merger, acquisition, stake sale, divestment",
    "regulatory_legal": "Regulator action, penalty, lawsuit, tax demand, probe, license",
    "management": "CEO/MD/board appointments or exits, auditor changes",
    "rating_target": "Broker rating or target price change, credit rating action",
    "price_move": "Commentary that only describes the stock price moving (no new event)",
    "macro_sector": "Economy, interest rates, sector-wide or market-wide news",
    "other": "Anything else, or not about this company",
}

MATERIAL_TYPES = {
    "earnings", "order_contract", "corporate_action",
    "m_and_a", "regulatory_legal", "management",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
                    "direction": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                    },
                },
                "required": ["id", "event_type", "direction"],
            },
        }
    },
    "required": ["events"],
}

SYSTEM_PROMPT = (
    "You classify financial news headlines about one Indian listed "
    "company. For each headline, choose exactly one event_type and the "
    "direction of its likely impact on the company's fundamentals "
    "(not on today's share price). Answer only with JSON.\n\n"
    "Event types:\n"
    + "\n".join(f"- {name}: {text}" for name, text in EVENT_TYPES.items())
    + "\n\nGuidelines:\n"
    "1. If the headline names a concrete event as the reason for a price "
    "move, classify the EVENT, not the price move.\n"
    "2. If it only reports the price moving, a price prediction, technical "
    "signals, 'stocks to watch' or 'buzzing stocks' lists, use price_move.\n"
    "3. Previews of results that have NOT happened yet ('ahead of', "
    "'before', 'what to expect') are price_move, not earnings.\n"
    "4. Any analyst or broker rating, target price or 'sees X% upside' is "
    "rating_target, even if a price move is also mentioned.\n"
    "5. Investors, promoters or founders buying or selling shares, block "
    "deals, stake purchases and subsidiary IPOs are m_and_a.\n"
    "6. Government tax or policy changes and regulatory approvals that "
    "apply to the company are regulatory_legal.\n"
    "7. Operating updates (client additions, loan growth, volumes) are "
    "earnings.\n"
    "8. Whole-market moves (Sensex/Nifty) without a company event are "
    "macro_sector.\n"
    "9. Direction is neutral unless the event clearly helps or hurts the "
    "business."
)

BATCH_SIZE = 15


# Cache key includes the model and prompt, so changing either
# never reuses stale classifications.
PROMPT_VERSION = hashlib.sha1(
    (LLM_MODEL + SYSTEM_PROMPT).encode("utf-8")
).hexdigest()[:12]


@cached("news_events", 30 * DAY)
def _classify_batch(company_name, headlines, prompt_version=PROMPT_VERSION):

    numbered = "\n".join(f"{i}. {h}" for i, h in enumerate(headlines))

    result = chat_json(
        SYSTEM_PROMPT,
        f"Company: {company_name}\n\nHeadlines:\n{numbered}",
        SCHEMA,
    )

    if not result:
        return None

    by_id = {e["id"]: e for e in result.get("events", []) if "id" in e}

    return [by_id.get(i) for i in range(len(headlines))]


def classify_headlines(company_name, headlines):
    """
    Returns a list (same order as headlines) of
    {"event_type", "direction"} dicts, or None for headlines the
    model failed to classify. Returns None if the model is down.
    """

    headlines = list(headlines)

    output = []

    for start in range(0, len(headlines), BATCH_SIZE):

        batch = tuple(headlines[start:start + BATCH_SIZE])

        classified = _classify_batch(company_name, batch, PROMPT_VERSION)

        if classified is None:
            return None

        output.extend(classified)

    return output


def summarize_events(news, classifications, max_items=4):
    """
    Material catalysts and risks from classified, de-duplicated news
    (newest first). Price-move commentary is counted, not reported.
    """

    catalysts, risks, neutral = [], [], []
    counts = {}

    for (_, row), event in zip(news.iterrows(), classifications):

        if not event:
            continue

        event_type = event["event_type"]
        counts[event_type] = counts.get(event_type, 0) + 1

        if event_type not in MATERIAL_TYPES:
            continue

        item = f"[{event_type}] {row['Headline']}"

        if event["direction"] == "positive" and len(catalysts) < max_items:
            catalysts.append(item)
        elif event["direction"] == "negative" and len(risks) < max_items:
            risks.append(item)
        elif event["direction"] == "neutral" and len(neutral) < max_items:
            neutral.append(item)

    total = sum(counts.values())

    return {
        "catalysts": catalysts,
        "risks": risks,
        "other_material": neutral,
        "event_counts": counts,
        "material_share": (
            sum(counts.get(t, 0) for t in MATERIAL_TYPES) / total
            if total else None
        ),
        "noise_share": (
            (counts.get("price_move", 0) + counts.get("other", 0)) / total
            if total else None
        ),
    }
