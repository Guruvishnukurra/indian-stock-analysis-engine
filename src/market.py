import numpy as np
import pandas as pd

from src.utils import trailing_return


def _normalize_index(index):
    """Align dates across sources that differ in time zone."""

    index = pd.DatetimeIndex(index)

    # Drop the time zone but keep local wall-clock dates.
    if index.tz is not None:
        index = index.tz_localize(None)

    return index.normalize()


def _close_series(data):

    if data is None or data.empty or "Close" not in data.columns:
        return None

    series = data["Close"].copy()

    series.index = _normalize_index(series.index)

    return series[~series.index.duplicated(keep="last")]


def calculate_market_features(
    stock_data,
    market_data,
    sector_data=None
):
    """
    Calculate stock performance relative to the
    broader market and sector.

    sector_data may be None (no sector benchmark); sector
    columns are then NaN rather than raising.
    """

    stock = _close_series(stock_data)

    if stock is None:
        return pd.DataFrame()

    market = _close_series(market_data)
    sector = _close_series(sector_data)

    # Align all datasets by date
    combined = pd.DataFrame(index=stock.index)

    combined["Stock_Close"] = stock

    combined["Market_Close"] = (
        market.reindex(combined.index) if market is not None else np.nan
    )

    combined["Sector_Close"] = (
        sector.reindex(combined.index) if sector is not None else np.nan
    )

    # Daily returns
    for name in ("Stock", "Market", "Sector"):

        combined[f"{name}_Return"] = (
            combined[f"{name}_Close"].pct_change(fill_method=None) * 100
        )

    # Relative performance
    combined["Stock_vs_Market"] = (
        combined["Stock_Return"]
        - combined["Market_Return"]
    )

    combined["Stock_vs_Sector"] = (
        combined["Stock_Return"]
        - combined["Sector_Return"]
    )

    # 20-day returns
    for name in ("Stock", "Market", "Sector"):

        combined[f"{name}_Return_20D"] = (
            combined[f"{name}_Close"].pct_change(20, fill_method=None) * 100
        )

    return combined


def _aligned(first, second, min_observations=60):

    aligned = pd.concat(
        [first, second],
        axis=1
    ).dropna()

    if len(aligned) < min_observations:
        return None

    return aligned


def calculate_beta(stock_returns, market_returns):
    """
    Calculate stock beta relative to the market.
    Returns None with fewer than ~3 months of overlap.
    """

    aligned = _aligned(stock_returns, market_returns)

    if aligned is None:
        return None

    market_variance = aligned.iloc[:, 1].var()

    if not market_variance:
        return None

    covariance = aligned.iloc[:, 0].cov(
        aligned.iloc[:, 1]
    )

    return float(covariance / market_variance)


def calculate_correlation(stock_returns, market_returns):
    """
    Calculate correlation between stock and market returns.
    """

    aligned = _aligned(stock_returns, market_returns)

    if aligned is None:
        return None

    return float(
        aligned.iloc[:, 0].corr(
            aligned.iloc[:, 1]
        )
    )


def summarize_market_context(market_features, window=30):
    """
    Trailing returns of stock, market and sector, and the
    stock's relative performance. Any piece may be None.
    """

    if market_features is None or market_features.empty:
        return {
            "stock_return": None,
            "market_return": None,
            "sector_return": None,
            "relative_to_market": None,
            "relative_to_sector": None,
            "market_above_200dma": None,
            "window": window,
        }

    stock_return = trailing_return(market_features["Stock_Close"], window)
    market_return = trailing_return(market_features["Market_Close"], window)
    sector_return = trailing_return(market_features["Sector_Close"], window)

    def difference(a, b):
        return a - b if a is not None and b is not None else None

    market_close = market_features["Market_Close"].dropna()

    market_above_200dma = None

    if len(market_close) >= 200:
        market_above_200dma = bool(
            market_close.iloc[-1] > market_close.tail(200).mean()
        )

    return {
        "stock_return": stock_return,
        "market_return": market_return,
        "sector_return": sector_return,
        "relative_to_market": difference(stock_return, market_return),
        "relative_to_sector": difference(stock_return, sector_return),
        "market_above_200dma": market_above_200dma,
        "window": window,
    }
