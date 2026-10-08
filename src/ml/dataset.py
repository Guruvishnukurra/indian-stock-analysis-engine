"""
Panel dataset for walk-forward validation.

One sample per stock per decision date (every SAMPLE_STEP trading
days). The label is the forward return over HORIZON trading days,
which is only known HORIZON days later; the walk-forward purges
training samples whose label window overlaps the test period.
"""

import io

import pandas as pd
import requests

from src.cache import DAY, cached
from src.config import MARKET_INDEX
from src.data import fetch_close_prices, fetch_index_history
from src.ml.features import build_features, technical_score_from_features


HORIZON = 40          # ~2 months: the 30-60 day trend window
SAMPLE_STEP = 20      # ~monthly decision points
HISTORY = "10y"


@cached("universe", 7 * DAY)
def get_nifty100_symbols():
    """Current NIFTY 100 members from NSE (survivorship-biased)."""

    response = requests.get(
        "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()

    data = pd.read_csv(io.StringIO(response.text))

    return [f"{s}.NS" for s in data["Symbol"].astype(str)]


def _naive(series):
    series = series.copy()
    index = pd.DatetimeIndex(series.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    series.index = index.normalize()
    return series[~series.index.duplicated(keep="last")]


def build_panel(tickers=None):

    tickers = tickers or get_nifty100_symbols()

    closes = fetch_close_prices(tickers, period=HISTORY)

    market = fetch_index_history(MARKET_INDEX, period=HISTORY)

    market_close = _naive(market["Close"])

    frames = []

    for ticker in closes.columns:

        close = _naive(closes[ticker].dropna())

        if len(close) < 300:
            continue

        mkt = market_close.reindex(close.index).ffill()

        features = build_features(close, mkt)

        features["tech_signal"] = technical_score_from_features(features)

        features["forward_return"] = close.shift(-HORIZON) / close - 1

        # Date on which the label becomes known.
        features["label_known"] = close.index.to_series().shift(-HORIZON)

        sampled = features.iloc[::SAMPLE_STEP].copy()
        sampled["ticker"] = ticker

        frames.append(sampled)

    panel = pd.concat(frames)
    panel.index.name = "date"

    return panel.reset_index()
