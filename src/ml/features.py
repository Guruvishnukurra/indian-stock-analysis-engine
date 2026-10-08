"""
Price-only features for the trend model.

Every feature at date t uses data up to and including t only.
Fundamentals are deliberately excluded: Yahoo provides no
point-in-time history, so using them would leak future data.
"""

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_5", "ret_20", "ret_60", "ret_120", "ret_250",
    "vol_20", "vol_60",
    "dist_sma50", "dist_sma200",
    "rsi_14", "macd_hist",
    "rel_20", "rel_60",
    "mkt_ret_20", "mkt_ret_60", "mkt_above_200",
    "drawdown_250",
]


def _rsi(close, window=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    return 100 - 100 / (1 + gain / loss)


def build_features(close, market_close):
    """
    close, market_close: daily closing prices (aligned dates).
    Returns a DataFrame of features indexed by date.
    """

    f = pd.DataFrame(index=close.index)

    daily = close.pct_change(fill_method=None)

    for n in (5, 20, 60, 120, 250):
        f[f"ret_{n}"] = close.pct_change(n, fill_method=None)

    f["vol_20"] = daily.rolling(20).std()
    f["vol_60"] = daily.rolling(60).std()

    f["dist_sma50"] = close / close.rolling(50).mean() - 1
    f["dist_sma200"] = close / close.rolling(200).mean() - 1

    f["rsi_14"] = _rsi(close)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    f["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / close

    market_ret_20 = market_close.pct_change(20, fill_method=None)
    market_ret_60 = market_close.pct_change(60, fill_method=None)

    f["rel_20"] = f["ret_20"] - market_ret_20
    f["rel_60"] = f["ret_60"] - market_ret_60
    f["mkt_ret_20"] = market_ret_20
    f["mkt_ret_60"] = market_ret_60
    f["mkt_above_200"] = (
        market_close > market_close.rolling(200).mean()
    ).astype(float)

    f["drawdown_250"] = close / close.rolling(250).max() - 1

    return f.replace([np.inf, -np.inf], np.nan)


def technical_score_from_features(f):
    """
    The engine's rule-based technical score, reconstructed from
    the same inputs (price vs SMA 50/200, RSI, MACD, 30D-ish
    return), so it can be backtested as a baseline.
    Returns +1 (Strong), 0 (Neutral), -1 (Weak).
    """

    votes = pd.DataFrame(index=f.index)

    votes["sma50"] = np.sign(f["dist_sma50"])
    votes["sma200"] = np.sign(f["dist_sma200"])
    votes["rsi"] = np.where(
        f["rsi_14"] > 70, -1, np.where(f["rsi_14"] >= 50, 1, np.where(f["rsi_14"] < 30, 0, -1))
    )
    votes["macd"] = np.sign(f["macd_hist"])
    votes["ret"] = np.sign(f["ret_20"])

    score = 50 + 50 * votes.mean(axis=1)

    return pd.Series(
        np.where(score >= 65, 1, np.where(score <= 35, -1, 0)),
        index=f.index,
    )
