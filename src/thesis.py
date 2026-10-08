"""
AI-written investment thesis, grounded and verified.

1. Build a FACTS sheet from the computed analysis (rounded values).
2. The local LLM writes a short thesis using only those facts.
3. Every number in the output is checked against the facts; any
   number not found, or any advice/guarantee language, rejects
   the text. The rule-based interpretation is then used instead.

The LLM therefore adds readability, never new information.
"""

import hashlib
import json
import re

from src.cache import DAY, cached
from src.llm import LLM_MODEL, chat_text, llm_available
from src.utils import is_valid


FORBIDDEN = [
    r"\bguarantee",
    r"\byou should (buy|sell)",
    r"\bstrong buy\b",
    r"\bstrong sell\b",
    r"\bwill (definitely|certainly)\b",
    r"\bsure to\b",
    r"\brisk[- ]free\b",
]

SYSTEM_PROMPT = (
    "You are a careful equity research writer. Write a concise investment "
    "thesis (120-170 words, plain prose, no headings, no bullet points) "
    "about the company described in the FACTS JSON.\n"
    "Rules:\n"
    "- Use ONLY information in FACTS. Do not add any number, date, "
    "percentage or claim that is not in FACTS.\n"
    "- Copy numbers exactly as written in FACTS, and keep their meaning "
    "(e.g. 'X% above the current price' must not become 'X% below').\n"
    "- Do NOT give your own overall verdict or call the stock attractive or "
    "unattractive; the engine's stance is added separately.\n"
    "- Cover: business quality, valuation versus the fair-value range, what "
    "the price assumes, the main risks, and current market condition.\n"
    "- Never tell the reader to buy or sell, and never promise outcomes.\n"
    "- End with: 'This is an analytical assessment, not investment advice.'"
)

NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def _round(value, digits=0):
    if not is_valid(value):
        return None
    value = round(float(value), digits)
    return int(value) if digits == 0 else value


def _without_price_gaps(items):
    """Drop 'price is X% above/below fair value' lines (see build_facts)."""
    return [
        item for item in items
        if "fair-value" not in item and "Scenario" not in item
        and "scenario" not in item
    ]


def build_facts(analysis):
    """A compact, pre-rounded facts sheet (the LLM's only source)."""

    fair_value = analysis.get("fair_value") or {}
    confidence = analysis.get("confidence") or {}
    explanation = analysis.get("explanation") or {}
    expectations = analysis.get("expectations") or {}
    scenarios = analysis.get("scenarios") or {}
    news_events = (analysis.get("news") or {}).get("events") or {}

    facts = {
        "company": analysis.get("company_name"),
        "company_type": analysis["company_profile"]["company_type"].replace("_", " "),
        "current_price_inr": _round(analysis.get("current_price")),
        "confidence": f"{confidence.get('label')} ({confidence.get('score')}/100)",
        "fundamental_quality": (
            f"{analysis['fundamental_score'].get('label')} "
            f"({_round(analysis['fundamental_score'].get('score'))}/100)"
        ),
        "strengths": _without_price_gaps(explanation.get("why_bullish", []))[:5],
        "weaknesses": _without_price_gaps(explanation.get("why_not_bullish", []))[:5],
        "risks": explanation.get("risks", [])[:4],
        "technical_condition": analysis["technical_score"].get("label"),
        "market_sector_condition": analysis["market_score"].get("label"),
    }

    if fair_value.get("available"):
        # Absolute levels plus a categorical position only: a small
        # model reliably flips percentage relationships ("X% above"
        # becomes "X% below"), so none are given.
        price = analysis.get("current_price")
        facts["fair_value_range_inr"] = (
            f"{_round(fair_value['low_rounded'])} to {_round(fair_value['high_rounded'])}"
        )
        facts["fair_value_base_inr"] = _round(fair_value["base_rounded"])
        facts["current_price_position"] = (
            "below the fair-value range" if price < fair_value["low"]
            else "above the fair-value range" if price > fair_value["high"]
            else "within the fair-value range"
        )
        facts["valuation_methods"] = fair_value.get("methods_used")

    if expectations.get("summary"):
        facts["what_the_price_assumes"] = expectations["summary"]

    if scenarios.get("available"):
        facts["scenario_values_today_inr_3y"] = {
            name: _round(case["value"])
            for name, case in scenarios["cases"].items()
        }

    if news_events.get("catalysts") or news_events.get("risks"):
        facts["news_catalysts"] = news_events.get("catalysts", [])[:3]
        facts["news_risks"] = news_events.get("risks", [])[:3]

    return facts


def _to_number(token):
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def allowed_numbers(facts):
    text = json.dumps(facts, ensure_ascii=False)
    return {
        abs(n) for n in (_to_number(t) for t in NUMBER.findall(text))
        if n is not None
    }


def verify_thesis(text, facts, stance=None):
    """
    Returns (ok, problems). A number passes if it matches a fact
    number within 1% (to allow '30.3' -> '30'). Small counting
    integers (0-10) not used as percentages or prices are allowed.
    """

    problems = []

    allowed = allowed_numbers(facts)

    for match in NUMBER.finditer(text):

        token = match.group()
        value = _to_number(token)

        if value is None:
            continue

        value = abs(value)

        following = text[match.end():match.end() + 1]
        preceding = text[max(0, match.start() - 1):match.start()]

        is_quantity = following == "%" or preceding == "₹"

        if not is_quantity and value <= 10 and value == int(value):
            continue

        if any(
            abs(value - fact) <= max(0.01 * abs(fact), 0.5)
            for fact in allowed
        ):
            continue

        problems.append(f"Unverified number: {token}")

    for pattern in FORBIDDEN:
        if re.search(pattern, text, flags=re.IGNORECASE):
            problems.append(f"Forbidden phrasing: {pattern}")

    if (
        stance is not None
        and stance != "ATTRACTIVE"
        and re.search(r"\battractive\b", text, flags=re.IGNORECASE)
    ):
        problems.append(f"Contradicts the engine's stance ({stance}).")

    if "not investment advice" not in text.lower():
        problems.append("Missing disclaimer sentence.")

    return not problems, problems


PROMPT_VERSION = hashlib.sha1(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]


@cached("thesis", 7 * DAY)
def _generate(facts_json, model, prompt_version=PROMPT_VERSION):
    return chat_text(SYSTEM_PROMPT, f"FACTS:\n{facts_json}", timeout=240)


def write_thesis(analysis):

    if not llm_available():
        return {"available": False, "reason": "Local LLM not running."}

    facts = build_facts(analysis)

    facts_json = json.dumps(facts, ensure_ascii=False, indent=1)

    text = _generate(facts_json, LLM_MODEL, PROMPT_VERSION)

    if not text:
        return {"available": False, "reason": "LLM returned no text."}

    text = text.strip()

    explanation = analysis.get("explanation") or {}
    confidence = analysis.get("confidence") or {}
    stance = explanation.get("stance")

    ok, problems = verify_thesis(text, facts, stance)

    if not ok:
        return {
            "available": False,
            "reason": "LLM thesis failed verification; rule-based interpretation used.",
            "problems": problems,
        }

    # The verdict comes from the engine, never from the LLM.
    verdict = (
        f"Engine stance: {stance} (confidence {confidence.get('label')}, "
        f"{confidence.get('score')}/100)."
    )

    return {
        "available": True,
        "text": text + "\n" + verdict,
        "model": LLM_MODEL,
        "verified": True,
        "facts_hash": hashlib.sha1(facts_json.encode("utf-8")).hexdigest()[:12],
        "note": (
            "Written by a local LLM from the engine's computed facts only; "
            "every number was checked against those facts."
        ),
    }
