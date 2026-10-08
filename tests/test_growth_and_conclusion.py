import numpy as np

from src.conclusion import build_conclusion
from src.growth_stage import project_value, simulate_values


COMMON = {"revenue": 1000.0, "start_margin": -0.15, "net_debt": -100.0, "shares": 10.0}


def test_cash_burning_years_cap_terminal_share_at_100pct():
    detail = project_value(**COMMON, start_growth=0.6, target_margin=0.10,
                           wacc=0.13, breakdown=True)

    assert detail["explicit_years_burn_cash"]
    assert detail["terminal_share"] == 1.0
    assert detail["peak_cash_burn"] > 0
    assert detail["first_positive_fcf_year"] is not None


def test_simulation_is_reproducible_and_ordered():
    first = simulate_values(COMMON, 0.4, [8.0, 12.0, 17.0], 0.12)
    second = simulate_values(COMMON, 0.4, [8.0, 12.0, 17.0], 0.12)

    assert np.array_equal(first, second)          # seeded
    p10, p90 = np.percentile(first, [10, 90])
    assert p10 < p90


def _growth_analysis():
    return {
        "company_name": "NewCo",
        "current_price": 1406.0,
        "company_profile": {"valuation_family": "operating", "earnings_usable": False},
        "explanation": {"stance": "NOT RATED"},
        "fundamental_metrics": {"values": {"revenue_growth": 88.8}},
        "fair_value": {"base": 170.0},
        "method_results": {"growth_dcf": {
            "implied_margin": 33.0,
            "assumptions": {"peer_margins": {"low": 6.9, "median": 11.6, "high": 17.0}},
            "simulation": {"runs": 4000, "share_justifying_price": 0.0},
            "funding": {"funding_gap": 2e11, "gap_share_of_market_cap": 0.37},
        }},
    }


def test_growth_conclusion_states_what_is_and_is_not_established():
    text = build_conclusion(_growth_analysis())

    assert "growing extremely fast (revenue +89%" in text
    assert "cannot establish that NewCo is worth ₹170" in text
    assert "₹1,406 requires" in text and "about 33%" in text
    assert "7-17%" in text and "unrealistic" in text
    assert "None of 4,000 simulated futures" in text
    assert "37% of its market cap" in text


def test_holding_company_conclusion():
    analysis = _growth_analysis()
    analysis["company_profile"] = {"valuation_family": "financial_balance_sheet",
                                   "holding_company": True}
    assert "sum-of-the-parts" in build_conclusion(analysis)
