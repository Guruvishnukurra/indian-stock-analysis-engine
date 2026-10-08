"""
Business-type routing beyond the basic company type.

One valuation recipe cannot serve every company. These checks decide
WHICH earnings and cash-flow base the valuation methods should use:

    cyclical            commodity-type industry AND volatile margins in
                        the company's own history -> value on mid-cycle
                        (median) margins, warn near peaks and troughs
    capex-heavy growth  heavy investment makes free cash flow negative
                        although the business generates cash -> value on
                        maintenance free cash flow (operating cash flow
                        minus depreciation as a proxy for upkeep capex)
    holding company     value lies in listed/unlisted stakes -> needs a
                        sum-of-the-parts, which is not implemented
    real estate / pharma / utilities: flagged method limitations

Every decision carries a plain-language reason.
"""

import statistics

from src.utils import is_positive, is_valid, valid_values


CYCLICAL_INDUSTRY_KEYWORDS = [
    "steel", "aluminum", "copper", "industrial metals", "gold", "silver",
    "coking coal", "thermal coal", "building materials", "chemicals",
    "agricultural inputs", "oil & gas", "paper", "solar", "lumber",
]

# Relative swing of operating margin (max - min) / median across the
# available years that confirms a company actually behaves cyclically.
MIN_MARGIN_SWING = 0.40
MIN_YEARS = 3

PEAK_FACTOR = 1.3
TROUGH_FACTOR = 0.7

HOLDING_PHRASES = ["holding company", "investment company", "investment holding"]


def assess_cyclicality(industry, fundamental_data):

    text = str(industry or "").lower()

    if not any(keyword in text for keyword in CYCLICAL_INDUSTRY_KEYWORDS):
        return {"cyclical": False}

    margins = [
        m for m in valid_values(fundamental_data, "Operating_Margin")
        if is_valid(m)
    ]

    if len(margins) < MIN_YEARS:
        return {
            "cyclical": False,
            "cyclical_note": (
                f"Commodity-type industry ({industry}) but too little history "
                "to judge the cycle."
            ),
        }

    median = statistics.median(margins)

    if median <= 0:
        return {"cyclical": False}

    swing = (max(margins) - min(margins)) / median

    if swing < MIN_MARGIN_SWING:
        return {
            "cyclical": False,
            "cyclical_note": (
                f"Commodity-type industry ({industry}) but margins have been "
                f"stable ({min(margins):.1f}-{max(margins):.1f}%): valued normally."
            ),
        }

    # One-off items (impairments, exceptional gains) are excluded from the
    # mid-cycle margin where the source reports normalized profit.
    net_margins = [
        m for m in valid_values(fundamental_data, "Normalized_Net_Margin")
        if is_valid(m)
    ] or [m for m in valid_values(fundamental_data, "Net_Margin") if is_valid(m)]

    mid_cycle_net = statistics.median(net_margins) if net_margins else None

    current = margins[-1]

    position = (
        "peak" if current > median * PEAK_FACTOR
        else "trough" if current < median * TROUGH_FACTOR
        else "mid"
    )

    return {
        "cyclical": True,
        "mid_cycle_operating_margin": median,
        "mid_cycle_net_margin": mid_cycle_net,
        "current_operating_margin": current,
        "cycle_position": position,
        "cyclical_note": (
            f"Cyclical: operating margin ranged {min(margins):.1f}-{max(margins):.1f}% "
            f"over {len(margins)} years (median {median:.1f}%, latest {current:.1f}%). "
            "Earnings are valued at mid-cycle (median) margins; "
            f"{len(margins)} years may not cover a full cycle."
        ),
    }


def maintenance_fcf(fundamental_data, years=3):
    """
    Operating cash flow minus depreciation (upkeep proxy), averaged.
    Returns (value, n_years) or (None, 0).
    """

    if fundamental_data is None or fundamental_data.empty:
        return None, 0

    data = fundamental_data[["Operating_Cash_Flow", "Depreciation"]].dropna().tail(years)

    if data.empty:
        return None, 0

    values = (data["Operating_Cash_Flow"] - data["Depreciation"].abs()).tolist()

    return sum(values) / len(values), len(values)


def assess_capex_heavy(fundamental_data, normalized_fcf, earnings_usable):
    """
    Growth investment, not distress: free cash flow is weak only because
    capex far exceeds depreciation while operations generate cash.
    """

    if not earnings_usable or fundamental_data is None or fundamental_data.empty:
        return {"capex_heavy": False}

    capex = [abs(v) for v in valid_values(fundamental_data, "Capital_Expenditure", last_n=3)]
    depreciation = [abs(v) for v in valid_values(fundamental_data, "Depreciation", last_n=3)]
    ocf = valid_values(fundamental_data, "Operating_Cash_Flow", last_n=3)
    income = valid_values(fundamental_data, "Net_Income", last_n=3)

    if not (capex and depreciation and ocf and income):
        return {"capex_heavy": False}

    capex_ratio = sum(capex) / max(sum(depreciation), 1.0)

    weak_fcf = (
        not is_positive(normalized_fcf)
        or normalized_fcf < 0.3 * (sum(income) / len(income))
    )

    if capex_ratio < 2.0 or not weak_fcf or sum(ocf) <= 0:
        return {"capex_heavy": False}

    value, years = maintenance_fcf(fundamental_data)

    if not is_positive(value):
        return {"capex_heavy": False}

    return {
        "capex_heavy": True,
        "maintenance_fcf": value,
        "capex_note": (
            f"Capex-heavy growth: capex was {capex_ratio:.1f}x depreciation over "
            f"the last {len(capex)} years, so free cash flow understates the "
            "business. DCF uses maintenance free cash flow (operating cash flow "
            "minus depreciation); this assumes the growth capex earns at least "
            "its cost of capital."
        ),
    }


def is_holding_company(industry, business_summary):

    text = str(business_summary or "").lower()

    if "conglomerate" in str(industry or "").lower():
        return True

    return any(phrase in text for phrase in HOLDING_PHRASES)
