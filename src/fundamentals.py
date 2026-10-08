import numpy as np
import pandas as pd


def get_statement_value(statement, possible_names):
    """
    Return the first available financial-statement line item.

    This allows the engine to handle companies whose Yahoo Finance
    statements use different accounting labels.
    """

    if statement is None or statement.empty:
        return pd.Series(dtype="float64")

    for name in possible_names:

        if name in statement.index:
            return pd.to_numeric(
                statement.loc[name],
                errors="coerce"
            )

    return pd.Series(
        index=statement.columns,
        dtype="float64"
    )


def build_fundamental_data(
    income_stmt,
    balance_sheet,
    cash_flow
):

    # Use every reporting date found in any statement, so an
    # empty income statement does not discard balance-sheet data.
    dates = set()

    for statement in (income_stmt, balance_sheet, cash_flow):
        if statement is not None and not statement.empty:
            dates.update(statement.columns)

    fundamental_data = pd.DataFrame(
        index=pd.DatetimeIndex(sorted(dates))
    )

    # -------------------------
    # Income statement
    # -------------------------

    fundamental_data["Revenue"] = get_statement_value(
        income_stmt,
        [
            "Total Revenue",
            "Operating Revenue"
        ]
    )

    fundamental_data["Operating_Income"] = get_statement_value(
        income_stmt,
        [
            "Operating Income"
        ]
    )

    fundamental_data["Net_Interest_Income"] = get_statement_value(
        income_stmt,
        [
            "Net Interest Income"
        ]
    )

    fundamental_data["Interest_Income"] = get_statement_value(
        income_stmt,
        [
            "Interest Income"
        ]
    )

    fundamental_data["Net_Income"] = get_statement_value(
        income_stmt,
        [
            "Net Income",
            "Net Income Common Stockholders"
        ]
    )

    fundamental_data["Normalized_Income"] = get_statement_value(
        income_stmt,
        [
            "Normalized Income"
        ]
    )

    fundamental_data["EBITDA"] = get_statement_value(
        income_stmt,
        [
            "EBITDA"
        ]
    )

    fundamental_data["EPS"] = get_statement_value(
        income_stmt,
        [
            "Diluted EPS",
            "Basic EPS"
        ]
    )

    # -------------------------
    # Balance sheet
    # -------------------------

    fundamental_data["Debt"] = get_statement_value(
        balance_sheet,
        [
            "Total Debt",
            "Long Term Debt",
            "Long Term Debt And Capital Lease Obligation"
        ]
    )

    fundamental_data["Equity"] = get_statement_value(
        balance_sheet,
        [
            "Stockholders Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest"
        ]
    )

    fundamental_data["Assets"] = get_statement_value(
        balance_sheet,
        [
            "Total Assets"
        ]
    )

    fundamental_data["Current_Assets"] = get_statement_value(
        balance_sheet,
        [
            "Current Assets"
        ]
    )

    fundamental_data["Current_Liabilities"] = get_statement_value(
        balance_sheet,
        [
            "Current Liabilities"
        ]
    )

    fundamental_data["Cash"] = get_statement_value(
        balance_sheet,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Federal Funds Sold"
        ]
    )

    fundamental_data["Cash_And_Investments"] = get_statement_value(
        balance_sheet,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents"
        ]
    )

    fundamental_data["Shares"] = get_statement_value(
        balance_sheet,
        [
            "Ordinary Shares Number",
            "Share Issued"
        ]
    )

    fundamental_data["Net_Debt"] = get_statement_value(
        balance_sheet,
        [
            "Net Debt"
        ]
    )

    fundamental_data["Tangible_Book_Value"] = get_statement_value(
        balance_sheet,
        [
            "Tangible Book Value"
        ]
    )

    fundamental_data["Invested_Capital"] = get_statement_value(
        balance_sheet,
        [
            "Invested Capital"
        ]
    )

    # -------------------------
    # Cash flow statement
    # -------------------------

    fundamental_data["Operating_Cash_Flow"] = get_statement_value(
        cash_flow,
        [
            "Operating Cash Flow"
        ]
    )

    fundamental_data["Free_Cash_Flow"] = get_statement_value(
        cash_flow,
        [
            "Free Cash Flow"
        ]
    )

    fundamental_data["Depreciation"] = get_statement_value(
        cash_flow,
        [
            "Depreciation And Amortization",
            "Depreciation"
        ]
    )

    fundamental_data["Capital_Expenditure"] = get_statement_value(
        cash_flow,
        [
            "Capital Expenditure"
        ]
    )

    # -------------------------
    # Sort by date
    # -------------------------

    fundamental_data = fundamental_data.sort_index()

    # Yahoo often returns a placeholder year with no data.
    fundamental_data = fundamental_data.dropna(how="all")

    return fundamental_data


def safe_pct_change(series):
    """
    Year-over-year growth that is undefined when the prior
    value is zero or negative (growth from a loss is not
    meaningful as a percentage).
    """

    previous = series.shift(1)

    growth = (series / previous - 1) * 100

    return growth.where(previous > 0)


def calculate_fundamental_ratios(
    fundamental_data
):

    data = fundamental_data.copy()

    # -------------------------
    # Growth
    # -------------------------

    data["Revenue_Growth"] = safe_pct_change(
        data["Revenue"]
    )

    data["Net_Income_Growth"] = safe_pct_change(
        data["Net_Income"]
    )

    data["EPS_Growth"] = safe_pct_change(
        data["EPS"]
    )

    data["NII_Growth"] = safe_pct_change(
        data["Net_Interest_Income"]
    )

    # -------------------------
    # Profitability
    # -------------------------

    data["Net_Margin"] = (
        data["Net_Income"]
        / data["Revenue"]
        * 100
    )

    # Net margin excluding one-off items, where the source provides it.
    data["Normalized_Net_Margin"] = (
        data["Normalized_Income"]
        / data["Revenue"]
        * 100
    )

    data["Operating_Margin"] = (
        data["Operating_Income"]
        / data["Revenue"]
        * 100
    )

    # Ratios on a negative denominator are meaningless.
    positive_equity = data["Equity"].where(data["Equity"] > 0)

    data["ROE"] = (
        data["Net_Income"]
        / positive_equity
        * 100
    )

    data["ROA"] = (
        data["Net_Income"]
        / data["Assets"]
        * 100
    )

    # -------------------------
    # Leverage
    # -------------------------

    data["Debt_to_Equity"] = (
        data["Debt"]
        / positive_equity
    )

    data["Assets_to_Equity"] = (
        data["Assets"]
        / positive_equity
    )

    # Net interest income / total assets. A proxy for net
    # interest margin (true NIM uses average earning assets,
    # which Yahoo does not provide).
    data["NIM_Proxy"] = (
        data["Net_Interest_Income"]
        / data["Assets"]
        * 100
    )

    # -------------------------
    # Liquidity
    # -------------------------

    data["Current_Ratio"] = (
        data["Current_Assets"]
        / data["Current_Liabilities"]
    )

    # -------------------------
    # Cash flow
    # -------------------------

    data["FCF_Margin"] = (
        data["Free_Cash_Flow"]
        / data["Revenue"]
        * 100
    )

    positive_income = data["Net_Income"].where(
        data["Net_Income"] > 0
    )

    data["FCF_to_Net_Income"] = (
        data["Free_Cash_Flow"]
        / positive_income
    )

    return data.replace([np.inf, -np.inf], np.nan)


def prepare_fundamental_data(
    income_stmt,
    balance_sheet,
    cash_flow
):

    fundamental_data = build_fundamental_data(
        income_stmt,
        balance_sheet,
        cash_flow
    )

    fundamental_data = calculate_fundamental_ratios(
        fundamental_data
    )

    return fundamental_data

# Year-over-year jumps this large are not organic growth: they
# indicate a merger, acquisition or large capital raise.
BREAK_ASSET_GROWTH = 50.0
BREAK_EQUITY_GROWTH = 80.0

GROWTH_COLUMNS = [
    "Revenue_Growth",
    "Net_Income_Growth",
    "EPS_Growth",
    "NII_Growth",
]


def detect_structural_break(fundamental_data):
    """
    Most recent fiscal year whose balance sheet jumped by more
    than organic growth could explain. Returns the date or None.
    """

    if fundamental_data is None or fundamental_data.empty:
        return None

    assets = safe_pct_change(fundamental_data["Assets"])
    equity = safe_pct_change(fundamental_data["Equity"])

    jumps = (assets > BREAK_ASSET_GROWTH) | (equity > BREAK_EQUITY_GROWTH)

    if not jumps.any():
        return None

    return jumps[jumps].index[-1]


def post_break_data(fundamental_data):
    """
    History usable for growth estimates: from the structural break
    onward, with the break year's own growth (the jump) removed.
    Returns (data, break_date).
    """

    break_date = detect_structural_break(fundamental_data)

    if break_date is None:
        return fundamental_data, None

    data = fundamental_data.loc[break_date:].copy()

    columns = [c for c in GROWTH_COLUMNS if c in data.columns]

    data.loc[break_date, columns] = np.nan

    return data, break_date
