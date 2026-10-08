import os
import sys
from pathlib import Path

# Tests must never read or write the on-disk data cache.
os.environ["STOCK_ENGINE_CACHE"] = "0"

# Tests must never call a real local LLM.
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_statement(rows, years):
    """Yahoo-style statement: line items as rows, dates as columns."""

    columns = pd.to_datetime([f"{y}-03-31" for y in years])

    return pd.DataFrame(
        {col: [rows[name][i] for name in rows] for i, col in enumerate(columns)},
        index=list(rows),
    )


@pytest.fixture
def years():
    return [2022, 2023, 2024, 2025]


@pytest.fixture
def healthy_statements(years):
    income = make_statement({
        "Total Revenue": [1000, 1100, 1210, 1330],
        "Operating Income": [250, 275, 300, 330],
        "Net Income": [180, 200, 220, 240],
        "Diluted EPS": [18, 20, 22, 24],
    }, years)

    balance = make_statement({
        "Stockholders Equity": [900, 1000, 1100, 1200],
        "Total Assets": [1500, 1650, 1800, 2000],
        "Total Debt": [100, 100, 90, 80],
        "Cash Cash Equivalents And Short Term Investments": [200, 220, 250, 300],
        "Current Assets": [600, 650, 700, 750],
        "Current Liabilities": [300, 320, 340, 360],
    }, years)

    cash_flow = make_statement({
        "Free Cash Flow": [150, 170, 190, 210],
        "Operating Cash Flow": [200, 220, 240, 260],
        "Capital Expenditure": [-50, -50, -50, -50],
    }, years)

    return income, balance, cash_flow


@pytest.fixture
def price_data():
    dates = pd.bdate_range("2021-01-01", "2025-12-31", tz="Asia/Kolkata")

    rng = np.random.default_rng(0)

    close = 400 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, len(dates))))

    return pd.DataFrame({
        "Close": close,
        "Volume": rng.integers(1_000, 10_000, len(dates)),
        "Dividends": 0.0,
    }, index=dates)
