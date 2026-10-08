import yfinance as yf
import pandas as pd

from src.cache import DAY, cached


@cached("industry", 7 * DAY)
def get_industry_companies(industry_key, region="IN"):
    """
    Get companies associated with a Yahoo Finance industry.

    Uses Yahoo Finance's Industry object rather than a
    manually maintained list of companies.
    """

    if not industry_key:
        return pd.DataFrame()

    try:
        industry = yf.Industry(industry_key, region=region)
        companies = industry.top_companies
    except Exception:
        return pd.DataFrame()

    if companies is None:
        return pd.DataFrame()

    return companies.copy()


def get_peer_tickers(industry_key, target_ticker, region="IN"):
    """
    Candidate peer tickers for an already-known industry key,
    excluding the target. Returns [] if unavailable.
    """

    companies = get_industry_companies(
        industry_key=industry_key,
        region=region
    )

    if companies is None or companies.empty:
        return []

    # The same company can be listed as X.NS and X.BO.
    # Keep one listing per company (NSE preferred) and drop
    # any listing of the target itself.
    def base(symbol):
        return str(symbol).rsplit(".", 1)[0].upper()

    target_base = base(target_ticker)

    chosen = {}

    for ticker in companies.index.tolist():

        key = base(ticker)

        if key == target_base:
            continue

        if key not in chosen or str(ticker).endswith(".NS"):
            chosen[key] = ticker

    return list(chosen.values())
