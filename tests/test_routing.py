import pandas as pd

from src.fundamentals import prepare_fundamental_data
from src.routing import assess_capex_heavy, assess_cyclicality, is_holding_company

from tests.conftest import make_statement


EMPTY = pd.DataFrame()


def fundamentals(years, revenue, operating, net, ocf=None, capex=None, dep=None, fcf=None):
    income = make_statement({
        "Total Revenue": revenue, "Operating Income": operating, "Net Income": net,
    }, years)
    cash_rows = {}
    if ocf:
        cash_rows["Operating Cash Flow"] = ocf
    if capex:
        cash_rows["Capital Expenditure"] = capex
    if dep:
        cash_rows["Depreciation And Amortization"] = dep
    if fcf:
        cash_rows["Free Cash Flow"] = fcf
    cash = make_statement(cash_rows, years) if cash_rows else EMPTY
    return prepare_fundamental_data(income, EMPTY, cash)


def test_volatile_steel_maker_is_cyclical(years):
    data = fundamentals(years, [100] * 4, [25, 8, 12, 30], [15, 4, 7, 20])

    result = assess_cyclicality("Steel", data)

    assert result["cyclical"]
    assert result["cycle_position"] == "peak"          # latest 30% vs median 18.5%


def test_stable_specialty_chemicals_not_cyclical(years):
    # Consumer-brand chemicals (e.g. adhesives) with steady margins.
    data = fundamentals(years, [100] * 4, [20, 21, 22, 21], [14, 15, 15, 15])

    result = assess_cyclicality("Specialty Chemicals", data)

    assert not result["cyclical"]
    assert "stable" in result["cyclical_note"]


def test_non_commodity_industry_never_cyclical(years):
    data = fundamentals(years, [100] * 4, [25, 8, 12, 30], [15, 4, 7, 20])
    assert not assess_cyclicality("Information Technology Services", data)["cyclical"]


def test_capex_heavy_growth_uses_maintenance_fcf(years):
    data = fundamentals(
        years, [100, 150, 220, 320], [12, 18, 26, 38], [8, 12, 18, 26],
        ocf=[15, 22, 32, 45], capex=[-40, -60, -90, -120],
        dep=[5, 7, 10, 14], fcf=[-25, -38, -58, -75],
    )

    result = assess_capex_heavy(data, normalized_fcf=-57, earnings_usable=True)

    assert result["capex_heavy"]
    # (22-7 + 32-10 + 45-14) / 3
    assert abs(result["maintenance_fcf"] - (15 + 22 + 31) / 3) < 1e-9


def test_distress_is_not_capex_heavy(years):
    # Negative operating cash flow: not a growth-investment story.
    data = fundamentals(
        years, [100] * 4, [5] * 4, [2] * 4,
        ocf=[-5, -6, -4, -8], capex=[-40] * 4, dep=[5] * 4, fcf=[-45] * 4,
    )
    assert not assess_capex_heavy(data, -45, True)["capex_heavy"]


def test_holding_company_detection():
    assert is_holding_company("Asset Management", "Bajaj Holdings is an investment company ...")
    assert not is_holding_company("Banks - Regional", "HDFC Bank provides banking services")
