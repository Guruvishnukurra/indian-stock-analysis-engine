import pandas as pd
import yfinance as yf

from src.cache import DAY, HOUR, cached


# ---------------------------------------------------------
# Cached primitives (prices refresh every few hours,
# statements weekly).
# ---------------------------------------------------------

@cached("info", 12 * HOUR)
def get_info(ticker):
    return yf.Ticker(ticker).info


@cached("history", 6 * HOUR)
def get_history(ticker, period="5y"):
    return yf.Ticker(ticker).history(period=period)


STATEMENT_ATTRIBUTES = {
    "income_stmt": "income_stmt",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cashflow",
    "quarterly_income_stmt": "quarterly_income_stmt",
}


@cached("statements", 7 * DAY)
def get_statement(ticker, kind):
    return getattr(yf.Ticker(ticker), STATEMENT_ATTRIBUTES[kind])


def _safe_fetch(fetch, default, label, warnings):
    """
    Run one data fetch. On failure, record a warning and
    return the default instead of crashing the analysis.
    """

    try:
        result = fetch()
    except Exception as error:
        warnings.append(f"{label} unavailable: {error}")
        return default

    if result is None:
        warnings.append(f"{label} unavailable.")
        return default

    if isinstance(result, pd.DataFrame) and result.empty:
        warnings.append(f"{label} is empty.")

    return result


def fetch_company_data(ticker, period="5y"):
    """
    Fetch everything needed for one company in a single,
    failure-tolerant step.

    Each piece is fetched independently: a failure in one
    (e.g. quarterly statements) never prevents the others.
    """

    warnings = []

    empty = pd.DataFrame()

    def statement(kind):
        return lambda: get_statement(ticker, kind)

    bundle = {
        "ticker": ticker,
        "info": _safe_fetch(
            lambda: get_info(ticker), {}, "Company info", warnings
        ),
        "price_data": _safe_fetch(
            lambda: get_history(ticker, period),
            empty, "Price history", warnings
        ),
        "income_stmt": _safe_fetch(
            statement("income_stmt"),
            empty, "Annual income statement", warnings
        ),
        "balance_sheet": _safe_fetch(
            statement("balance_sheet"),
            empty, "Annual balance sheet", warnings
        ),
        "cash_flow": _safe_fetch(
            statement("cash_flow"),
            empty, "Annual cash flow", warnings
        ),
        "quarterly_income_stmt": _safe_fetch(
            statement("quarterly_income_stmt"),
            empty, "Quarterly income statement", warnings
        ),
        "warnings": warnings,
    }

    return bundle


@cached("index", 6 * HOUR)
def _index_history(symbol, period):
    return yf.Ticker(symbol).history(period=period)


def fetch_index_history(symbol, period="5y", min_rows=200):
    """
    Fetch index history. Returns None if Yahoo does not serve a
    usable history (several NSE sector indices return only one row).
    """

    try:
        history = _index_history(symbol, period)
    except Exception:
        return None

    if history is None or len(history) < min_rows:
        return None

    return history


@cached("close_prices", 6 * HOUR)
def fetch_close_prices(tickers, period="5y"):
    """
    Closing prices for several tickers in one request.
    Returns an empty DataFrame on failure.
    """

    if not tickers:
        return pd.DataFrame()

    tickers = list(tickers)

    try:
        data = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception:
        return pd.DataFrame()

    if data is None or data.empty:
        return pd.DataFrame()

    close = data["Close"]

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    return close
