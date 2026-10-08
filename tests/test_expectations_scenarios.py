import pytest

from src import config
from src.expectations import (
    residual_income_value,
    reverse_dcf,
    reverse_residual_income,
    solve_implied_growth,
)
from src.fundamentals import prepare_fundamental_data
from src.quarterly import build_quarterly_fundamentals
from src.scenarios import run_scenarios
from src.valuation import calculate_dcf, estimate_cost_of_equity, run_dcf

import pandas as pd

EMPTY = pd.DataFrame()


def test_reverse_dcf_round_trip():
    # If the price equals the DCF value at 9% growth,
    # the reverse DCF must recover 9%.
    price = calculate_dcf(
        100, 10, growth_rate=0.09,
        terminal_growth=config.DCF_TERMINAL_GROWTH, wacc=0.12,
        forecast_years=config.DCF_HIGH_GROWTH_YEARS,
        net_cash=50, fade_years=config.DCF_FADE_YEARS,
    )

    implied, status = solve_implied_growth(price, 100, 10, 0.12, 50)

    assert status == "solved"
    assert implied == pytest.approx(0.09, abs=1e-3)


def test_reverse_dcf_flags_demanding_price(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    dcf = run_dcf(data, 10, raw_beta=1.0, market_cap=4000, normalized_fcf=190)

    result = reverse_dcf(dcf["base"] * 3, dcf, 10, data)

    assert result["implied_growth"] > result["reference_growth"]
    assert result["assessment"] in ("Demanding", "Very demanding")


def test_roe_equal_to_cost_of_equity_is_worth_book():
    # No excess return -> value equals book value.
    assert residual_income_value(100, 0.13, 0.13, 0.15, 0.05) == pytest.approx(100)


def test_reverse_residual_income_round_trip(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    cost_of_equity, _, _ = estimate_cost_of_equity(1.0)

    result_at_book = reverse_residual_income(100, 100, 15, 1.0, data)

    # Price = book means the market expects ROE = cost of equity.
    assert result_at_book["implied_roe"] == pytest.approx(cost_of_equity * 100, abs=0.01)


def _peer_pe(low, median, high):
    return {"available": True, "multiple_low": low,
            "multiple_median": median, "multiple_high": high}


def test_scenarios_are_ordered(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    result = run_scenarios(
        {"positive_earnings": True},
        {"peer_pe": _peer_pe(15, 20, 25), "historical_pe": {"available": False}},
        {"trailing_eps": 24},
        data,
        build_quarterly_fundamentals(income_stmt=EMPTY),
        price=400,
        raw_beta=1.0,
    )

    cases = result["cases"]

    assert cases["bear"]["value"] <= cases["base"]["value"] <= cases["bull"]["value"]
    assert cases["bear"]["exit_pe"] == 15 and cases["bull"]["exit_pe"] == 25


def test_scenarios_need_positive_earnings():
    result = run_scenarios(
        {"positive_earnings": False}, {}, {"trailing_eps": -3},
        EMPTY, EMPTY, price=100, raw_beta=1.0,
    )

    assert not result["available"]
