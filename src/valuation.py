"""
Valuation methods.

Every method returns either a result dict with an explicit
low / base / high, or None plus a reason. No method invents a
value when its inputs are missing or meaningless.
"""

import numpy as np
import pandas as pd

from src import config
from src.utils import is_positive, is_valid, latest_valid, valid_values


# =========================================================
# DCF BUILDING BLOCK
# =========================================================

def calculate_dcf(
    free_cash_flow,
    shares_outstanding,
    growth_rate=0.08,
    terminal_growth=0.04,
    wacc=0.10,
    forecast_years=5,
    net_cash=0.0,
    fade_years=0
):
    """
    Per-share equity value from a two-stage FCF DCF.

    Stage 1: `forecast_years` at `growth_rate`.
    Stage 2: `fade_years` with growth fading linearly to
             `terminal_growth` (0 = no fade stage).
    Terminal: Gordon growth.

    Equity value = enterprise value + net cash.
    """

    if not is_positive(free_cash_flow) or not is_positive(shares_outstanding):
        return None

    if not is_valid(wacc) or wacc <= terminal_growth:
        return None

    net_cash = net_cash if is_valid(net_cash) else 0.0

    growth_path = [growth_rate] * forecast_years

    for step in range(1, fade_years + 1):
        growth_path.append(
            growth_rate
            + (terminal_growth - growth_rate) * step / (fade_years + 1)
        )

    fcf = free_cash_flow
    present_value = 0.0

    for year, growth in enumerate(growth_path, start=1):
        fcf = fcf * (1 + growth)
        present_value += fcf / ((1 + wacc) ** year)

    years = len(growth_path)

    terminal_value = (
        fcf * (1 + terminal_growth)
        / (wacc - terminal_growth)
    )

    present_terminal_value = terminal_value / ((1 + wacc) ** years)

    enterprise_value = present_value + present_terminal_value

    equity_value = enterprise_value + net_cash

    if equity_value <= 0:
        return None

    return equity_value / shares_outstanding


def _unavailable(reason):
    return {"available": False, "reason": reason}


# =========================================================
# DISCOUNT RATE
# =========================================================

def adjust_beta(raw_beta):
    """
    Blume adjustment (2/3 raw + 1/3 market) and bounds.
    Missing beta defaults to 1.0 (market risk), flagged.
    """

    if not is_valid(raw_beta):
        return 1.0, "Beta unavailable; market beta of 1.0 assumed."

    adjusted = 0.67 * raw_beta + 0.33

    low, high = config.BETA_BOUNDS

    bounded = min(max(adjusted, low), high)

    note = f"Raw beta {raw_beta:.2f}, adjusted {bounded:.2f}."

    return bounded, note


def estimate_cost_of_equity(raw_beta):

    beta, note = adjust_beta(raw_beta)

    cost = config.RISK_FREE_RATE + beta * config.EQUITY_RISK_PREMIUM

    return cost, beta, note


def estimate_wacc(raw_beta, market_cap, total_debt):
    """
    Market-value-weighted cost of capital.
    With no debt data, WACC equals cost of equity.
    """

    cost_of_equity, beta, note = estimate_cost_of_equity(raw_beta)

    after_tax_cost_of_debt = (
        (config.RISK_FREE_RATE + config.DEBT_SPREAD)
        * (1 - config.TAX_RATE)
    )

    if is_positive(market_cap) and is_positive(total_debt):
        debt_weight = total_debt / (market_cap + total_debt)
    else:
        debt_weight = 0.0

    wacc = (
        (1 - debt_weight) * cost_of_equity
        + debt_weight * after_tax_cost_of_debt
    )

    # Keep a minimum gap over terminal growth: a WACC close to
    # terminal growth makes the terminal value explode.
    wacc = max(wacc, config.DCF_TERMINAL_GROWTH + 0.03)

    return {
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "beta": beta,
        "debt_weight": debt_weight,
        "note": note,
    }


# =========================================================
# DCF
# =========================================================

def estimate_dcf_growth(fundamental_data):
    """
    Base growth = historical revenue CAGR, bounded.
    Revenue is used rather than FCF because FCF is too
    volatile year to year to extrapolate.
    """

    revenue = valid_values(fundamental_data, "Revenue", last_n=4)

    low, high = config.DCF_GROWTH_BOUNDS

    if len(revenue) >= 2 and revenue[0] > 0 and revenue[-1] > 0:

        years = len(revenue) - 1

        cagr = (revenue[-1] / revenue[0]) ** (1 / years) - 1

        bounded = min(max(cagr, low), high)

        basis = f"{years}-year revenue CAGR of {cagr * 100:.1f}%"

        if bounded != cagr:
            basis += f", bounded to {bounded * 100:.1f}%"

        return bounded, basis, True

    return (
        config.DCF_DEFAULT_GROWTH,
        "Default assumption (insufficient revenue history)",
        False,
    )


def run_dcf(
    fundamental_data,
    shares_outstanding,
    raw_beta,
    market_cap,
    normalized_fcf
):
    """
    DCF with sensitivity analysis.

    Range = one-step shocks to a single assumption
    (growth +/- step, or WACC +/- step), i.e. "what if one
    key assumption is wrong by one notch".
    The full 3x3 grid is returned for display.
    """

    if not is_positive(normalized_fcf):
        return _unavailable("Normalised free cash flow is negative or missing.")

    if not is_positive(shares_outstanding):
        return _unavailable("Shares outstanding unavailable.")

    debt = latest_valid(fundamental_data, "Debt") or 0.0
    cash = latest_valid(fundamental_data, "Cash_And_Investments") or 0.0

    net_cash = cash - debt

    capital = estimate_wacc(raw_beta, market_cap, debt)
    wacc = capital["wacc"]

    growth, growth_basis, growth_from_data = estimate_dcf_growth(
        fundamental_data
    )

    def value(g, r):
        return calculate_dcf(
            free_cash_flow=normalized_fcf,
            shares_outstanding=shares_outstanding,
            growth_rate=g,
            terminal_growth=config.DCF_TERMINAL_GROWTH,
            wacc=r,
            forecast_years=config.DCF_HIGH_GROWTH_YEARS,
            net_cash=net_cash,
            fade_years=config.DCF_FADE_YEARS,
        )

    base = value(growth, wacc)

    if base is None:
        return _unavailable("DCF produced a non-positive equity value.")

    g_step = config.DCF_GROWTH_STEP
    r_step = config.DCF_WACC_STEP

    growth_cases = [growth - g_step, growth, growth + g_step]
    wacc_cases = [wacc - r_step, wacc, wacc + r_step]

    grid = pd.DataFrame(
        [[value(g, r) for r in wacc_cases] for g in growth_cases],
        index=[f"g={g * 100:.0f}%" for g in growth_cases],
        columns=[f"WACC={r * 100:.1f}%" for r in wacc_cases],
    )

    one_step = [
        v for v in (
            value(growth - g_step, wacc),
            value(growth + g_step, wacc),
            value(growth, wacc + r_step),
            value(growth, wacc - r_step),
        )
        if v is not None
    ]

    return {
        "available": True,
        "base": base,
        "low": min(one_step + [base]),
        "high": max(one_step + [base]),
        "sensitivity": grid,
        "assumptions": {
            "normalized_fcf": normalized_fcf,
            "growth": growth,
            "growth_basis": growth_basis,
            "growth_from_data": growth_from_data,
            "terminal_growth": config.DCF_TERMINAL_GROWTH,
            "wacc": wacc,
            "cost_of_equity": capital["cost_of_equity"],
            "beta": capital["beta"],
            "beta_note": capital["note"],
            "net_cash": net_cash,
        },
        "range_basis": (
            f"growth +/-{g_step * 100:.0f}pp or "
            f"WACC +/-{r_step * 100:.0f}pp"
        ),
    }


# =========================================================
# PEER MULTIPLES
# =========================================================

def peer_multiple_valuation(per_share_metric, summary, metric_name):
    """
    Value = per-share metric x peer multiple.
    Range = peer interquartile (or min-max) multiples.
    """

    if summary is None:
        return _unavailable(f"No valid peer {metric_name} multiples.")

    if not is_positive(per_share_metric):
        return _unavailable(f"Company {metric_name} base is not positive.")

    return {
        "available": True,
        "base": per_share_metric * summary["median"],
        "low": per_share_metric * summary["low"],
        "high": per_share_metric * summary["high"],
        "multiple_median": summary["median"],
        "multiple_low": summary["low"],
        "multiple_high": summary["high"],
        "peer_count": summary["count"],
        "range_basis": f"peer {metric_name} {summary['spread_basis']}",
    }


def roe_adjusted_pb_valuation(
    book_value_per_share,
    company_roe,
    pb_peers,
    summary
):
    """
    Peer P/B adjusted for profitability.

    Price-to-book rises with return on equity: a bank earning
    18% ROE deserves a higher P/B than one earning 10%.
    The fair P/B is the peer median "P/B per unit of ROE"
    applied to the company's ROE, with the adjustment bounded.
    Falls back to plain peer P/B if ROE data is missing.
    """

    result = peer_multiple_valuation(
        book_value_per_share, summary, "P/B"
    )

    if not result["available"]:
        return result

    if (
        pb_peers is None
        or pb_peers.empty
        or not is_positive(company_roe)
    ):
        result["roe_adjusted"] = False
        result["range_basis"] += " (not ROE-adjusted: ROE data missing)"
        return result

    peers = pb_peers.dropna(subset=["PB", "ROE"])
    peers = peers[(peers["PB"] > 0) & (peers["ROE"] > 0)]

    if len(peers) < 3:
        result["roe_adjusted"] = False
        result["range_basis"] += " (not ROE-adjusted: too few peers with ROE)"
        return result

    peer_roe_median = peers["ROE"].median() * 100

    factor = company_roe / peer_roe_median

    low_bound, high_bound = config.ROE_ADJUSTMENT_BOUNDS

    factor = min(max(factor, low_bound), high_bound)

    for key in ("base", "low", "high", "multiple_median",
                "multiple_low", "multiple_high"):
        result[key] = result[key] * factor

    result["roe_adjusted"] = True
    result["roe_factor"] = factor
    result["company_roe"] = company_roe
    result["peer_median_roe"] = peer_roe_median
    result["range_basis"] += (
        f", ROE-adjusted x{factor:.2f} "
        f"(ROE {company_roe:.1f}% vs peer median {peer_roe_median:.1f}%)"
    )

    return result


# =========================================================
# HISTORICAL P/E
# =========================================================

def remove_dividend_adjustment(price_data):
    """
    Yahoo's adjusted close is reduced for every past dividend,
    which would understate historical P/E. Undo the dividend
    adjustment (split adjustment is kept).
    """

    close = price_data["Close"]

    if "Dividends" not in price_data.columns:
        return close

    dividends = price_data["Dividends"].fillna(0)

    previous_close = close.shift(1)

    factor = (1 - dividends / previous_close).where(dividends > 0, 1.0)

    factor = factor.fillna(1.0).clip(lower=0.5, upper=1.0)

    # Each ex-dividend factor applies to all earlier dates.
    cumulative = factor[::-1].cumprod()[::-1].shift(-1).fillna(1.0)

    return close / cumulative


def _eps_consistency_problem(fundamental_data, trailing_eps):
    """
    Detect split/bonus distortions. Statement EPS may not be
    restated for splits while prices are; comparing EPS growth
    with net-income growth exposes this.
    """

    data = fundamental_data[["EPS", "Net_Income"]].dropna()

    data = data[(data["EPS"] > 0) & (data["Net_Income"] > 0)]

    if len(data) >= 2:

        eps_ratio = data["EPS"] / data["EPS"].shift(1)
        income_ratio = data["Net_Income"] / data["Net_Income"].shift(1)

        mismatch = (eps_ratio / income_ratio - 1).abs().dropna()

        if (mismatch > 0.25).any():
            return (
                "EPS and net income moved inconsistently "
                "(possible split/bonus not restated)."
            )

    latest_eps = latest_valid(fundamental_data, "EPS")

    if is_positive(trailing_eps) and is_positive(latest_eps):

        ratio = trailing_eps / latest_eps

        if ratio < 0.6 or ratio > 1.7:
            return (
                "Latest annual EPS is inconsistent with trailing EPS "
                "(possible split/bonus)."
            )

    return None


def historical_pe_valuation(price_data, fundamental_data, trailing_eps):
    """
    The company's own P/E history, from daily prices divided by
    the most recent *published* annual EPS (fiscal year-end plus
    a reporting lag, so no look-ahead).

    Approximate: annual EPS is a step function, not true TTM.
    Kept at low weight.
    """

    if not is_positive(trailing_eps):
        return _unavailable("Trailing EPS is not positive.")

    if price_data is None or price_data.empty:
        return _unavailable("No price history.")

    if fundamental_data is None or fundamental_data.empty:
        return _unavailable("No annual EPS history.")

    problem = _eps_consistency_problem(fundamental_data, trailing_eps)

    if problem:
        return _unavailable(problem)

    eps = fundamental_data["EPS"].dropna()
    eps = eps[eps > 0]

    if len(eps) < config.MIN_HISTORICAL_PE_YEARS:
        return _unavailable(
            f"Fewer than {config.MIN_HISTORICAL_PE_YEARS} years "
            "of positive annual EPS."
        )

    close = remove_dividend_adjustment(price_data)

    close.index = pd.DatetimeIndex(close.index)

    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)

    available_from = (
        pd.DatetimeIndex(eps.index)
        + pd.Timedelta(days=config.REPORTING_LAG_DAYS)
    )

    eps_known = pd.Series(eps.values, index=available_from).sort_index()

    eps_on_date = eps_known.reindex(
        close.index.union(eps_known.index)
    ).ffill().reindex(close.index)

    pe = (close / eps_on_date).dropna()

    pe = pe[np.isfinite(pe) & (pe > 0)]

    years_used = eps_on_date.dropna().nunique()

    if pe.empty or years_used < config.MIN_HISTORICAL_PE_YEARS:
        return _unavailable(
            "Not enough overlapping price and EPS history."
        )

    median_pe = pe.median()
    low_pe = pe.quantile(0.25)
    high_pe = pe.quantile(0.75)

    return {
        "available": True,
        "base": trailing_eps * median_pe,
        "low": trailing_eps * low_pe,
        "high": trailing_eps * high_pe,
        "multiple_median": median_pe,
        "multiple_low": low_pe,
        "multiple_high": high_pe,
        "years_used": int(years_used),
        "range_basis": (
            f"interquartile own P/E over {len(pe)} trading days "
            f"({int(years_used)} fiscal years of EPS)"
        ),
    }


# =========================================================
# EV / SALES (loss-making or barely profitable companies)
# =========================================================

def ev_sales_valuation(revenue, net_debt, shares, summary):
    """
    Equity value per share from peer EV/Sales:

        (peer EV/Sales x company revenue - net debt) / shares

    Unlike P/S, this accounts for debt: a heavily indebted company
    is worth far less per share than its sales alone suggest.
    """

    if summary is None:
        return _unavailable("No valid peer EV/Sales multiples.")

    if not is_positive(revenue) or not is_positive(shares):
        return _unavailable("Revenue or share count unavailable.")

    net_debt = net_debt if is_valid(net_debt) else 0.0

    def per_share(multiple):
        return (multiple * revenue - net_debt) / shares

    base = per_share(summary["median"])

    if base <= 0:
        return _unavailable(
            "Net debt exceeds the enterprise value implied by peer "
            "EV/Sales: no positive equity value."
        )

    return {
        "available": True,
        "base": base,
        "low": max(per_share(summary["low"]), 0.0),
        "high": per_share(summary["high"]),
        "multiple_median": summary["median"],
        "multiple_low": summary["low"],
        "multiple_high": summary["high"],
        "peer_count": summary["count"],
        "net_debt": net_debt,
        "range_basis": (
            f"peer EV/Sales {summary['spread_basis']}, less net debt"
        ),
    }
