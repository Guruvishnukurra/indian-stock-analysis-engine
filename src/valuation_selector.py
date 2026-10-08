from src import config
from src.fair_value import METHOD_LABELS


def get_valuation_weights(company_profile):
    """
    Method weights for the company's valuation family.
    Weights are renormalised later over available methods.
    """

    family = company_profile.get("valuation_family", "operating")

    if family == "financial_balance_sheet":
        return dict(config.FINANCIAL_BALANCE_SHEET_WEIGHTS)

    if family == "asset_light_financial":
        return dict(config.ASSET_LIGHT_FINANCIAL_WEIGHTS)

    if not company_profile.get(
        "earnings_usable", company_profile.get("positive_earnings", False)
    ):
        return dict(config.LOSS_MAKING_WEIGHTS)

    return dict(config.OPERATING_WEIGHTS)


def select_valuation_methods(
    company_profile,
    method_results
):
    """
    A method is selected only if it is:

    1. Appropriate for the company profile, and
    2. Actually produced a value from available data.

    Every exclusion carries a reason.
    """

    selected_methods = []
    excluded_methods = {}

    for method, label in METHOD_LABELS.items():

        if not company_profile.get(f"{method}_applicable", False):
            excluded_methods[label] = company_profile.get(
                f"{method}_reason",
                "Not appropriate for company profile."
            )
            continue

        result = method_results.get(method)

        if result is None:
            excluded_methods[label] = "Not computed."
            continue

        if result.get("available"):
            selected_methods.append(label)
        else:
            excluded_methods[label] = result.get(
                "reason", "Required data unavailable."
            )

    return {
        "selected_methods": selected_methods,
        "excluded_methods": excluded_methods
    }
