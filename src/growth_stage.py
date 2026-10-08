"""
Growth-stage ("path to profitability") valuation for loss-making or
barely profitable operating companies.

Today's earnings and today's sales multiples say little about a
company growing revenue 50-90% a year at a loss: its value depends on
the margin it reaches once it matures. Standard young-company DCF
(Damodaran-style):

    years 1..N   revenue growth fades linearly from current growth
                 to long-run growth; operating margin moves linearly
                 from today's margin to a mature TARGET margin
    cash flow    after-tax operating profit (no tax on losses)
                 minus reinvestment = revenue increase / sales-to-capital
    terminal     mature company: reinvestment = g / return on capital
    equity       enterprise value - net debt

The target margin comes from what mature PEERS actually earn
(25th / median / 75th percentile -> bear / base / bull).

The most useful output is the REVERSE question: which mature margin
does the current price require, and where would that rank among peers?

Beyond one base case, the model samples many plausible futures (growth,
mature margin from real peers, discount rate, capital intensity) and
reports the spread of values and the share of futures that justify the
current price. It also checks whether the company can fund itself until
it turns cash-positive (a funding gap means likely dilution).

Not modelled: probability of outright failure, tax-loss carry-forwards.
Results are a range with explicit assumptions, never a precise value.
"""

import numpy as np

from src import config
from src.utils import is_positive, is_valid
from src.valuation import estimate_wacc


YEARS = 10
MAX_START_GROWTH = 0.60          # first-year growth is capped
SALES_TO_CAPITAL = 2.0           # revenue per rupee of new invested capital
TERMINAL_EXCESS_RETURN = 0.02    # floor: mature return on capital >= WACC + 2pp
MARGIN_SEARCH = (-0.20, 0.60)

SIMULATIONS = 4000
SIM_SEED = 7
MARGIN_NOISE = 0.02              # +/-2pp around a resampled peer margin
WACC_NOISE = 0.01
SALES_TO_CAPITAL_RANGE = (1.5, 3.0)


def project_value(
    revenue,
    start_growth,
    start_margin,
    target_margin,
    wacc,
    net_debt,
    shares,
    years=YEARS,
    terminal_growth=config.DCF_TERMINAL_GROWTH,
    sales_to_capital=SALES_TO_CAPITAL,
    tax_rate=config.TAX_RATE,
    breakdown=False,
):
    """
    Equity value per share under one set of assumptions.

    breakdown=True returns a dict with the value, the share of value
    from the terminal value, the first year of positive free cash flow
    and the peak cumulative cash burn before that.
    """

    present_value = 0.0

    current_revenue = revenue

    cumulative_cash = 0.0
    peak_burn = 0.0
    first_positive_year = None

    for year in range(1, years + 1):

        fade = (year - 1) / (years - 1)
        growth = start_growth + (terminal_growth - start_growth) * fade

        margin = start_margin + (target_margin - start_margin) * year / years

        next_revenue = current_revenue * (1 + growth)

        operating_profit = next_revenue * margin

        after_tax = (
            operating_profit * (1 - tax_rate)
            if operating_profit > 0
            else operating_profit
        )

        reinvestment = (next_revenue - current_revenue) / sales_to_capital

        free_cash_flow = after_tax - reinvestment

        present_value += free_cash_flow / (1 + wacc) ** year

        cumulative_cash += free_cash_flow
        peak_burn = min(peak_burn, cumulative_cash)

        if first_positive_year is None and free_cash_flow > 0:
            first_positive_year = year

        current_revenue = next_revenue

    # Mature return on capital implied by the target margin and capital
    # intensity (after-tax margin x sales-to-capital), never below WACC.
    mature_return = max(
        target_margin * (1 - tax_rate) * sales_to_capital,
        wacc + TERMINAL_EXCESS_RETURN,
    )

    terminal_profit = (
        current_revenue * (1 + terminal_growth) * target_margin * (1 - tax_rate)
    )

    terminal_cash_flow = terminal_profit * (1 - terminal_growth / mature_return)

    terminal_value = terminal_cash_flow / (wacc - terminal_growth)

    present_terminal = terminal_value / (1 + wacc) ** years

    explicit_value = present_value

    present_value += present_terminal

    value = (present_value - (net_debt or 0.0)) / shares

    if not breakdown:
        return value

    return {
        "value": value,
        # If the explicit years burn cash (negative value), all of the
        # value - and more - comes from beyond the forecast: report 100%.
        "terminal_share": (
            1.0 if explicit_value <= 0
            else present_terminal / present_value if present_value > 0
            else None
        ),
        "explicit_years_burn_cash": explicit_value <= 0,
        "first_positive_fcf_year": first_positive_year,
        "peak_cash_burn": -peak_burn,
    }


def simulate_values(common, start_growth, peer_margins, wacc, seed=SIM_SEED):
    """
    Values across many plausible futures. Each draw combines:
      growth          uniform between half and all of current growth
      mature margin   a resampled profitable-peer margin +/- noise
      discount rate   base WACC +/- noise
      capital needs   sales-to-capital within a typical range
    Returns a numpy array of per-share values.
    """

    rng = np.random.default_rng(seed)

    margins = np.array(peer_margins) / 100

    values = np.empty(SIMULATIONS)

    floor = config.DCF_TERMINAL_GROWTH + 0.03

    for i in range(SIMULATIONS):

        values[i] = project_value(
            revenue=common["revenue"],
            start_growth=start_growth * rng.uniform(0.5, 1.0),
            start_margin=common["start_margin"],
            target_margin=max(rng.choice(margins) + rng.normal(0, MARGIN_NOISE), 0.0),
            wacc=max(wacc + rng.normal(0, WACC_NOISE), floor),
            net_debt=common["net_debt"],
            shares=common["shares"],
            sales_to_capital=rng.uniform(*SALES_TO_CAPITAL_RANGE),
        )

    return values


def peer_margin_distribution(peer_data):
    """
    25th / 50th / 75th percentile operating margin of PROFITABLE peers (%).
    Loss-making peers (other start-ups) say nothing about the margin a
    company earns once mature, so they are excluded.
    """

    if peer_data is None or peer_data.empty or "Operating_Margin" not in peer_data:
        return None

    margins = peer_data["Operating_Margin"].dropna()

    margins = margins[margins > 0]

    if len(margins) < 3:
        return None

    return {
        "low": float(margins.quantile(0.25)),
        "median": float(margins.median()),
        "high": float(margins.quantile(0.75)),
        "count": int(len(margins)),
        "values": margins.tolist(),
    }


def implied_target_margin(price, solve_inputs, tolerance=1e-4):
    """Mature margin at which the model value equals the price."""

    low, high = MARGIN_SEARCH

    def value(margin):
        return project_value(target_margin=margin, **solve_inputs)

    if value(high) < price:
        return None, "above"

    if value(low) > price:
        return None, "below"

    while high - low > tolerance:
        middle = (low + high) / 2
        if value(middle) < price:
            low = middle
        else:
            high = middle

    return (low + high) / 2, "solved"


def growth_stage_valuation(
    revenue,
    revenue_growth_pct,
    operating_margin_pct,
    net_debt,
    shares,
    raw_beta,
    market_cap,
    total_debt,
    peer_data,
    price,
    basis_label=None,
    risk_premium=0.0,
):

    if not is_positive(revenue) or not is_positive(shares):
        return {"available": False, "reason": "Revenue or share count unavailable."}

    if not is_valid(revenue_growth_pct):
        return {"available": False, "reason": "Revenue growth unavailable."}

    if not is_valid(operating_margin_pct):
        return {"available": False, "reason": "Current operating margin unavailable."}

    margins = peer_margin_distribution(peer_data)

    if margins is None:
        return {
            "available": False,
            "reason": "Too few peers with operating margins to set a mature target.",
        }

    wacc = estimate_wacc(raw_beta, market_cap, total_debt, risk_premium)["wacc"]

    start_growth = min(max(revenue_growth_pct / 100, 0.0), MAX_START_GROWTH)

    common = {
        "revenue": revenue,
        "start_margin": operating_margin_pct / 100,
        "wacc": wacc,
        "net_debt": net_debt,
        "shares": shares,
    }

    cases = {
        # Bear: growth halves and margins only reach a weak peer's level.
        "bear": {"start_growth": start_growth / 2, "target_margin": margins["low"] / 100},
        "base": {"start_growth": start_growth, "target_margin": margins["median"] / 100},
        "bull": {"start_growth": start_growth, "target_margin": margins["high"] / 100},
    }

    values = {
        name: project_value(**common, **case)
        for name, case in cases.items()
    }

    base_detail = project_value(**common, **cases["base"], breakdown=True)

    simulated = simulate_values(common, start_growth, margins["values"], wacc)

    p10, p50, p90 = np.percentile(simulated, [10, 50, 90])

    share_justifying_price = float(np.mean(simulated >= price))

    # Funding: can existing net cash carry the company to positive cash flow?
    net_cash = -(net_debt or 0.0)
    gap = base_detail["peak_cash_burn"] - max(net_cash, 0.0)
    market_cap_now = price * shares

    funding = {
        "peak_cash_burn": base_detail["peak_cash_burn"],
        "net_cash": net_cash,
        "first_positive_fcf_year": base_detail["first_positive_fcf_year"],
        "funding_gap": max(gap, 0.0),
        "gap_share_of_market_cap": (
            max(gap, 0.0) / market_cap_now if market_cap_now > 0 else None
        ),
    }

    implied, status = implied_target_margin(
        price, {**common, "start_growth": start_growth}
    )

    implied_text = None

    if implied is not None:

        implied_pct = implied * 100

        share_of_peers_below = float(
            np.mean([m < implied_pct for m in margins["values"]])
        )

        implied_text = (
            f"The price requires a mature operating margin of about "
            f"{implied_pct:.0f}% (with revenue growth starting at "
            f"{start_growth * 100:.0f}% and fading over {YEARS} years). "
            f"Peers earn {margins['low']:.0f}-{margins['high']:.0f}% "
            f"(median {margins['median']:.0f}%); "
            f"{share_of_peers_below * 100:.0f}% of peers earn less than that."
        )

    elif status == "above":
        implied_text = (
            "Even a 60% mature margin does not justify the price under "
            "these growth assumptions."
        )

    simulation = {
        "runs": SIMULATIONS,
        "p10": float(p10),
        "p50": float(p50),
        "p90": float(p90),
        "share_justifying_price": share_justifying_price,
    }

    if values["base"] <= 0:
        return {
            "available": False,
            "reason": "Projected equity value is not positive under base assumptions.",
            "implied_margin_summary": implied_text,
            "implied_margin": None if implied is None else implied * 100,
            "assumptions": {
                "peer_margins": {k: margins[k] for k in ("low", "median", "high", "count")},
            },
            "simulation": simulation,
            "funding": funding,
        }

    return {
        "available": True,
        "base": values["base"],
        # Range = 10th-90th percentile of plausible futures, not two
        # hand-picked extremes.
        "low": max(float(p10), 0.0),
        "high": float(p90),
        "simulation": simulation,
        "funding": funding,
        "terminal_share": base_detail["terminal_share"],
        "explicit_years_burn_cash": base_detail["explicit_years_burn_cash"],
        "cases": {
            name: {
                "start_growth": case["start_growth"],
                "target_margin": case["target_margin"],
                "value": values[name],
            }
            for name, case in cases.items()
        },
        "assumptions": {
            "start_growth": start_growth,
            "current_margin": operating_margin_pct / 100,
            "peer_margins": {k: margins[k] for k in ("low", "median", "high", "count")},
            "wacc": wacc,
            "years": YEARS,
            "sales_to_capital": SALES_TO_CAPITAL,
            "basis": basis_label,
        },
        "implied_margin": None if implied is None else implied * 100,
        "implied_margin_summary": implied_text,
        "peer_count": margins["count"],
        "range_basis": (
            f"10th-90th percentile of {SIMULATIONS:,} simulated futures "
            "(growth, peer-based mature margin, discount rate, capital needs)"
        ),
    }


def growth_valuation_confidence(analysis):
    """
    How much to trust a growth-stage (pre-profit) fair value, separate
    from the overall data-confidence score. Returns None when the
    growth-stage model was not used.
    """

    result = analysis["method_results"].get("growth_dcf", {})

    if not result or "assumptions" not in result:
        return None

    reasons = []

    profile = analysis["company_profile"]
    peers = result["assumptions"].get("peer_margins") or {}

    current = result["assumptions"].get("current_margin")

    if current is not None and current < 0:
        reasons.append("Currently loss-making at the operating level")

    if not profile.get("positive_fcf"):
        reasons.append("Free cash flow is negative")

    terminal = result.get("terminal_share")

    if result.get("explicit_years_burn_cash"):
        reasons.append(
            "All of the value comes from beyond year 10: the next 10 years "
            "consume cash"
        )
    elif terminal and terminal > 0.70:
        reasons.append(
            f"{terminal * 100:.0f}% of the value comes from beyond year 10 "
            "(terminal value)"
        )

    implied = result.get("implied_margin")

    if implied is not None and peers and implied > peers.get("high", 0):
        reasons.append(
            f"The price-implied mature margin ({implied:.0f}%) is above the "
            f"peer range ({peers['low']:.0f}-{peers['high']:.0f}%)"
        )

    simulation = result.get("simulation") or {}

    if simulation.get("p10") and simulation.get("p90"):
        if simulation["p10"] <= 0 or simulation["p90"] / simulation["p10"] > 4:
            reasons.append(
                "Plausible futures span a very wide range of values "
                "(10th-90th percentile more than 4x apart)"
            )

    ev_sales = analysis["method_results"].get("peer_evs", {})

    if (
        ev_sales.get("available")
        and ev_sales.get("multiple_low")
        and ev_sales["multiple_high"] / ev_sales["multiple_low"] > 2
    ):
        reasons.append("Peer EV/Sales multiples are widely dispersed")

    funding = result.get("funding") or {}

    if funding.get("funding_gap"):
        reasons.append(
            "Likely needs new funding before turning cash-positive "
            "(dilution risk)"
        )

    if profile.get("annual_years", 0) < 3:
        reasons.append("Short financial history")

    level = "LOW" if len(reasons) >= 4 else "MEDIUM" if len(reasons) >= 2 else "HIGH"

    return {"level": level, "reasons": reasons}
