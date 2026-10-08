"""
Combine valuation methods into a fair-value RANGE.

Two sources of uncertainty are reflected:

1. Within-method uncertainty
   Each method already supplies low/base/high
   (DCF sensitivity, peer interquartile multiples, ...).
   These are weighted together.

2. Between-method disagreement
   If methods disagree, the range is widened to at least
   +/- one weighted standard deviation of the method base
   values around the combined base.

No arbitrary +/-20% band is used.
"""

import math

from src.utils import calculate_upside_pct, is_positive, round_price


METHOD_LABELS = {
    "dcf": "DCF",
    "peer_pe": "Peer P/E",
    "historical_pe": "Historical P/E",
    "peer_pb": "Peer P/B",
    "peer_evs": "Peer EV/Sales",
}


def normalized_weights(method_results, weights):
    """
    Weights renormalised over methods that produced a value.
    """

    usable = {
        method: weights[method]
        for method, result in method_results.items()
        if result.get("available")
        and weights.get(method, 0) > 0
    }

    total = sum(usable.values())

    if total <= 0:
        return {}

    return {
        method: weight / total
        for method, weight in usable.items()
    }


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

    if not used_weights:
        return {
            "available": False,
            "reason": "No valuation method produced a usable value.",
            "methods_used": [],
        }

    def weighted(key):
        return sum(
            method_results[m][key] * w
            for m, w in used_weights.items()
        )

    base = weighted("base")
    low = weighted("low")
    high = weighted("high")

    dispersion = method_dispersion(method_results, used_weights)

    widened_for_disagreement = False

    if dispersion is not None:

        std = dispersion["weighted_std"]

        if base - std < low:
            low = base - std
            widened_for_disagreement = True

        if base + std > high:
            high = base + std
            widened_for_disagreement = True

    low = max(low, 0.0)

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
        "dispersion": dispersion,
        "widened_for_disagreement": widened_for_disagreement,
    }
