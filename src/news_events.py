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
import re

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

BATCH_SIZE = 8


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

        # The model sometimes skips items in a batch. Re-ask skipped
        # headlines one at a time instead of silently treating them as
        # noise.
        for position, event in enumerate(classified):
            if event is None:
                single = _classify_batch(
                    company_name, (batch[position],), PROMPT_VERSION
                )
                classified[position] = single[0] if single else None

        output.extend(classified)

    return output


SAME_STORY = 0.5

_WORD = re.compile(r"[a-z0-9]+")

_COMMON = {"the", "and", "for", "with", "limited", "ltd", "shares", "share",
           "stock", "india", "after", "from", "over", "into"}


def _story_words(headline):
    text = re.sub(r"\s+-\s+[^-]+$", "", str(headline).lower())
    return {w for w in _WORD.findall(text) if len(w) > 2 and w not in _COMMON}


def _repeats_listed_story(headline, listed_words):
    words = _story_words(headline)
    return any(
        words and other and len(words & other) / len(words | other) >= SAME_STORY
        for other in listed_words
    )


def summarize_events(news, classifications, max_items=4):
    """
    Material catalysts and risks from classified, de-duplicated news
    (newest first). Price-move commentary is counted, not reported.
    """

    catalysts, risks, neutral = [], [], []
    counts = {}
    listed_words = []

    for (_, row), event in zip(news.iterrows(), classifications):

        if not event:
            continue

        event_type = event["event_type"]
        counts[event_type] = counts.get(event_type, 0) + 1

        if event_type not in MATERIAL_TYPES:
            continue

        item = f"[{event_type}] {row['Headline']}"

        # One story repeated by several outlets (e.g. law-firm notices of
        # the same class action) is listed once.
        if _repeats_listed_story(row["Headline"], listed_words):
            continue

        listed_words.append(_story_words(row["Headline"]))

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


# =========================================================
# SECOND PASS: verify items before they are reported
# =========================================================
# The first pass classifies headlines in batches and is right about the
# exact event type only ~60% of the time. Items it calls MATERIAL are
# re-checked one at a time with an explicit decision procedure; only
# confirmed company events reach the report.

VERIFY_TYPES = sorted(MATERIAL_TYPES) + ["rating_target", "price_move", "macro_sector", "other"]

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_company_event": {"type": "boolean"},
        "event_type": {"type": "string", "enum": VERIFY_TYPES},
        "direction": {"type": "string", "enum": ["positive", "negative", "neutral"]},
    },
    "required": ["is_company_event", "event_type", "direction"],
}

VERIFY_PROMPT = (
    "You check one news headline about an Indian listed company. Decide "
    "step by step, then answer only with JSON.\n\n"
    "Step 1 - is_company_event: true ONLY if the headline reports a NEW, "
    "CONCRETE action or result of THIS company: results announced, a "
    "contract/order/partnership signed, a dividend/buyback/bonus/fund-raise "
    "declared, an acquisition/merger/stake sale agreed, a regulator or court "
    "action against or approval for it, or an executive appointed or "
    "leaving. It is FALSE for headlines that only describe the share price "
    "moving, ask why the stock moved, preview events that have not happened, "
    "list stocks to watch, report broker/analyst ratings or targets, cover "
    "the whole market or sector, or are mainly about another company.\n"
    "Step 2 - event_type: if true, the matching type: "
    + ", ".join(f"{t} ({EVENT_TYPES[t]})" for t in sorted(MATERIAL_TYPES))
    + ". If false: rating_target for broker/analyst opinions, price_move for "
    "price commentary or previews, macro_sector for market/sector-wide news, "
    "other otherwise.\n"
    "Step 3 - direction: impact on the company's business (not the share "
    "price): positive, negative, or neutral if unclear."
)

VERIFY_VERSION = hashlib.sha1(
    (LLM_MODEL + VERIFY_PROMPT).encode("utf-8")
).hexdigest()[:12]


@cached("news_events_verify", 30 * DAY)
def _verify_one(company_name, headline, proposed_type, version=VERIFY_VERSION):

    return chat_json(
        VERIFY_PROMPT,
        f"Company: {company_name}\nHeadline: {headline}\n"
        f"(A first reader suggested: {proposed_type}.)",
        VERIFY_SCHEMA,
    )


def verify_classifications(company_name, headlines, classifications):
    """
    Re-check every item the first pass called material. Confirmed items
    keep the verifier's type and direction; rejected ones take the
    verifier's non-material type. If the verifier fails, the item is
    dropped from material rather than reported unchecked.
    """

    refined = []

    for headline, event in zip(headlines, classifications):

        if not event or event.get("event_type") not in MATERIAL_TYPES:
            refined.append(event)
            continue

        check = _verify_one(company_name, headline, event["event_type"], VERIFY_VERSION)

        if not check:
            refined.append({"event_type": "other", "direction": "neutral",
                            "verified": False})
            continue

        event_type = check["event_type"]

        if not check["is_company_event"] and event_type in MATERIAL_TYPES:
            event_type = "other"

        if check["is_company_event"] and event_type not in MATERIAL_TYPES:
            event_type = event["event_type"]

        refined.append({
            "event_type": event_type,
            "direction": check["direction"],
            "verified": True,
        })

    return refined
