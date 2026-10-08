import numpy as np
import pandas as pd

from src.fundamentals import post_break_data, prepare_fundamental_data
from src.peer_selection import apply_ownership_filter

from tests.conftest import make_statement


EMPTY = pd.DataFrame()


def test_merger_year_is_detected_and_excluded(years):
    income = make_statement({"Net Income": [100, 105, 160, 170]}, years)
    balance = make_statement({
        "Stockholders Equity": [500, 520, 1200, 1300],   # merger in 2024
        "Total Assets": [3000, 3100, 6000, 6400],
    }, years)

    data = prepare_fundamental_data(income, balance, EMPTY)

    growth_data, break_date = post_break_data(data)

    assert break_date.year == 2024
    assert len(growth_data) == 2
    # The merger jump itself is not counted as growth.
    assert np.isnan(growth_data["Net_Income_Growth"].iloc[0])


def test_organic_growth_is_not_a_break(healthy_statements):
    data = prepare_fundamental_data(*healthy_statements)
    assert post_break_data(data)[1] is None


def _peers(ownerships):
    return pd.DataFrame({
        "Ticker": [f"P{i}.NS" for i in range(len(ownerships))],
        "Ownership": ownerships,
        "EPS": 10.0, "PE": 15.0, "Market_Cap": 1e9,
    })


def test_private_target_uses_private_peers_when_enough():
    peers = _peers(["Private"] * 6 + ["PSU"] * 6)

    filtered, note = apply_ownership_filter(peers, "T.NS", "Private")

    assert set(filtered["Ownership"]) == {"Private"}
    assert "only" in note


def test_too_few_same_ownership_peers_keeps_all():
    peers = _peers(["Private"] * 2 + ["PSU"] * 8)

    filtered, note = apply_ownership_filter(peers, "T.NS", "Private")

    assert len(filtered) == 10
    assert note.startswith("Mixed")


def test_similarity_ranks_peers_when_available():
    from src.peer_selection import select_comparable_peers

    peers = _peers(["Private"] * 4).assign(
        Market_Cap=[4e9, 3e9, 2e9, 1e9],
        Similarity=[0.1, 0.2, 0.9, 0.8],
    )

    selected = select_comparable_peers(peers, "T.NS", number_of_peers=2)

    assert selected["Ticker"].tolist() == ["P2.NS", "P3.NS"]


def test_market_cap_ranking_without_similarity():
    from src.peer_selection import select_comparable_peers

    peers = _peers(["Private"] * 4).assign(Market_Cap=[1e9, 4e9, 2e9, 3e9])

    selected = select_comparable_peers(peers, "T.NS", number_of_peers=2)

    assert selected["Ticker"].tolist() == ["P1.NS", "P3.NS"]


def test_ev_sales_subtracts_debt():
    from src.valuation import ev_sales_valuation

    summary = {"median": 2.0, "low": 1.5, "high": 3.0, "count": 8,
               "spread_basis": "interquartile range"}

    no_debt = ev_sales_valuation(1000, 0, 100, summary)
    with_debt = ev_sales_valuation(1000, 500, 100, summary)

    assert no_debt["base"] == 20
    assert with_debt["base"] == 15


def test_ev_sales_unavailable_when_debt_exceeds_value():
    from src.valuation import ev_sales_valuation

    summary = {"median": 1.0, "low": 0.5, "high": 1.5, "count": 8,
               "spread_basis": "interquartile range"}

    assert not ev_sales_valuation(1000, 5000, 100, summary)["available"]


def test_thin_margin_switches_to_ev_sales(years):
    from src.company_profile import assess_company_profile
    from src.quarterly import build_quarterly_fundamentals

    income = make_statement({
        "Total Revenue": [1000, 1100, 1200, 1300],
        "Net Income": [5, 8, 10, 13],          # 1% net margin
    }, years)

    data = prepare_fundamental_data(income, EMPTY, EMPTY)

    profile = assess_company_profile(
        data, build_quarterly_fundamentals(income_stmt=EMPTY),
        sector="Consumer Cyclical", industry="Internet Retail", trailing_eps=0.1,
    )

    assert profile["positive_earnings"]
    assert not profile["peer_pe_applicable"]
    assert profile["peer_evs_applicable"]
    assert "too thin" in profile["peer_pe_reason"]


def test_cached_functions_do_not_collide(tmp_path, monkeypatch):
    from src import cache

    monkeypatch.setattr(cache, "ENABLED", True)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)

    @cache.cached("shared", 3600)
    def first():
        return ["first"]

    @cache.cached("shared", 3600)
    def second():
        return ["second"]

    assert first() == ["first"]
    assert second() == ["second"]


def test_one_off_profit_is_not_a_pe_base(years):
    from src.company_profile import assess_company_profile
    from src.quarterly import build_quarterly_fundamentals

    income = make_statement({
        "Total Revenue": [1000, 1000, 1000, 1000],
        "Operating Income": [-50, -60, -40, -30],   # loss-making operations
        "Net Income": [-100, -110, -90, 800],       # one-off gain
    }, years)

    data = prepare_fundamental_data(income, EMPTY, EMPTY)

    profile = assess_company_profile(
        data, build_quarterly_fundamentals(income_stmt=EMPTY),
        sector="Communication Services", industry="Telecom Services",
        trailing_eps=3.0,
    )

    assert not profile["earnings_usable"]
    assert not profile["peer_pe_applicable"]
    assert "one-off" in profile["peer_pe_reason"]


def test_single_quarter_profit_detected():
    from src.company_profile import earnings_quality_issue

    quarterly = pd.DataFrame({"Net_Income": [-5.0, -6.0, -4.0, 40.0]})

    issue = earnings_quality_issue(
        {"positive_earnings": True, "valuation_family": "operating"},
        EMPTY, quarterly, net_margin=10.0,
    )

    assert "single quarter" in issue
