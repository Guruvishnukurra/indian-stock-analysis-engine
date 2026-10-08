"""
Market-implied expectations ("reverse valuation").

Instead of asking "what is the stock worth?", ask
"what does the current price ASSUME?" and compare that
assumption with what the company has actually delivered.

Operating companies (positive FCF):
    Reverse DCF -> growth rate needed to justify the price.

Financial companies:
    Reverse residual income -> sustainable ROE needed to justify
    the price. Two stages: book value grows at its recent rate for
    10 years, then excess returns grow at long-run growth.
    (A single-stage P/B = (ROE - g)/(COE - g) cannot describe fast
    growing lenders and makes them all look absurdly expensive.)
"""

from src import config
from src.utils import is_positive, is_valid, latest_valid, valid_values
from src.valuation import calculate_dcf, estimate_cost_of_equity


GROWTH_SEARCH_BOUNDS = (-0.20, 0.60)

# Past growth above this is treated as a boom, not a sustainable
# yardstick for what the price should assume.
MAX_REFERENCE_GROWTH = 0.30

RI_GROWTH_YEARS = 10
BOOK_GROWTH_BOUNDS = (0.0, 0.18)
# Recent years only: older years can include mergers.
BOOK_GROWTH_LOOKBACK = 3


def historical_cagr(fundamental_data, column, max_years=4):
    """CAGR of a statement line; None without two positive endpoints."""

    values = valid_values(fundamental_data, column, last_n=max_years)

    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None

    years = len(values) - 1

    return (values[-1] / values[0]) ** (1 / years) - 1


def _assess_gap(gap_pp, thresholds):
    """
    thresholds: (undemanding_below, consistent_up_to, demanding_up_to)
    in percentage points of implied minus delivered.
    """

    undemanding, consistent, demanding = thresholds

    if gap_pp <= undemanding:
        return "Undemanding"
    if gap_pp <= consistent:
        return "Consistent with history"
    if gap_pp <= demanding:
        return "Demanding"
    return "Very demanding"


def reference_growth(delivered):
    """Best delivered growth, capped; returns (value, note)."""

    best = max(delivered)

    if best > MAX_REFERENCE_GROWTH:
        return MAX_REFERENCE_GROWTH, (
            f" (historical {best * 100:.0f}% capped at "
            f"{MAX_REFERENCE_GROWTH * 100:.0f}% as unsustainable)"
        )

    return best, ""


def solve_implied_growth(price, fcf, shares, wacc, net_cash, tolerance=1e-4):
    """
    Bisection for the stage-1 growth rate at which the DCF value
    equals the current price. All other DCF assumptions are held
    at their base values.
    """

    def value(growth):
        return calculate_dcf(
            free_cash_flow=fcf,
            shares_outstanding=shares,
            growth_rate=growth,
            terminal_growth=config.DCF_TERMINAL_GROWTH,
            wacc=wacc,
            forecast_years=config.DCF_HIGH_GROWTH_YEARS,
            net_cash=net_cash,
            fade_years=config.DCF_FADE_YEARS,
        ) or 0.0

    low, high = GROWTH_SEARCH_BOUNDS

    if value(low) >= price:
        return low, "below"

    if value(high) <= price:
        return high, "above"

    while high - low > tolerance:

        middle = (low + high) / 2

        if value(middle) < price:
            low = middle
        else:
            high = middle

    return (low + high) / 2, "solved"


def reverse_dcf(price, dcf_result, shares, fundamental_data):

    if not dcf_result.get("available"):
        return {"available": False, "reason": dcf_result.get("reason")}

    a = dcf_result["assumptions"]

    implied, status = solve_implied_growth(
        price,
        a["normalized_fcf"],
        shares,
        a["wacc"],
        a["net_cash"],
    )

    revenue_cagr = historical_cagr(fundamental_data, "Revenue")
    profit_cagr = historical_cagr(fundamental_data, "Net_Income")

    delivered = [g for g in (revenue_cagr, profit_cagr) if g is not None]

    result = {
        "available": True,
        "method": "Reverse DCF",
        "implied_growth": implied,
        "solve_status": status,
        "revenue_cagr": revenue_cagr,
        "profit_cagr": profit_cagr,
        "wacc": a["wacc"],
        "years_at_implied_growth": config.DCF_HIGH_GROWTH_YEARS,
    }

    if not delivered:
        result["assessment"] = "No growth history to compare"
        return result

    reference, cap_note = reference_growth(delivered)

    gap_pp = (implied - reference) * 100

    result["reference_growth"] = reference
    result["gap_pp"] = gap_pp
    result["assessment"] = _assess_gap(gap_pp, (-3, 3, 8))

    prefix = {"below": "under ", "above": "over "}.get(status, "")

    result["summary"] = (
        f"Price implies {prefix}{implied * 100:.1f}% annual FCF growth for "
        f"{config.DCF_HIGH_GROWTH_YEARS} years (then fading), vs "
        f"{reference * 100:.1f}% historical growth{cap_note}: "
        f"{result['assessment'].lower()}"
    )

    net_income = latest_valid(fundamental_data, "Net_Income")

    if (
        is_positive(net_income)
        and a["normalized_fcf"] / net_income < 0.5
        and result["assessment"] in ("Demanding", "Very demanding")
    ):
        result["summary"] += (
            " (FCF is currently depressed relative to profit; part of the "
            "implied growth may be capex normalising)"
        )

    return result


def residual_income_value(book_value, roe, cost_of_equity,
                          book_growth, long_run_growth,
                          years=RI_GROWTH_YEARS):
    """
    Value per share = book value + PV of residual income,
    residual income = (ROE - COE) x opening book value.
    """

    value = book_value
    book = book_value

    for year in range(1, years + 1):
        value += (roe - cost_of_equity) * book / (1 + cost_of_equity) ** year
        book *= 1 + book_growth

    terminal = (
        (roe - cost_of_equity) * book
        / (cost_of_equity - long_run_growth)
    )

    return value + terminal / (1 + cost_of_equity) ** years


def estimate_book_growth(fundamental_data):

    growth = historical_cagr(
        fundamental_data, "Equity", max_years=BOOK_GROWTH_LOOKBACK
    )

    low, high = BOOK_GROWTH_BOUNDS

    if growth is None:
        return config.DCF_TERMINAL_GROWTH, "long-run growth (no book history)"

    bounded = min(max(growth, low), high)

    basis = f"recent book value growth {growth * 100:.1f}%"

    if bounded != growth:
        basis += f", bounded to {bounded * 100:.0f}%"

    return bounded, basis


def reverse_residual_income(price, book_value_per_share, company_roe,
                            raw_beta, fundamental_data, tolerance=1e-5):

    if not is_positive(book_value_per_share):
        return {"available": False, "reason": "Book value unavailable."}

    cost_of_equity, _, _ = estimate_cost_of_equity(raw_beta)

    long_run = config.DCF_TERMINAL_GROWTH

    book_growth, growth_basis = estimate_book_growth(fundamental_data)

    def value(roe):
        return residual_income_value(
            book_value_per_share, roe, cost_of_equity, book_growth, long_run
        )

    low, high = 0.0, 1.0

    if value(high) < price:
        implied = high
    else:
        while high - low > tolerance:
            middle = (low + high) / 2
            if value(middle) < price:
                low = middle
            else:
                high = middle
        implied = (low + high) / 2

    implied_roe = implied * 100

    result = {
        "available": True,
        "method": "Reverse residual income",
        "price_to_book": price / book_value_per_share,
        "implied_roe": implied_roe,
        "cost_of_equity": cost_of_equity,
        "book_growth": book_growth,
        "book_growth_basis": growth_basis,
        "actual_roe": company_roe,
    }

    if not is_valid(company_roe):
        result["assessment"] = "Current ROE unavailable"
        return result

    gap_pp = implied_roe - company_roe

    result["gap_pp"] = gap_pp
    result["assessment"] = _assess_gap(gap_pp, (-3, 2, 6))

    result["summary"] = (
        f"P/B {result['price_to_book']:.2f}x implies a sustained ROE of "
        f"{implied_roe:.1f}% while book value grows {book_growth * 100:.0f}% "
        f"a year for {RI_GROWTH_YEARS} years (cost of equity "
        f"{cost_of_equity * 100:.1f}%), vs current ROE {company_roe:.1f}%: "
        f"{result['assessment'].lower()}"
    )

    return result


def reverse_earnings_dcf(price, shares, raw_beta, fundamental_data):
    """
    Asset-light financials (brokers, AMCs, exchanges) need little
    capital and pay out most of their earnings, so net income is
    used as the cash-flow proxy, discounted at cost of equity.
    """

    net_income = latest_valid(fundamental_data, "Net_Income")

    if not is_positive(net_income) or not is_positive(shares):
        return {"available": False, "reason": "Positive net income required."}

    cost_of_equity, _, _ = estimate_cost_of_equity(raw_beta)

    implied, status = solve_implied_growth(
        price, net_income, shares, cost_of_equity, 0.0
    )

    profit_cagr = historical_cagr(fundamental_data, "Net_Income")
    revenue_cagr = historical_cagr(fundamental_data, "Revenue")

    delivered = [g for g in (profit_cagr, revenue_cagr) if g is not None]

    result = {
        "available": True,
        "method": "Reverse earnings DCF (earnings as cash-flow proxy)",
        "implied_growth": implied,
        "solve_status": status,
        "profit_cagr": profit_cagr,
        "revenue_cagr": revenue_cagr,
        "cost_of_equity": cost_of_equity,
    }

    prefix = {"below": "under ", "above": "over "}.get(status, "")

    if not delivered:
        result["assessment"] = "No growth history to compare"
        result["summary"] = (
            f"Price implies {prefix}{implied * 100:.1f}% annual earnings "
            f"growth for {config.DCF_HIGH_GROWTH_YEARS} years; "
            "too little history to compare"
        )
        return result

    reference, cap_note = reference_growth(delivered)
    gap_pp = (implied - reference) * 100

    result["reference_growth"] = reference
    result["gap_pp"] = gap_pp
    result["assessment"] = _assess_gap(gap_pp, (-3, 3, 8))
    result["summary"] = (
        f"Price implies {prefix}{implied * 100:.1f}% annual earnings growth for "
        f"{config.DCF_HIGH_GROWTH_YEARS} years (then fading), vs "
        f"{reference * 100:.1f}% historical growth{cap_note}: "
        f"{result['assessment'].lower()}"
    )

    return result


def market_implied_expectations(
    company_profile,
    method_results,
    inputs,
    fundamental_data,
    price,
    raw_beta
):

    family = company_profile.get("valuation_family")
    company_type = company_profile.get("company_type")

    if family == "operating":

        growth = method_results.get("growth_dcf", {})

        # Pre-profit companies: what mature margin does the price need?
        if growth.get("implied_margin_summary"):
            implied = growth.get("implied_margin")
            peers = growth.get("assumptions", {}).get("peer_margins", {})
            median = peers.get("median")

            if implied is None or median is None:
                assessment = "Very demanding"
            else:
                gap = implied - median
                assessment = (
                    "Undemanding" if gap <= -3
                    else "Consistent with peers" if gap <= 2
                    else "Demanding" if gap <= 6
                    else "Very demanding"
                )

            return {
                "available": True,
                "method": "Reverse growth-stage DCF (implied mature margin)",
                "implied_margin": implied,
                "assessment": assessment,
                "summary": growth["implied_margin_summary"],
            }

        if not method_results.get("dcf", {}).get("available"):
            return {
                "available": False,
                "reason": (
                    "Reverse DCF needs positive normalised free cash flow."
                ),
            }

        return reverse_dcf(
            price,
            method_results["dcf"],
            inputs["shares_outstanding"],
            fundamental_data,
        )

    if company_type == "insurance":
        return {
            "available": False,
            "reason": (
                "An insurer's value lies in embedded value (not available "
                "from the data source); a book-ROE test would mislead."
            ),
        }

    if family == "asset_light_financial":
        return reverse_earnings_dcf(
            price,
            inputs["shares_outstanding"],
            raw_beta,
            fundamental_data,
        )

    return reverse_residual_income(
        price,
        inputs["book_value_per_share"],
        inputs["roe"],
        raw_beta,
        fundamental_data,
    )
