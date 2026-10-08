"""
Bear / base / bull scenario valuation.

Model (3-year horizon, works for any company with positive
earnings, including financials):

    value today = EPS x (1 + g)^3 x exit P/E / (1 + cost of equity)^3

Scenario inputs come from OBSERVED ranges, not arbitrary +/-%:

    growth      bear = weaker of: worst observed annual profit growth,
                       or growth stalling to the long-run rate (5%)
                base = multi-year profit (or revenue) CAGR, capped
                bull = strongest of recent quarterly / annual growth
    exit P/E    bear = average of peer / own-history 25th percentiles
                base = average of peer / own-history medians
                bull = average of peer / own-history 75th percentiles

The bear case includes "growth stalls" so that a company whose
whole history is a boom still gets a genuine downside case.

No probabilities are assigned (they would be invented). Instead
the payoff asymmetry (bull upside vs bear downside) is reported.

Scenarios are NOT blended into the fair-value range: they reuse
the peer and historical P/E inputs and would double-count them.
"""

from src import config
from src.expectations import MAX_REFERENCE_GROWTH, historical_cagr
from src.utils import calculate_upside_pct, is_positive, latest_valid
from src.valuation import estimate_cost_of_equity


HORIZON_YEARS = 3
GROWTH_BOUNDS = (-0.15, 0.35)


def _bounded(growth):
    low, high = GROWTH_BOUNDS
    return min(max(growth, low), high)


def scenario_growth_rates(fundamental_data, quarterly_data):
    """
    Growth rates per scenario from the company's own history.
    Net income is used rather than EPS because it is not
    distorted by splits and bonus issues.
    """

    base = historical_cagr(fundamental_data, "Net_Income")
    base_basis = "net income CAGR"

    if base is None:
        base = historical_cagr(fundamental_data, "Revenue")
        base_basis = "revenue CAGR"

    if base is None:
        return None

    observations = []

    if fundamental_data is not None and "Net_Income_Growth" in fundamental_data:
        observations = [
            g / 100
            for g in fundamental_data["Net_Income_Growth"].dropna().tolist()
        ]

    recent = latest_valid(quarterly_data, "Net_Profit_YoY")

    bull_candidates = observations + [base]

    if recent is not None:
        bull_candidates.append(recent / 100)

    bear = _bounded(
        min(observations + [base, config.DCF_TERMINAL_GROWTH])
    )
    bull = _bounded(max(bull_candidates))
    base = _bounded(min(base, MAX_REFERENCE_GROWTH))

    return {
        "bear": bear,
        "base": base,
        "bull": bull,
        "basis": (
            f"bear = worst year or stall to "
            f"{config.DCF_TERMINAL_GROWTH * 100:.0f}%, base = {base_basis}, "
            f"bull = strongest recent/annual profit growth "
            f"({len(observations)} annual observations)"
        ),
        "observations": len(observations),
    }


def scenario_exit_multiples(method_results):
    """Exit P/E per scenario from peer and own-history ranges."""

    sources = [
        method_results.get(m, {})
        for m in ("peer_pe", "historical_pe")
    ]

    sources = [s for s in sources if s.get("available")]

    if not sources:
        return None

    names = []

    if method_results.get("peer_pe", {}).get("available"):
        names.append("peer P/E")
    if method_results.get("historical_pe", {}).get("available"):
        names.append("own historical P/E")

    def average(key):
        return sum(s[key] for s in sources) / len(sources)

    return {
        "bear": average("multiple_low"),
        "base": average("multiple_median"),
        "bull": average("multiple_high"),
        "basis": " and ".join(names),
    }


def run_scenarios(
    company_profile,
    method_results,
    inputs,
    fundamental_data,
    quarterly_data,
    price,
    raw_beta
):

    eps = inputs.get("trailing_eps")

    usable = company_profile.get(
        "earnings_usable", company_profile.get("positive_earnings")
    )

    if not usable or not is_positive(eps):
        return {
            "available": False,
            "reason": "Scenario valuation needs positive earnings.",
        }

    growth = scenario_growth_rates(fundamental_data, quarterly_data)

    if growth is None:
        return {
            "available": False,
            "reason": "No earnings or revenue history to build scenarios.",
        }

    multiples = scenario_exit_multiples(method_results)

    if multiples is None:
        return {
            "available": False,
            "reason": "No peer or historical P/E range for exit multiples.",
        }

    cost_of_equity, _, _ = estimate_cost_of_equity(raw_beta)

    discount = (1 + cost_of_equity) ** HORIZON_YEARS

    cases = {}

    for name in ("bear", "base", "bull"):

        g = growth[name]
        exit_pe = multiples[name]

        future_eps = eps * (1 + g) ** HORIZON_YEARS

        value = future_eps * exit_pe / discount

        cases[name] = {
            "growth": g,
            "exit_pe": exit_pe,
            "future_eps": future_eps,
            "value": value,
            "upside": calculate_upside_pct(price, value),
        }

    bear_upside = cases["bear"]["upside"]
    bull_upside = cases["bull"]["upside"]

    if bear_upside >= 0:
        asymmetry = None
        asymmetry_text = "Even the bear case is at or above the current price"
    elif bull_upside <= 0:
        asymmetry = 0.0
        asymmetry_text = "Even the bull case is below the current price"
    else:
        asymmetry = bull_upside / abs(bear_upside)
        asymmetry_text = (
            f"Bull upside {bull_upside:+.0f}% vs bear downside "
            f"{bear_upside:+.0f}% (ratio {asymmetry:.1f}x)"
        )

    return {
        "available": True,
        "horizon_years": HORIZON_YEARS,
        "cost_of_equity": cost_of_equity,
        "cases": cases,
        "growth_basis": growth["basis"],
        "multiple_basis": multiples["basis"],
        "limited_history": growth["observations"] < 3,
        "payoff_ratio": asymmetry,
        "payoff_summary": asymmetry_text,
        "note": (
            "Excludes dividends; no probabilities are assigned to scenarios."
        ),
    }
