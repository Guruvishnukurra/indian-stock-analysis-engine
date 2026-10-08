"""
Confidence score (0-100) for the fair-value assessment.

Confidence answers: "how much should you trust the fair-value
range?" It is about data and method reliability, NOT about
whether the stock is attractive. A weak technical trend is a
risk, not a reason for low confidence.

Each component has a fixed maximum and an explicit reason.
The point allocations are heuristic and documented, not fitted.

    Data completeness          20
    Number of valid methods    20
    Agreement between methods  20
    Peer support               15
    Earnings stability         15
    Classification certainty   10
                              ---
                              100   (minus explicit penalties)
"""

from src import config
from src.utils import label_from_thresholds, valid_values


MATERIAL_METHOD_WEIGHT = 0.10

# Peer multiple spread (75th / 25th percentile).
PEER_SPREAD_WIDE = 1.8
PEER_SPREAD_VERY_WIDE = 2.5

SHARP_DECLINE = 0.20

# Methods in the same family share inputs (e.g. the same peer set),
# so their agreement is not independent confirmation.
METHOD_FAMILIES = {
    "dcf": "intrinsic",
    "peer_pe": "peer",
    "peer_pb": "peer",
    "peer_evs": "peer",
    "historical_pe": "own_history",
    "growth_dcf": "intrinsic",
}


def material_families(fair_value):

    weights = fair_value.get("weights_used", {})

    families = {}

    for method, weight in weights.items():
        family = METHOD_FAMILIES.get(method, method)
        families[family] = families.get(family, 0) + weight

    return [f for f, w in families.items() if w >= MATERIAL_METHOD_WEIGHT]

CONSISTENCY_PENALTY = 5


def _component(name, points, maximum, positives=None, concerns=None):
    return {
        "name": name,
        "points": round(points, 1),
        "max": maximum,
        "positives": positives or [],
        "concerns": concerns or [],
    }


def score_data_completeness(data_quality):

    quality = data_quality.get("score") or 0
    years = data_quality.get("annual_years", 0)

    points = 20 * quality / 100

    positives, concerns = [], []

    if quality >= 90:
        positives.append("Core financial statements are complete")
    elif quality < 70:
        concerns.append(f"Financial data only {quality:.0f}% complete")

    if years < 3:
        points -= 5
        concerns.append(f"Only {years} year(s) of annual financials")

    return _component(
        "Data completeness", max(points, 0), 20, positives, concerns
    )


def score_method_count(fair_value):
    """
    Counts independent method FAMILIES with material weight
    (intrinsic, peer-relative, own-history), not individual
    methods: P/E and P/B on the same peer set are one source.
    """

    families = material_families(fair_value)

    count = len(families)

    points = {0: 0, 1: 8, 2: 15}.get(count, 20)

    positives, concerns = [], []

    if count >= 2:
        positives.append(
            f"{count} independent valuation approaches "
            f"({', '.join(sorted(families))})"
        )
    elif count == 1:
        concerns.append(
            f"Only one independent valuation approach ({families[0]})"
        )
    else:
        concerns.append("No valuation method available")

    return _component("Valuation methods", points, 20, positives, concerns)


def score_agreement(fair_value):

    dispersion = fair_value.get("dispersion")

    if dispersion is None or dispersion.get("coefficient_of_variation") is None:

        if fair_value.get("available"):
            return _component(
                "Method agreement", 5, 20,
                concerns=["Single method: cannot cross-check"]
            )

        return _component("Method agreement", 0, 20)

    cv = dispersion["coefficient_of_variation"]

    # Agreement within one family (same inputs) is weak evidence.
    single_family = len(material_families(fair_value)) < 2

    if cv < 0.10:
        points, text = 20, "Valuation methods broadly agree"
    elif cv < 0.20:
        points, text = 14, "Valuation methods moderately agree"
    elif cv < 0.35:
        points, text = 7, "Valuation methods disagree materially"
    else:
        points, text = 0, "Valuation methods disagree strongly"

    text += f" (dispersion {cv * 100:.0f}%)"

    if single_family and points > 10:
        return _component(
            "Method agreement", 10, 20,
            concerns=[text + ", but they share the same inputs (not independent)"]
        )

    if points >= 14:
        return _component("Method agreement", points, 20, positives=[text])

    return _component("Method agreement", points, 20, concerns=[text])


def score_peer_support(method_results, fair_value):
    """
    Number of peers, discounted when peers are heterogeneous:
    a wide spread of peer multiples means the median is a poor
    description of "the typical peer".
    """

    weights = fair_value.get("weights_used", {})

    peer_methods = [
        method_results[m]
        for m in weights
        if m.startswith("peer_")
    ]

    count = max(
        (r.get("peer_count", 0) for r in peer_methods),
        default=0
    )

    if count >= 8:
        points = 15
    elif count >= 5:
        points = 11
    elif count >= 3:
        points = 7
    elif count >= 1:
        points = 3
    else:
        points = 0

    positives, concerns = [], []

    if count >= 5:
        positives.append(f"{count} valid peers")
    else:
        concerns.append(
            f"Only {count} valid peer(s)"
            if count
            else "No peer comparison available"
        )

    # Spread of the main peer multiple (highest-weighted peer method).
    main = max(
        (m for m in weights if m.startswith("peer_")),
        key=lambda m: weights[m],
        default=None
    )

    if main is not None:

        result = method_results[main]

        low = result.get("multiple_low")
        high = result.get("multiple_high")

        if low and high and low > 0:

            spread = high / low

            if spread > PEER_SPREAD_VERY_WIDE:
                points -= 8
            elif spread > PEER_SPREAD_WIDE:
                points -= 5

            if spread > PEER_SPREAD_WIDE:
                concerns.append(
                    f"Peers are heterogeneous: multiples range "
                    f"{low:.1f}x–{high:.1f}x (median less representative)"
                )

    return _component(
        "Peer support", max(points, 0), 15, positives, concerns
    )


def score_earnings_stability(fundamental_data):
    """
    Share of profitable years, minus a penalty for each sharp
    earnings decline. Fast growth is NOT treated as instability.
    """

    incomes = valid_values(fundamental_data, "Net_Income")

    if len(incomes) < 3:
        return _component(
            "Earnings stability", 4, 15,
            concerns=["Too little earnings history to judge stability"]
        )

    positive_share = sum(1 for v in incomes if v > 0) / len(incomes)

    points = 15 * positive_share

    sharp_declines = sum(
        1
        for previous, current in zip(incomes, incomes[1:])
        if previous > 0 and current < previous * (1 - SHARP_DECLINE)
    )

    points -= 4 * sharp_declines

    positives, concerns = [], []

    if positive_share < 1:
        losses = len(incomes) - round(positive_share * len(incomes))
        concerns.append(f"Loss-making in {losses} of {len(incomes)} years")

    if sharp_declines:
        concerns.append(
            f"Earnings fell more than {SHARP_DECLINE * 100:.0f}% "
            f"in {sharp_declines} year(s)"
        )

    if positive_share == 1 and not sharp_declines:
        positives.append(
            f"Profitable in all {len(incomes)} years without sharp declines"
        )

    return _component(
        "Earnings stability", max(points, 0), 15, positives, concerns
    )


def score_classification(company_profile):

    certainty = company_profile.get("classification_certainty", "Low")

    points = {"High": 10, "Medium": 6}.get(certainty, 2)

    basis = company_profile.get("classification_basis", "")

    if certainty == "High":
        return _component(
            "Classification", points, 10,
            positives=[f"Clear classification ({basis})"]
        )

    return _component(
        "Classification", points, 10,
        concerns=[f"Uncertain classification ({basis})"]
    )


def penalties(method_results, fair_value, data_quality=None,
              peer_analysis=None):

    items = []

    if (peer_analysis or {}).get("mixed_ownership") and any(
        m.startswith("peer_") for m in fair_value.get("weights_used", {})
    ):
        items.append((
            5,
            "Peer set mixes PSU and private companies "
            "(structurally different multiples)"
        ))

    for issue in (data_quality or {}).get("consistency_issues", []):
        items.append((CONSISTENCY_PENALTY, f"Data inconsistency: {issue}"))

    weights = fair_value.get("weights_used", {})

    if "peer_evs" in weights:
        items.append((
            10,
            "Loss-making or barely profitable: relies on an EV/Sales fallback"
        ))

    if "growth_dcf" in weights:
        items.append((
            5,
            "Pre-profit valuation depends on an assumed mature margin"
        ))

    dcf = method_results.get("dcf", {})

    if (
        "dcf" in weights
        and not dcf.get("assumptions", {}).get("growth_from_data", True)
    ):
        items.append((3, "DCF growth is a default assumption"))

    return items


def calculate_confidence(
    data_quality,
    fair_value,
    method_results,
    fundamental_data,
    company_profile,
    peer_analysis=None
):

    components = [
        score_data_completeness(data_quality),
        score_method_count(fair_value),
        score_agreement(fair_value),
        score_peer_support(method_results, fair_value),
        score_earnings_stability(fundamental_data),
        score_classification(company_profile),
    ]

    penalty_items = penalties(
        method_results, fair_value, data_quality, peer_analysis
    )

    total = (
        sum(c["points"] for c in components)
        - sum(p for p, _ in penalty_items)
    )

    total = max(0.0, min(100.0, total))

    positives = [p for c in components for p in c["positives"]]

    concerns = (
        [c for comp in components for c in comp["concerns"]]
        + [text for _, text in penalty_items]
    )

    return {
        "score": round(total),
        "label": label_from_thresholds(total, config.CONFIDENCE_LABELS),
        "components": components,
        "penalties": penalty_items,
        "reasons": positives,
        "concerns": concerns,
    }
