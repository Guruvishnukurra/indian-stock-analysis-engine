"""
Company classification and valuation-method applicability.

Classification uses Yahoo sector/industry metadata. It never
depends on a specific ticker.
"""

from src import config
from src.routing import assess_capex_heavy, assess_cyclicality, is_holding_company
from src.utils import is_positive, is_valid, latest_valid, valid_values


# ---------------------------------------------------------
# Company types
# ---------------------------------------------------------

FINANCIAL_BALANCE_SHEET_TYPES = {"bank", "nbfc", "insurance"}
ASSET_LIGHT_FINANCIAL_TYPES = {"capital_markets", "asset_management"}
FINANCIAL_TYPES = (
    FINANCIAL_BALANCE_SHEET_TYPES
    | ASSET_LIGHT_FINANCIAL_TYPES
    | {"other_financial"}
)

# Matched against the Yahoo industry (lower case), in order.
INDUSTRY_RULES = [
    # Solar module/cell makers: capital-intensive manufacturing, not IT
    # (Yahoo files them under the Technology sector).
    ("solar", "industrial"),
    ("banks", "bank"),
    ("credit services", "nbfc"),
    ("mortgage finance", "nbfc"),
    ("financial conglomerates", "nbfc"),
    ("insurance", "insurance"),
    ("capital markets", "capital_markets"),
    ("financial data & stock exchanges", "capital_markets"),
    ("asset management", "asset_management"),
    ("auto", "automobile"),
    ("telecom", "telecom"),
    ("drug manufacturers", "pharma"),
    ("biotechnology", "pharma"),
    ("medical care", "healthcare_services"),
    ("diagnostics", "healthcare_services"),
    ("health information", "healthcare_services"),
    ("medical", "healthcare_services"),
    ("real estate", "real_estate"),
]

# Fallback when the industry is unknown or unmatched.
SECTOR_RULES = {
    "technology": "technology",
    "healthcare": "healthcare_services",
    "consumer defensive": "consumer_defensive",
    "consumer cyclical": "consumer_cyclical",
    "energy": "energy",
    "utilities": "utilities",
    "basic materials": "materials",
    "industrials": "industrial",
    "real estate": "real_estate",
    "communication services": "telecom",
    "financial services": "other_financial",
}


UNAMBIGUOUS_SECTORS = {
    "technology",
    "consumer defensive",
    "energy",
    "utilities",
    "basic materials",
    "industrials",
    "real estate",
}


# Net margin (%) below which earnings are too thin for P/E methods.
THIN_MARGIN = 3.0


def classify_company(sector=None, industry=None):
    """
    Return the company type and how certain the
    classification is.
    """

    industry_text = str(industry or "").lower()
    sector_text = str(sector or "").lower()

    for keyword, company_type in INDUSTRY_RULES:
        if keyword in industry_text:
            return {
                "company_type": company_type,
                "certainty": "High",
                "basis": f"Yahoo industry '{industry}'",
            }

    if sector_text in SECTOR_RULES:

        # For these sectors every industry gets the same
        # analytical treatment, so the sector alone is decisive.
        certainty = (
            "High"
            if sector_text in UNAMBIGUOUS_SECTORS
            else "Medium"
        )

        return {
            "company_type": SECTOR_RULES[sector_text],
            "certainty": certainty,
            "basis": f"Yahoo sector '{sector}'",
        }

    return {
        "company_type": "other",
        "certainty": "Low",
        "basis": "No usable sector/industry metadata",
    }


def get_valuation_family(company_type):

    if company_type in FINANCIAL_BALANCE_SHEET_TYPES:
        return "financial_balance_sheet"

    if company_type in ASSET_LIGHT_FINANCIAL_TYPES:
        return "asset_light_financial"

    if company_type == "other_financial":
        return "financial_balance_sheet"

    return "operating"


def normalized_fcf(fundamental_data, years=None):
    """
    Average free cash flow over the last few years.

    A single year's FCF can be distorted by capex timing or
    working-capital swings, so DCF uses this average.
    """

    values = valid_values(
        fundamental_data,
        "Free_Cash_Flow",
        last_n=years or config.DCF_FCF_NORMALIZATION_YEARS
    )

    if not values:
        return None, 0

    return sum(values) / len(values), len(values)


def earnings_quality_issue(profile, fundamental_data, quarterly_data, net_margin):
    """
    Reasons why positive earnings are not a usable base for P/E
    methods. Returns None when earnings are usable.
    """

    if not profile["positive_earnings"]:
        return None

    operating = profile["valuation_family"] == "operating"

    if operating and net_margin is not None and net_margin < THIN_MARGIN:
        return f"Earnings too thin for P/E (net margin below {THIN_MARGIN:.0f}%)."

    operating_income = latest_valid(fundamental_data, "Operating_Income")

    if operating and operating_income is not None and operating_income <= 0:
        return (
            "Profit comes from non-operating or one-off items "
            "(operating income is not positive)."
        )

    recent = [
        value for value in (
            quarterly_data["Net_Income"].dropna().tail(4).tolist()
            if quarterly_data is not None and "Net_Income" in quarterly_data
            else []
        )
    ]

    if len(recent) == 4 and sum(1 for v in recent if v < 0) >= 3:
        return (
            "Trailing profit depends on a single quarter "
            "(3 of the last 4 quarters were losses)."
        )

    return None


def assess_company_profile(
    fundamental_data,
    quarterly_data,
    sector=None,
    industry=None,
    trailing_eps=None,
    price_history_days=None,
    business_summary=None
):
    profile = {}

    # -------------------------
    # Classification
    # -------------------------

    classification = classify_company(sector, industry)

    company_type = classification["company_type"]

    profile["sector"] = sector
    profile["industry"] = industry
    profile["company_type"] = company_type
    profile["classification_certainty"] = classification["certainty"]
    profile["classification_basis"] = classification["basis"]
    profile["valuation_family"] = get_valuation_family(company_type)
    profile["financial_sector"] = company_type in FINANCIAL_TYPES

    # -------------------------
    # Earnings
    # -------------------------
    # Prefer trailing-twelve-month EPS; fall back to the
    # latest annual net income.

    if is_valid(trailing_eps):
        profile["positive_earnings"] = trailing_eps > 0
        profile["earnings_basis"] = "Trailing EPS"
    else:
        net_income = latest_valid(fundamental_data, "Net_Income")
        profile["positive_earnings"] = is_positive(net_income)
        profile["earnings_basis"] = (
            "Latest annual net income"
            if net_income is not None
            else "Unavailable"
        )

    # Barely profitable operating companies: a tiny EPS makes P/E
    # methods meaningless (a 1% margin can mean a P/E of 1,000).
    net_income = latest_valid(fundamental_data, "Net_Income")
    revenue = latest_valid(fundamental_data, "Revenue")

    net_margin = (
        net_income / revenue * 100
        if is_valid(net_income) and is_positive(revenue)
        else None
    )

    profile["net_margin"] = net_margin

    profile["earnings_issue"] = earnings_quality_issue(
        profile, fundamental_data, quarterly_data, net_margin
    )

    profile["earnings_usable"] = (
        profile["positive_earnings"] and profile["earnings_issue"] is None
    )

    # -------------------------
    # Free cash flow (normalised)
    # -------------------------

    # -------------------------
    # Business-type routing
    # -------------------------

    operating = profile["valuation_family"] == "operating"

    cycle = assess_cyclicality(industry, fundamental_data) if operating else {"cyclical": False}
    profile.update(cycle)

    # Cyclicals: average free cash flow over every available year
    # (closer to a full cycle) rather than the last three.
    fcf, fcf_years = normalized_fcf(
        fundamental_data,
        years=10 if profile.get("cyclical") else config.DCF_FCF_NORMALIZATION_YEARS,
    )

    profile["fcf_basis"] = f"average free cash flow over {fcf_years} years"

    capex = (
        assess_capex_heavy(fundamental_data, fcf, profile["earnings_usable"])
        if operating else {"capex_heavy": False}
    )
    profile.update(capex)

    if profile.get("capex_heavy"):
        fcf = capex["maintenance_fcf"]
        profile["fcf_basis"] = "maintenance free cash flow (operating cash flow - depreciation)"

    profile["holding_company"] = is_holding_company(industry, business_summary)

    profile["normalized_fcf"] = fcf
    profile["fcf_years"] = fcf_years
    profile["positive_fcf"] = is_positive(fcf)

    # -------------------------
    # Growth
    # -------------------------

    revenue_growth = latest_valid(quarterly_data, "Revenue_YoY")
    profit_growth = latest_valid(quarterly_data, "Net_Profit_YoY")

    profile["high_growth"] = (
        revenue_growth is not None and revenue_growth >= 20
    )

    profile["positive_profit_growth"] = (
        profit_growth is not None and profit_growth > 0
    )

    # -------------------------
    # History depth
    # -------------------------

    annual_years = len(valid_values(fundamental_data, "Net_Income"))

    profile["annual_years"] = annual_years
    profile["limited_history"] = annual_years < 3

    profile["newly_listed"] = (
        price_history_days is not None
        and price_history_days < 250
    )

    # -------------------------
    # Valuation method applicability
    # -------------------------

    profile.update(
        determine_method_applicability(profile)
    )

    return profile


def determine_method_applicability(profile):
    """
    Decide which valuation methods are conceptually appropriate,
    independent of whether the data is present. Each decision
    carries a reason so the report can explain exclusions.
    """

    family = profile["valuation_family"]
    positive_earnings = profile["positive_earnings"]
    earnings_usable = profile.get("earnings_usable", positive_earnings)

    thin = positive_earnings and not earnings_usable

    rules = {}

    # DCF: cash-flow-based; not meaningful for lenders/insurers
    # whose "cash flow" is driven by deposits/borrowing/float.
    if family != "operating":
        rules["dcf"] = (
            False,
            "DCF is not meaningful for financial companies "
            "(cash flows reflect lending/borrowing, not operations)."
        )
    elif not profile["positive_fcf"]:
        rules["dcf"] = (
            False,
            "DCF unavailable: normalised free cash flow is "
            "negative or missing."
        )
    else:
        rules["dcf"] = (True, "Positive normalised free cash flow.")

    # Earnings multiples require meaningful positive earnings.
    if earnings_usable:
        rules["peer_pe"] = (True, "Positive earnings.")
        rules["historical_pe"] = (True, "Positive earnings.")
    else:
        reason = (
            profile.get("earnings_issue")
            if thin
            else "P/E is meaningless with negative or missing earnings."
        )
        rules["peer_pe"] = (False, reason)
        rules["historical_pe"] = (False, reason)

    # Book-value multiples are the anchor for financials; for regulated
    # utilities, book equity approximates the regulated asset base.
    if family in ("financial_balance_sheet", "asset_light_financial"):
        rules["peer_pb"] = (True, "Book value anchors financial companies.")
    elif profile.get("company_type") == "utilities":
        rules["peer_pb"] = (
            True,
            "Regulated utility: book equity approximates the regulated asset base."
        )
    else:
        rules["peer_pb"] = (
            False,
            "P/B is not a primary method for operating companies."
        )

    # Sales multiple: weak fallback only for loss-making or barely
    # profitable operating companies.
    if family == "operating" and not earnings_usable:
        rules["peer_evs"] = (
            True,
            "Fallback when earnings are negative or not a usable base "
            "(low reliability)."
        )
    else:
        rules["peer_evs"] = (
            False,
            "Earnings-based methods are available or more appropriate."
        )

    # Growth-stage DCF: values a loss-making / barely profitable
    # operating company on the margin it could reach when mature.
    if family == "operating" and not earnings_usable:
        rules["growth_dcf"] = (
            True,
            "Path-to-profitability valuation for a company without "
            "usable earnings."
        )
    else:
        rules["growth_dcf"] = (
            False,
            "Only used when earnings are negative or not a usable base."
        )

    # Scenarios are reported separately, not blended into fair value.
    if earnings_usable:
        rules["scenario"] = (
            True,
            "Bear/base/bull earnings scenarios (reported separately)."
        )
    else:
        rules["scenario"] = (
            False,
            "Scenario valuation needs meaningful positive earnings."
        )

    applicability = {}

    for method, (applicable, reason) in rules.items():
        applicability[f"{method}_applicable"] = applicable
        applicability[f"{method}_reason"] = reason

    # Backward-compatible keys used by older code.
    applicability["pe_applicable"] = rules["peer_pe"][0]
    applicability["pb_applicable"] = rules["peer_pb"][0]
    applicability["scenario_valuation_applicable"] = rules["scenario"][0]

    return applicability
