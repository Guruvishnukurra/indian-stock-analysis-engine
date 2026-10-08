"""
Combine valuation methods into a fair-value RANGE.

CORE methods (configured weight >= CONTEXT_WEIGHT_THRESHOLD) build the
base estimate and the range:

    base   = weighted average of core central estimates
    range  = weighted core lows/highs (each method's own uncertainty:
             DCF sensitivity, peer interquartile multiples, ...),
             widened if needed so it spans every core method's central
             estimate (disagreement between credible methods is shown,
             not averaged away)

CONTEXT methods (low configured weight, e.g. own-history P/E) are
reported next to the range but never move it: one extreme reference
must not explode the range.

No arbitrary +/-20% band is used.
"""

import math

from src.config import CONTEXT_WEIGHT_THRESHOLD
from src.utils import calculate_upside_pct, is_positive, round_price


METHOD_LABELS = {
    "dcf": "DCF",
    "peer_pe": "Peer P/E",
    "historical_pe": "Historical P/E",
    "peer_pb": "Peer P/B",
    "peer_evs": "Peer EV/Sales",
    "growth_dcf": "Growth-stage DCF",
}


def split_methods(method_results, weights):
    """
    (core, context) method names among those that produced a value.
    If no core method is available, context methods are used as core.
    """

    available = [
        m for m, r in method_results.items()
        if r.get("available") and weights.get(m, 0) > 0
    ]

    core = [m for m in available if weights[m] >= CONTEXT_WEIGHT_THRESHOLD]
    context = [m for m in available if weights[m] < CONTEXT_WEIGHT_THRESHOLD]

    if not core:
        return context, []

    return core, context


def normalized_weights(method_results, weights):
    """Core-method weights renormalised over methods that produced a value."""

    core, _ = split_methods(method_results, weights)

    total = sum(weights[m] for m in core)

    if total <= 0:
        return {}

    return {m: weights[m] / total for m in core}


def method_dispersion(method_results, used_weights):
    """
    How much the methods disagree.

    Returns the weighted standard deviation of base values and
    the coefficient of variation (std / mean). None if fewer
    than two methods.
    """

    if len(used_weights) < 2:
        return None

    bases = {m: method_results[m]["base"] for m in used_weights}

    mean = sum(bases[m] * w for m, w in used_weights.items())

    variance = sum(
        w * (bases[m] - mean) ** 2
        for m, w in used_weights.items()
    )

    std = math.sqrt(variance)

    values = list(bases.values())

    return {
        "weighted_std": std,
        "coefficient_of_variation": std / mean if mean > 0 else None,
        "max_to_min": max(values) / min(values),
    }


def build_fair_value_range(method_results, weights, current_price):

    used_weights = normalized_weights(method_results, weights)

    _, context = split_methods(method_results, weights)

    context_methods = {
        METHOD_LABELS.get(m, m): {
            "base": method_results[m]["base"],
            "upside": calculate_upside_pct(current_price, method_results[m]["base"]),
        }
        for m in context
    }

    if not used_weights:
        return {
            "available": False,
            "reason": "No valuation method produced a usable value.",
            "methods_used": [],
            "context_methods": context_methods,
        }

    def weighted(key):
        return sum(
            method_results[m][key] * w
            for m, w in used_weights.items()
        )

    base = weighted("base")
    low = weighted("low")
    high = weighted("high")

    core_bases = [method_results[m]["base"] for m in used_weights]

    widened_for_disagreement = (
        min(core_bases) < low or max(core_bases) > high
    )

    low = max(min(low, min(core_bases)), 0.0)
    high = max(high, max(core_bases))

    return {
        "available": True,
        "base": base,
        "low": low,
        "high": high,
        "base_rounded": round_price(base),
        "low_rounded": round_price(low) if is_positive(low) else None,
        "high_rounded": round_price(high),
        "upside_base": calculate_upside_pct(current_price, base),
        "upside_low": calculate_upside_pct(current_price, low),
        "upside_high": calculate_upside_pct(current_price, high),
        "weights_used": used_weights,
        "methods_used": [METHOD_LABELS.get(m, m) for m in used_weights],
        "method_upsides": {
            METHOD_LABELS.get(m, m): calculate_upside_pct(
                current_price, method_results[m]["base"]
            )
            for m in used_weights
        },
        "dispersion": method_dispersion(method_results, used_weights),
        "widened_for_disagreement": widened_for_disagreement,
        "context_methods": context_methods,
    }
