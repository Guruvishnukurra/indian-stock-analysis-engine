"""
Convert an analysis result into JSON-safe data for the API.

Large intermediate frames are reduced to what a dashboard needs:
annual and quarterly fundamentals, about one year of price/SMA
history, and the most recent headlines.
"""

import math
from datetime import date, datetime

import numpy as np
import pandas as pd


PRICE_HISTORY_DAYS = 260
HEADLINES = 25

DROP_COLUMNS = {"Summary"}


def to_jsonable(value):
    """Recursively convert pandas/numpy/datetime values."""

    if value is None or isinstance(value, (bool, str)):
        return value

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, (int, np.integer)):
        return int(value)

    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return None if pd.isna(value) else value.isoformat()

    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]

    if isinstance(value, pd.Series):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, pd.DataFrame):
        frame = value.drop(columns=[c for c in value.columns if c in DROP_COLUMNS])
        if isinstance(frame.index, pd.RangeIndex):
            return [to_jsonable(row) for row in frame.to_dict(orient="records")]
        return {
            str(k): to_jsonable(v)
            for k, v in frame.to_dict(orient="index").items()
        }

    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return str(value)


def _dated_records(frame, columns):

    if frame is None or frame.empty:
        return []

    columns = [c for c in columns if c in frame.columns]

    data = frame[columns].copy()

    index = pd.DatetimeIndex(data.index)

    if index.tz is not None:
        index = index.tz_localize(None)

    data.insert(0, "date", index.strftime("%Y-%m-%d"))

    return to_jsonable(data.reset_index(drop=True))


def serialize_analysis(analysis):

    if analysis.get("status") != "ok":
        return to_jsonable(analysis)

    heavy = {
        "fundamental_data", "quarterly_data", "technical_data",
        "market_features", "latest_technical", "news",
    }

    result = {k: v for k, v in analysis.items() if k not in heavy}

    result["fundamentals_annual"] = _dated_records(
        analysis["fundamental_data"],
        ["Revenue", "Net_Income", "EPS", "Free_Cash_Flow", "Equity",
         "Operating_Margin", "Net_Margin", "ROE", "Debt_to_Equity"],
    )

    result["fundamentals_quarterly"] = _dated_records(
        analysis["quarterly_data"],
        ["Revenue", "Net_Income", "EPS", "Net_Margin",
         "Revenue_YoY", "Net_Profit_YoY", "EPS_YoY"],
    )

    result["price_history"] = _dated_records(
        analysis["technical_data"].tail(PRICE_HISTORY_DAYS),
        ["Close", "SMA_50", "SMA_200", "RSI_14"],
    )

    latest = analysis["latest_technical"]

    result["latest_technical"] = to_jsonable(
        latest[[c for c in ["Close", "SMA_20", "SMA_50", "SMA_200", "RSI_14",
                            "MACD", "MACD_Signal", "Return_30D", "Volatility_30"]
                if c in latest.index]]
    )

    news = dict(analysis.get("news") or {})

    articles = news.pop("news", None)

    if isinstance(articles, pd.DataFrame) and not articles.empty:
        keep = [c for c in ["Date", "Headline", "URL", "VADER_Score", "FinBERT_Score"]
                if c in articles.columns]
        recent = articles.sort_values("Date", ascending=False).head(HEADLINES)[keep]
        news["articles"] = to_jsonable(recent.reset_index(drop=True))
    else:
        news["articles"] = []

    result["news"] = news

    return to_jsonable(result)
