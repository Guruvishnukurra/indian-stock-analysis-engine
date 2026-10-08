import numpy as np
import pandas as pd

from src.fundamentals import get_statement_value
from src.utils import safe_growth


QUARTERLY_COLUMNS = [
    "Revenue",
    "Operating_Income",
    "Net_Interest_Income",
    "Net_Income",
    "Normalized_Income",
    "Unusual_Items",
    "EPS",
    "Net_Margin",
    "Operating_Margin",
    "Revenue_YoY",
    "Net_Profit_YoY",
    "EPS_YoY",
]


def build_quarterly_fundamentals(
    stock=None,
    income_stmt=None
):
    """
    Build quarterly fundamentals.

    Pass either a yfinance Ticker (`stock`) or an already
    fetched quarterly income statement (`income_stmt`).
    Always returns a DataFrame (possibly empty) with the
    standard columns, never raises on missing data.
    """

    if income_stmt is None and stock is not None:
        try:
            income_stmt = stock.quarterly_income_stmt
        except Exception:
            income_stmt = None

    if income_stmt is None or income_stmt.empty:
        return pd.DataFrame(columns=QUARTERLY_COLUMNS, dtype="float64")

    data = pd.DataFrame(
        index=pd.DatetimeIndex(income_stmt.columns)
    )

    data["Revenue"] = get_statement_value(
        income_stmt,
        [
            "Total Revenue",
            "Operating Revenue"
        ]
    )

    data["Operating_Income"] = get_statement_value(
        income_stmt,
        [
            "Operating Income"
        ]
    )

    # Banking metric
    data["Net_Interest_Income"] = get_statement_value(
        income_stmt,
        [
            "Net Interest Income"
        ]
    )

    data["Net_Income"] = get_statement_value(
        income_stmt,
        [
            "Net Income",
            "Net Income Common Stockholders"
        ]
    )

    data["EPS"] = get_statement_value(
        income_stmt,
        [
            "Diluted EPS",
            "Basic EPS"
        ]
    )

    # One-off items (pre-tax) and profit excluding them, as reported
    # by the data source.
    data["Normalized_Income"] = get_statement_value(
        income_stmt,
        [
            "Normalized Income"
        ]
    )

    data["Unusual_Items"] = get_statement_value(
        income_stmt,
        [
            "Total Unusual Items",
            "Total Unusual Items Excluding Goodwill"
        ]
    )

    positive_revenue = data["Revenue"].where(data["Revenue"] > 0)

    data["Net_Margin"] = (
        data["Net_Income"]
        / positive_revenue
        * 100
    )

    data["Operating_Margin"] = (
        data["Operating_Income"]
        / positive_revenue
        * 100
    )

    data = data.sort_index()

    data = data.dropna(
        how="all",
        subset=["Revenue", "Net_Income", "EPS"]
    )

    data = add_yoy_growth(data)

    return data.replace([np.inf, -np.inf], np.nan)


def _find_year_ago(index, current_date, tolerance_days=20):
    """
    Find the quarter one year earlier, allowing for small
    differences in period-end dates.
    """

    target = current_date - pd.DateOffset(years=1)

    differences = abs(index - target)

    if len(differences) == 0:
        return None

    position = differences.argmin()

    if differences[position] > pd.Timedelta(days=tolerance_days):
        return None

    return index[position]


def add_yoy_growth(data):

    data = data.copy()

    growth_columns = {
        "Revenue_YoY": "Revenue",
        "Net_Profit_YoY": "Net_Income",
        "EPS_YoY": "EPS",
    }

    for column in growth_columns:
        data[column] = np.nan

    for current_date in data.index:

        previous_date = _find_year_ago(
            data.index,
            current_date
        )

        if previous_date is None:
            continue

        for growth_column, source in growth_columns.items():

            # Growth is undefined from a zero or negative base.
            growth = safe_growth(
                data.loc[current_date, source],
                data.loc[previous_date, source]
            )

            if growth is not None:
                data.loc[current_date, growth_column] = growth

    return data
