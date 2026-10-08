"""
Split verdicts: quality, valuation and timing answer different
questions and are reported separately, next to the overall stance.

    quality    how good is the business?        (fundamental score)
    valuation  how is it priced vs fair value?  (log(fair value / price))
    timing     what is the price trend doing?   (technicals, weeks horizon)

Also:
    consensus gate   a fair value more than 2x away from analyst
                     consensus means the model likely cannot value the
                     company; no verdict is issued
    triggers         the price levels at which the verdict would change
"""

import math

from src import config
from src.utils import is_positive, is_valid


FAIR_BAND = math.log(1.15)          # within +/-15% of fair value = fairly valued
CONSENSUS_GATE = 2.0
MIN_ANALYSTS_FOR_GATE = 5

TIMING_HORIZON = "next few weeks"


def valuation_verdict(fair_value, price):

    if not fair_value.get("available") or not is_positive(fair_value.get("base")):
        return {"label": "Unavailable", "log_gap": None}

    log_gap = math.log(fair_value["base"] / price)

    if log_gap > FAIR_BAND:
        label = "Undervalued"
    elif log_gap < -FAIR_BAND:
        label = "Overvalued"
    else:
        label = "Fairly valued"

    return {
        "label": label,
        "log_gap": log_gap,
        "fair_value_to_price": fair_value["base"] / price,
        "measure": (
            f"fair value / price = {fair_value['base'] / price:.2f}x "
            f"(log gap {log_gap:+.2f}; within +/-{FAIR_BAND:.2f} counts as fair)"
        ),
    }


def timing_verdict(technical_score, latest_technical):

    label = technical_score.get("label", "Unavailable")

    notes = []

    rsi = latest_technical.get("RSI_14") if hasattr(latest_technical, "get") else None

    if is_valid(rsi):
        if rsi < 30 and label == "Weak":
            notes.append(
                f"Short-term oversold (RSI {rsi:.0f}) within a downtrend: a bounce "
                "over days is possible, but the trend over weeks is still down"
            )
        elif rsi > 70 and label == "Strong":
            notes.append(
                f"Short-term overbought (RSI {rsi:.0f}) within an uptrend: a pause "
                "over days is possible, but the trend over weeks is still up"
            )

    return {"label": label, "horizon": TIMING_HORIZON, "notes": notes}


def consensus_gate(fair_value, inputs):
    """
    Returns a reason string if the model's fair value is so far from
    analyst consensus that the model probably cannot value the company.
    Consensus is a sanity reference, never an input to fair value.
    """

    consensus = inputs.get("consensus_target")
    analysts = inputs.get("analyst_count") or 0

    if (
        not fair_value.get("available")
        or not is_positive(consensus)
        or analysts < MIN_ANALYSTS_FOR_GATE
    ):
        return None

    ratio = fair_value["base"] / consensus

    if ratio > CONSENSUS_GATE or ratio < 1 / CONSENSUS_GATE:
        return (
            f"The model's base fair value is {ratio:.2f}x the analyst consensus "
            f"({analysts} analysts). A gap over {CONSENSUS_GATE:.0f}x usually "
            "means the model's methods do not fit this company (e.g. a growth "
            "premium or a structure peers cannot capture), so no verdict is issued."
        )

    return None


def verdict_triggers(fair_value, price, stance):
    """Price levels at which the valuation-driven verdict would change."""

    if stance not in ("ATTRACTIVE", "WATCH", "AVOID") or not fair_value.get("available"):
        return []

    base = fair_value["base"]

    attractive_below = base / (1 + config.ATTRACTIVE_MIN_UPSIDE / 100)
    avoid_above = base / (1 + config.AVOID_MAX_UPSIDE / 100)

    triggers = []

    if price > attractive_below:
        triggers.append(
            f"Valuation would support ATTRACTIVE below about Rs {attractive_below:,.0f} "
            "(if quality and confidence hold)"
        )

    if price < avoid_above:
        triggers.append(
            f"Valuation would point to AVOID above about Rs {avoid_above:,.0f}"
        )

    triggers.append(
        "A change in the fair-value inputs (earnings, peer multiples, growth) "
        "moves these levels"
    )

    return triggers
