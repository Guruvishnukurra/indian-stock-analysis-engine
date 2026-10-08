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

Assumptions that matter and are NOT modelled: probability of failure,
future dilution, tax-loss carry-forwards. Results are a range with
explicit assumptions, never a precise value.
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
):
    """Equity value per share under one set of assumptions."""

    present_value = 0.0

    current_revenue = revenue

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

        present_value += (after_tax - reinvestment) / (1 + wacc) ** year

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

    present_value += terminal_value / (1 + wacc) ** years

    return (present_value - (net_debt or 0.0)) / shares


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

    if values["base"] <= 0:
        return {
            "available": False,
            "reason": "Projected equity value is not positive under base assumptions.",
            "implied_margin_summary": implied_text,
        }

    return {
        "available": True,
        "base": values["base"],
        "low": max(min(values.values()), 0.0),
        "high": max(values.values()),
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
            "bear/base/bull mature margins = peer 25th/median/75th percentile; "
            "bear also halves growth"
        ),
    }
