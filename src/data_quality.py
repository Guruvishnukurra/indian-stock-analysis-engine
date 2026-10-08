import pandas as pd


def latest_snapshot(data):
    """
    Latest available value of every column (a missing latest
    value falls back to the most recent earlier one).
    Returns an empty Series for missing/empty data.
    """

    if data is None or data.empty:
        return pd.Series(dtype="float64")

    return data.ffill().iloc[-1]


def calculate_metric_coverage(row, metrics):

    available = []
    missing = []

    for metric in metrics:

        if metric not in row.index:
            missing.append(metric)
            continue

        value = row[metric]

        if pd.notna(value):
            available.append(metric)
        else:
            missing.append(metric)

    total_metrics = len(metrics)

    if total_metrics == 0:
        coverage_ratio = 0.0
    else:
        coverage_ratio = (
            len(available) / total_metrics
        )

    return {
        "available_metrics": available,
        "missing_metrics": missing,
        "coverage_count": len(available),
        "total_metrics": total_metrics,
        "coverage_ratio": coverage_ratio
    }


def calculate_data_quality_score(
    fundamental_data,
    quarterly_data,
    required_annual_metrics=None,
    required_quarterly_metrics=None
):

    if required_annual_metrics is None:

        required_annual_metrics = [
            "Revenue",
            "Net_Income",
            "EPS",
            "Equity",
            "Assets"
        ]

    if required_quarterly_metrics is None:

        required_quarterly_metrics = [
            "Revenue",
            "Net_Income",
            "EPS"
        ]

    latest_annual = latest_snapshot(fundamental_data)
    latest_quarter = latest_snapshot(quarterly_data)

    annual_quality = calculate_metric_coverage(
        latest_annual,
        required_annual_metrics
    )

    quarterly_quality = calculate_metric_coverage(
        latest_quarter,
        required_quarterly_metrics
    )

    annual_score = (
        annual_quality["coverage_ratio"]
        * 100
    )

    quarterly_score = (
        quarterly_quality["coverage_ratio"]
        * 100
    )

    overall_score = (
        annual_score * 0.60
        +
        quarterly_score * 0.40
    )

    annual_years = (
        0
        if fundamental_data is None or fundamental_data.empty
        else int(fundamental_data["Net_Income"].notna().sum())
        if "Net_Income" in fundamental_data.columns
        else 0
    )

    quarters = (
        0
        if quarterly_data is None or quarterly_data.empty
        else len(quarterly_data)
    )

    return {
        "score": overall_score,
        "label": get_data_quality_label(overall_score),
        "annual_years": annual_years,
        "quarters": quarters,
        "annual": annual_quality,
        "quarterly": quarterly_quality
    }


def get_data_quality_label(score):

    if score >= 90:
        return "High"

    if score >= 75:
        return "Good"

    if score >= 50:
        return "Moderate"

    return "Low"

def _relative_gap(a, b):
    return abs(a - b) / max(abs(a), abs(b))


def check_data_consistency(info, fundamental_data, ttm=None):
    """
    Cross-check statement-derived figures against Yahoo's
    summary figures. Yahoo statements are occasionally wrong
    (e.g. after mergers); when the two sources disagree, flag it,
    prefer the summary value (it is consistent with the price
    multiples Yahoo reports), and let confidence fall.

    Returns {"issues": [...], "preferred": {...}}.
    """

    from src.utils import is_positive, latest_valid, safe_float

    issues = []
    preferred = {}
    notes = []

    info = info or {}

    # Shares issued after the latest balance sheet (IPO, QIP, ESOPs,
    # conversions): book value and net cash describe the older share
    # base. Informational unless large.
    statement_shares = latest_valid(fundamental_data, "Shares")
    current_shares = safe_float(info.get("sharesOutstanding"))

    if is_positive(statement_shares) and is_positive(current_shares):

        change = current_shares / statement_shares - 1

        if abs(change) > 0.03:
            text = (
                f"Share count changed {change * 100:+.1f}% since the latest "
                "balance sheet (issuance or buyback after the reporting date): "
                "book value and net cash may be out of date"
            )
            if abs(change) > 0.10:
                issues.append(text)
            else:
                notes.append(text)

    # ROE
    statement_roe = latest_valid(fundamental_data, "ROE")
    summary_roe = safe_float(info.get("returnOnEquity"))

    if summary_roe is not None:
        summary_roe *= 100

    if (
        is_positive(statement_roe)
        and is_positive(summary_roe)
        and _relative_gap(statement_roe, summary_roe) > 0.30
    ):
        issues.append(
            f"Statement ROE {statement_roe:.1f}% disagrees with "
            f"Yahoo summary ROE {summary_roe:.1f}%; using summary"
        )
        preferred["roe"] = summary_roe

    # Book value per share
    equity = latest_valid(fundamental_data, "Equity")
    shares = safe_float(info.get("sharesOutstanding"))
    summary_bvps = safe_float(info.get("bookValue"))

    if is_positive(equity) and is_positive(shares) and is_positive(summary_bvps):

        statement_bvps = equity / shares

        if _relative_gap(statement_bvps, summary_bvps) > 0.25:
            issues.append(
                f"Statement book value/share {statement_bvps:,.0f} disagrees "
                f"with Yahoo summary {summary_bvps:,.0f}; using summary"
            )

    # Summary (Yahoo's own TTM) vs statements summed over the same TTM.
    if ttm and ttm.get("available"):

        for label, summary_key, ttm_key, tolerance in (
            ("revenue", "totalRevenue", "Revenue", 0.10),
            ("net profit", "netIncomeToCommon", "Net_Income", 0.15),
        ):
            summary_value = safe_float(info.get(summary_key))
            statement_value = ttm.get(ttm_key)

            if (
                is_positive(summary_value)
                and is_positive(statement_value)
                and _relative_gap(summary_value, statement_value) > tolerance
            ):
                issues.append(
                    f"Trailing {label} differs between Yahoo summary "
                    f"({summary_value / 1e7:,.0f} cr) and quarterly statements "
                    f"({statement_value / 1e7:,.0f} cr, {ttm['label']})"
                )

    # Reporting currency must match the trading currency.
    financial_ccy = info.get("financialCurrency")
    trading_ccy = info.get("currency")

    if financial_ccy and trading_ccy and financial_ccy != trading_ccy:
        issues.append(
            f"Financials are reported in {financial_ccy} but the stock "
            f"trades in {trading_ccy}; per-share values may be misstated"
        )

    return {"issues": issues, "preferred": preferred, "notes": notes}
