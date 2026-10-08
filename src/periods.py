"""
Period hygiene.

Every figure the engine reports carries the period it describes, and
figures from different periods are never combined in one ratio.

Trailing-twelve-month (TTM) values are built ONLY from four
consecutive quarters. Data sources sometimes omit a quarter; summing
"the last four available" would then silently span 15 months.
"""

import pandas as pd

from src.utils import is_positive, is_valid


QUARTER_GAP_DAYS = (80, 100)

TTM_FIELDS = [
    "Revenue",
    "Operating_Income",
    "Net_Income",
    "Normalized_Income",
    "Unusual_Items",
]


def fy_label(date):
    """Indian fiscal-year label for a year-end date (Mar-2026 -> FY2026)."""
    date = pd.Timestamp(date)
    return f"FY{date.year if date.month <= 3 else date.year + 1}"


def quarter_label(date):
    return f"quarter ended {pd.Timestamp(date):%d %b %Y}"


def consecutive_quarters(quarterly_data, count=4):
    """
    The latest `count` quarters if they are consecutive, else None.
    """

    if quarterly_data is None or quarterly_data.empty:
        return None

    data = quarterly_data.dropna(how="all", subset=["Revenue"]).sort_index()

    if len(data) < count:
        return None

    latest = data.iloc[-count:]

    gaps = pd.Series(latest.index).diff().dropna().dt.days

    low, high = QUARTER_GAP_DAYS

    if not gaps.between(low, high).all():
        return None

    return latest


def build_ttm(quarterly_data):
    """
    TTM sums from four consecutive quarters.

    Returns {"available": bool, "label": "TTM to 30 Jun 2026",
             field: value, ..., "reason": ...}
    """

    latest = consecutive_quarters(quarterly_data)

    if latest is None:
        return {
            "available": False,
            "reason": (
                "Fewer than four consecutive quarters available "
                "(a quarter is missing or history is short)."
            ),
        }

    result = {
        "available": True,
        "label": f"TTM to {latest.index[-1]:%d %b %Y}",
        "end": latest.index[-1],
    }

    for field in TTM_FIELDS:

        if field not in latest.columns:
            result[field] = None
            continue

        values = pd.to_numeric(latest[field], errors="coerce")

        # One-off items are often blank when zero; other fields must be
        # complete or the TTM value is not defined.
        if field == "Unusual_Items":
            result[field] = float(values.fillna(0).sum())
        elif values.notna().all():
            result[field] = float(values.sum())
        else:
            result[field] = None

    revenue = result.get("Revenue")

    for name, field in (
        ("Operating_Margin", "Operating_Income"),
        ("Net_Margin", "Net_Income"),
    ):
        value = result.get(field)
        result[name] = (
            value / revenue * 100
            if is_valid(value) and is_positive(revenue)
            else None
        )

    return result


def normalized_eps(trailing_eps, quarterly_data, shares):
    """
    Trailing EPS with one-off items removed.

    The data source's trailing EPS already covers exactly the last 12
    months. One-offs are taken from the quarters dated within that same
    window (after-tax: normalized income - net income), so no periods are
    mixed even if a quarter is missing from the statements.

    Returns (eps, note). eps is unchanged when one-offs are immaterial.
    """

    if (
        not is_valid(trailing_eps)
        or not is_positive(shares)
        or quarterly_data is None
        or quarterly_data.empty
        or "Normalized_Income" not in quarterly_data.columns
    ):
        return trailing_eps, None

    data = quarterly_data.sort_index()

    latest = data.index.max()

    window = data[data.index > latest - pd.Timedelta(days=365)]

    addback = (
        pd.to_numeric(window["Normalized_Income"], errors="coerce")
        - pd.to_numeric(window["Net_Income"], errors="coerce")
    ).fillna(0.0).sum()

    trailing_profit = trailing_eps * shares

    if not trailing_profit or abs(addback) < 0.05 * abs(trailing_profit):
        return trailing_eps, None

    pre_tax = pd.to_numeric(window.get("Unusual_Items"), errors="coerce").fillna(0).sum()

    # The after-tax add-back must be explained by reported one-off items
    # (it cannot exceed them, allowing 10% for rounding); otherwise the
    # "normalized" figure reflects something else and is not used.
    if abs(addback) > abs(pre_tax) * 1.1:
        return trailing_eps, (
            "Data source's normalized profit differs from reported profit "
            "without matching one-off items; earnings were not adjusted."
        )

    adjusted = trailing_eps + addback / shares

    kind = "charges" if addback > 0 else "gains"

    note = (
        f"One-off {kind} of about {abs(pre_tax) / 1e7:,.0f} crore (pre-tax) in the "
        f"last 12 months excluded from earnings: EPS {trailing_eps:.2f} -> "
        f"{adjusted:.2f}."
    )

    if len(window) < 4:
        note += (
            f" Only {len(window)} of the last 4 quarters are in the data, "
            "so one-offs in the missing quarter are unknown."
        )

    return adjusted, note
