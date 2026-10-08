"""
Offline tests: no network. They check that missing or
meaningless data degrades gracefully instead of crashing or
inventing values.
"""

import numpy as np
import pandas as pd
import pytest

from src import analysis as analysis_module
from src.company_profile import assess_company_profile, classify_company
from src.confidence import calculate_confidence
from src.fair_value import build_fair_value_range
from src.fundamentals import prepare_fundamental_data
from src.quarterly import build_quarterly_fundamentals
from src.report import generate_report
from src.scoring import (
    calculate_fundamental_score,
    calculate_quality_value_score,
    calculate_technical_score,
    calculate_valuation_score,
    extract_fundamental_metrics,
)
from src.technical import calculate_technical_features
from src.utils import interpolate_score, round_price, safe_growth, trailing_return
from src.valuation import (
    calculate_dcf,
    historical_pe_valuation,
    peer_multiple_valuation,
    run_dcf,
)

from tests.conftest import make_statement


EMPTY = pd.DataFrame()


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def test_growth_from_negative_base_is_undefined():
    assert safe_growth(1.0, -2.0) is None
    assert safe_growth(1.0, 0.0) is None
    assert safe_growth(12.0, 10.0) == pytest.approx(20.0)


def test_trailing_return_needs_enough_history():
    assert trailing_return(pd.Series([1.0, 2.0]), 30) is None


def test_round_price_avoids_false_precision():
    assert round_price(3017.86) == 3000
    assert round_price(492.3) == 490
    assert round_price(-5) is None


def test_interpolate_supports_lower_is_better():
    assert interpolate_score(0.3, weak=1.5, strong=0.3) == 100
    assert interpolate_score(None, 0, 10) is None


# ---------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------

def test_empty_income_statement_keeps_balance_sheet(healthy_statements):
    _, balance, cash_flow = healthy_statements

    data = prepare_fundamental_data(EMPTY, balance, cash_flow)

    assert data["Equity"].notna().all()
    assert data["Revenue"].isna().all()


def test_all_statements_empty_does_not_crash():
    data = prepare_fundamental_data(EMPTY, EMPTY, EMPTY)
    assert data.empty


def test_eps_growth_from_loss_is_nan(years):
    income = make_statement({
        "Total Revenue": [100, 110, 120, 130],
        "Net Income": [-10, -5, 4, 8],
        "Diluted EPS": [-1.0, -0.5, 0.4, 0.8],
    }, years)

    data = prepare_fundamental_data(income, EMPTY, EMPTY)

    growth = data["EPS_Growth"].tolist()

    assert np.isnan(growth[1]) and np.isnan(growth[2])
    assert growth[3] == pytest.approx(100.0)


def test_negative_equity_gives_no_roe(years):
    income = make_statement({"Net Income": [10, 10, 10, 10]}, years)
    balance = make_statement({"Stockholders Equity": [-5, -5, -5, -5]}, years)

    data = prepare_fundamental_data(income, balance, EMPTY)

    assert data["ROE"].isna().all()


def test_empty_quarterly_returns_standard_columns():
    data = build_quarterly_fundamentals(income_stmt=EMPTY)
    assert data.empty
    assert "Revenue_YoY" in data.columns


# ---------------------------------------------------------
# Company profile
# ---------------------------------------------------------

@pytest.mark.parametrize("sector, industry, expected", [
    ("Technology", "Information Technology Services", "technology"),
    ("Financial Services", "Banks - Regional", "bank"),
    ("Financial Services", "Credit Services", "nbfc"),
    ("Financial Services", "Mortgage Finance", "nbfc"),
    ("Financial Services", "Insurance - Life", "insurance"),
    ("Financial Services", "Capital Markets", "capital_markets"),
    ("Financial Services", "Financial Data & Stock Exchanges", "capital_markets"),
    ("Financial Services", "Asset Management", "asset_management"),
    ("Healthcare", "Drug Manufacturers - Specialty & Generic", "pharma"),
    ("Healthcare", "Medical Care Facilities", "healthcare_services"),
    ("Consumer Cyclical", "Auto Manufacturers", "automobile"),
    (None, None, "other"),
])
def test_classification(sector, industry, expected):
    assert classify_company(sector, industry)["company_type"] == expected


def _profile(fundamentals, sector, industry, eps):
    return assess_company_profile(
        fundamentals,
        build_quarterly_fundamentals(income_stmt=EMPTY),
        sector=sector,
        industry=industry,
        trailing_eps=eps,
    )


def test_bank_excludes_dcf_and_uses_pb(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    profile = _profile(data, "Financial Services", "Banks - Regional", 24)

    assert not profile["dcf_applicable"]
    assert profile["peer_pb_applicable"]
    assert profile["peer_pe_applicable"]


def test_loss_maker_uses_sales_fallback_only(years):
    income = make_statement({
        "Total Revenue": [100, 150, 200, 260],
        "Net Income": [-50, -40, -30, -20],
    }, years)
    cash_flow = make_statement({"Free Cash Flow": [-60, -50, -40, -30]}, years)

    data = prepare_fundamental_data(income, EMPTY, cash_flow)

    profile = _profile(data, "Consumer Cyclical", "Internet Retail", -2.0)

    assert not profile["dcf_applicable"]
    assert not profile["peer_pe_applicable"]
    assert profile["peer_evs_applicable"]


# ---------------------------------------------------------
# Valuation
# ---------------------------------------------------------

def test_dcf_refuses_negative_fcf():
    assert calculate_dcf(-100, 10) is None


def test_dcf_adds_net_cash():
    without = calculate_dcf(100, 10, net_cash=0)
    with_cash = calculate_dcf(100, 10, net_cash=500)
    assert with_cash == pytest.approx(without + 50)


def test_run_dcf_returns_range_and_grid(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    result = run_dcf(data, 10, raw_beta=1.0, market_cap=4000, normalized_fcf=190)

    assert result["available"]
    assert result["low"] < result["base"] < result["high"]
    assert result["sensitivity"].shape == (3, 3)


def test_peer_multiple_unavailable_without_peers():
    result = peer_multiple_valuation(10, None, "P/E")
    assert not result["available"]


def test_historical_pe_rejects_unrestated_split(years, price_data):
    # EPS halves while net income rises: a bonus/split that the
    # statements did not restate.
    income = make_statement({
        "Net Income": [100, 110, 120, 130],
        "Diluted EPS": [20, 22, 12, 13],
    }, years)

    data = prepare_fundamental_data(income, EMPTY, EMPTY)

    result = historical_pe_valuation(price_data, data, trailing_eps=13)

    assert not result["available"]
    assert "split" in result["reason"]


def test_historical_pe_uses_only_published_eps(healthy_statements, price_data):
    data = prepare_fundamental_data(*healthy_statements)

    result = historical_pe_valuation(price_data, data, trailing_eps=24)

    assert result["available"]
    # Prices before FY2022 EPS was published (Mar-31 + lag) are unused.
    assert result["years_used"] == 4


# ---------------------------------------------------------
# Fair value + confidence
# ---------------------------------------------------------

def _method(base, low, high, **extra):
    return {"available": True, "base": base, "low": low, "high": high, **extra}


def test_fair_value_renormalizes_missing_methods():
    results = {
        "dcf": {"available": False, "reason": "negative FCF"},
        "peer_pe": _method(100, 90, 110),
    }

    fv = build_fair_value_range(results, {"dcf": 0.45, "peer_pe": 0.50}, 80)

    assert fv["weights_used"] == {"peer_pe": 1.0}
    assert fv["base"] == pytest.approx(100)


def test_fair_value_widens_when_methods_disagree():
    results = {
        "dcf": _method(60, 55, 65),
        "peer_pe": _method(140, 130, 150),
    }

    fv = build_fair_value_range(results, {"dcf": 0.5, "peer_pe": 0.5}, 100)

    assert fv["widened_for_disagreement"]
    assert fv["low"] <= 60 and fv["high"] >= 140


def test_no_methods_means_no_fair_value():
    fv = build_fair_value_range({}, {"dcf": 1.0}, 100)
    assert not fv["available"]


def test_confidence_handles_empty_inputs():
    confidence = calculate_confidence(
        {"score": 0, "annual_years": 0},
        {"available": False},
        {},
        EMPTY,
        {"classification_certainty": "Low"},
    )

    assert 0 <= confidence["score"] <= 25


def test_heterogeneous_peers_lower_confidence(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    def confidence_for(low, high):
        results = {"peer_pe": _method(
            100, 80, 120, peer_count=10,
            multiple_low=low, multiple_high=high
        )}
        fv = build_fair_value_range(results, {"peer_pe": 1.0}, 100)
        return calculate_confidence(
            {"score": 100, "annual_years": 4}, fv, results, data,
            {"classification_certainty": "High"},
        )["score"]

    assert confidence_for(5, 20) < confidence_for(18, 22)


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

def test_missing_metrics_are_excluded_not_penalised(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    metrics = extract_fundamental_metrics(
        data, build_quarterly_fundamentals(income_stmt=EMPTY), 190
    )

    result = calculate_fundamental_score(metrics, "technology")

    assert result["score"] is not None
    assert all(item["score"] is not None for item in result["metrics"])


def test_too_few_metrics_gives_no_score():
    metrics = {"values": {"roe": 15.0}, "sources": {}}
    assert calculate_fundamental_score(metrics, "bank")["score"] is None


def test_valuation_score_is_not_imputed():
    assert calculate_valuation_score()["score"] is None
    assert calculate_quality_value_score(80, None) is None


def test_technical_score_skips_missing_sma200(price_data):
    recent = price_data.tail(120)   # newly listed: no 200-day SMA

    latest = calculate_technical_features(recent).iloc[-1]

    result = calculate_technical_score(latest)

    assert result["score"] is not None
    assert not any("200-day" in text for _, text in result["signals"])


# ---------------------------------------------------------
# Full pipeline with almost no data
# ---------------------------------------------------------

def test_pipeline_survives_minimal_data(monkeypatch, price_data, capsys):
    bundle = {
        "ticker": "NEWCO.NS",
        "stock": None,
        "info": {},
        "price_data": price_data.tail(60),
        "income_stmt": EMPTY,
        "balance_sheet": EMPTY,
        "cash_flow": EMPTY,
        "quarterly_income_stmt": EMPTY,
        "warnings": ["Annual income statement is empty."],
    }

    monkeypatch.setattr(analysis_module, "fetch_company_data", lambda t: bundle)
    monkeypatch.setattr(analysis_module, "get_peer_tickers", lambda *a, **k: [])
    monkeypatch.setattr(analysis_module, "fetch_index_history", lambda *a, **k: None)

    result = analysis_module.analyze_stock("NEWCO.NS", include_news=False)

    assert result["status"] == "ok"
    assert not result["fair_value"]["available"]
    assert result["explanation"]["stance"] == "INSUFFICIENT DATA"

    generate_report(result)

    assert "INSUFFICIENT DATA" in capsys.readouterr().out


def test_pipeline_without_prices_fails_cleanly(monkeypatch):
    bundle = {
        "ticker": "X", "stock": None, "info": {}, "price_data": EMPTY,
        "income_stmt": EMPTY, "balance_sheet": EMPTY, "cash_flow": EMPTY,
        "quarterly_income_stmt": EMPTY, "warnings": [],
    }

    monkeypatch.setattr(analysis_module, "fetch_company_data", lambda t: bundle)

    result = analysis_module.analyze_stock("X", include_news=False)

    assert result["status"] == "failed"


def test_same_peer_set_methods_are_not_independent(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)

    results = {
        "peer_pe": _method(100, 95, 105, peer_count=10,
                           multiple_low=19, multiple_high=21),
        "peer_pb": _method(101, 96, 106, peer_count=10,
                           multiple_low=1.9, multiple_high=2.1),
    }

    fv = build_fair_value_range(results, {"peer_pe": 0.5, "peer_pb": 0.5}, 100)

    confidence = calculate_confidence(
        {"score": 100, "annual_years": 4}, fv, results, data,
        {"classification_certainty": "High"},
    )

    points = {c["name"]: c["points"] for c in confidence["components"]}

    assert points["Valuation methods"] == 8
    assert points["Method agreement"] <= 10


def test_valuation_gap_wording_keeps_direction():
    from src.explain import build_reasons

    def reasons(upside):
        analysis = {
            "fundamental_score": {"metrics": []},
            "fair_value": {"available": True, "upside_base": upside,
                           "low": 1, "high": 10_000},
            "technical_score": {}, "market_score": {}, "news": {},
            "current_price": 1406, "inputs": {}, "peer_analysis": {},
        }
        return build_reasons(analysis)

    _, not_bullish = reasons(-74.3)
    assert "Base fair-value estimate is 74% below the price" in not_bullish

    bullish, _ = reasons(30.3)
    assert "Base fair-value estimate is 30% above the price" in bullish


def test_context_method_does_not_move_range():
    results = {
        "dcf": _method(145, 130, 160),
        "peer_pe": _method(255, 220, 300),
        "historical_pe": _method(1050, 900, 1200),
    }
    weights = {"dcf": 0.25, "peer_pe": 0.70, "historical_pe": 0.05}

    fv = build_fair_value_range(results, weights, 300)

    assert fv["high"] <= 300
    assert "Historical P/E" in fv["context_methods"]
    assert set(fv["methods_used"]) == {"DCF", "Peer P/E"}
    # The range spans both credible methods' central estimates.
    assert fv["low"] <= 145 and fv["high"] >= 255


def test_valuation_score_blends_method_premiums():
    score = calculate_valuation_score(
        method_upsides={"DCF": -50.0, "Peer P/E": 0.0},
        method_weights={"DCF": 0.25, "Peer P/E": 0.75},
    )["score"]

    assert score == pytest.approx(0.25 * 0 + 0.75 * 50)
