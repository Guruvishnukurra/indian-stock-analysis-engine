"""
Sector benchmark selection.

Yahoo serves usable history for only a few NSE sector indices.
For every other company type, an equal-weighted basket of the
company's own industry peers is used as the sector benchmark.
"""

import pandas as pd

from src.data import fetch_close_prices, fetch_index_history


# Indices verified to return full history from Yahoo.
# Others (FMCG, Auto, Energy, Metal, ...) currently return a
# single row and are therefore not used.
SECTOR_INDEX_BY_TYPE = {
    "technology": ("^CNXIT", "NIFTY IT"),
    "bank": ("^NSEBANK", "NIFTY BANK"),
    "pharma": ("^CNXPHARMA", "NIFTY PHARMA"),
}

MIN_BASKET_MEMBERS = 3


def build_peer_basket(peer_tickers, period="5y", max_members=10):
    """
    Equal-weighted index of peer prices (rebased to 100).

    Daily returns are averaged across whichever peers traded
    that day, so a recently listed peer does not break the index.
    """

    tickers = list(peer_tickers)[:max_members]

    close = fetch_close_prices(tickers, period=period)

    if close.empty:
        return None, 0

    close = close.dropna(axis=1, how="all")

    members = close.shape[1]

    if members < MIN_BASKET_MEMBERS:
        return None, members

    returns = close.pct_change(fill_method=None)

    basket_return = returns.mean(axis=1, skipna=True).fillna(0)

    index_level = 100 * (1 + basket_return).cumprod()

    return pd.DataFrame({"Close": index_level}), members


def select_sector_benchmark(company_type, peer_tickers, period="5y"):
    """
    Returns:
        {
          "data": DataFrame with Close (or None),
          "name": str,
          "source": "index" | "peer_basket" | "unavailable",
        }
    """

    if company_type in SECTOR_INDEX_BY_TYPE:

        symbol, name = SECTOR_INDEX_BY_TYPE[company_type]

        history = fetch_index_history(symbol, period=period)

        if history is not None:
            return {
                "data": history,
                "name": name,
                "source": "index",
            }

    if peer_tickers:

        basket, members = build_peer_basket(peer_tickers, period=period)

        if basket is not None:
            return {
                "data": basket,
                "name": f"Peer basket ({members} industry peers)",
                "source": "peer_basket",
            }

    return {
        "data": None,
        "name": "Unavailable",
        "source": "unavailable",
    }
