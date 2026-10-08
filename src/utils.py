"""
Small helpers that make missing data safe to handle.

The rule throughout the engine:
    metric unavailable -> return None, never raise.
"""

import math

import numpy as np
import pandas as pd


def is_valid(value):
    """True if value is a finite real number."""

    if value is None:
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def safe_float(value):
    """Convert to float, or None if missing/invalid."""

    return float(value) if is_valid(value) else None


def is_positive(value):
    return is_valid(value) and float(value) > 0


def latest_valid(data, column):
    """
    Most recent non-missing value of a column.

    Returns None if the frame/column is missing or all NaN.
    """

    if data is None or data.empty or column not in data.columns:
        return None

    series = pd.to_numeric(data[column], errors="coerce").dropna()

    series = series[np.isfinite(series)]

    if series.empty:
        return None

    return float(series.iloc[-1])


def valid_values(data, column, last_n=None):
    """Non-missing values of a column, oldest first."""

    if data is None or data.empty or column not in data.columns:
        return []

    series = pd.to_numeric(data[column], errors="coerce").dropna()

    series = series[np.isfinite(series)]

    values = series.tolist()

    if last_n is not None:
        values = values[-last_n:]

    return values


def safe_growth(current, previous):
    """
    Percentage growth that is only defined when the base is
    positive. Growth from a negative or zero base is meaningless
    (e.g. EPS going from -2 to +1 is not "-150%").
    """

    if not is_valid(current) or not is_positive(previous):
        return None

    return (float(current) / float(previous) - 1) * 100


def trailing_return(series, periods):
    """
    Percentage return over the last `periods` observations.
    Returns None if there is not enough history.
    """

    if series is None:
        return None

    series = pd.to_numeric(series, errors="coerce").dropna()

    if len(series) <= periods:
        return None

    start = series.iloc[-(periods + 1)]
    end = series.iloc[-1]

    if not is_positive(start):
        return None

    return (end / start - 1) * 100


def calculate_upside_pct(current_price, fair_value):
    """Percentage difference between fair value and price."""

    if not is_positive(current_price) or not is_valid(fair_value):
        return None

    return (float(fair_value) / float(current_price) - 1) * 100


def interpolate_score(value, weak, strong):
    """
    Map a metric linearly onto 0-100.

    weak   -> 0
    strong -> 100

    Works for "lower is better" metrics by passing
    weak > strong.
    """

    if not is_valid(value) or weak == strong:
        return None

    score = (float(value) - weak) / (strong - weak) * 100

    return max(0.0, min(100.0, score))


def round_price(value):
    """
    Round a price estimate to a precision that does not imply
    false accuracy (about 2.5 significant figures).

    3017.86 -> 3000
    492.3   -> 490
    45.27   -> 45.5
    """

    if not is_valid(value) or value <= 0:
        return None

    magnitude = 10 ** (math.floor(math.log10(value)) - 1)

    step = magnitude / 2

    return round(round(value / step) * step, 2)


def label_from_thresholds(value, thresholds):
    """
    thresholds: list of (min_value, label), highest first.
    """

    if not is_valid(value):
        return "Unavailable"

    for minimum, label in thresholds:
        if value >= minimum:
            return label

    return thresholds[-1][1]


def latest_valid_dated(data, column):
    """(value, date) of the most recent non-missing value, or (None, None)."""

    if data is None or data.empty or column not in data.columns:
        return None, None

    series = pd.to_numeric(data[column], errors="coerce").dropna()

    series = series[np.isfinite(series)]

    if series.empty:
        return None, None

    return float(series.iloc[-1]), series.index[-1]
