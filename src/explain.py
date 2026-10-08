"""
Explainability: turn the analysis into reasons a person can check.

The final stance (ATTRACTIVE / WATCH / AVOID) depends only on
fundamentals, valuation and confidence. Technical, market and
news conditions are reported alongside as context and risks,
but never override the valuation view.
"""

from src import config
from src.verdicts import (
    consensus_gate,
    timing_verdict,
    valuation_verdict,
    verdict_triggers,
)
from src.utils import is_valid


def _fmt_metric(item):

    value = item["value"]

    if item["unit"] == "%":
        return f"{item['label']} {value:.1f}%"

    return f"{item['label']} {value:.2f}x"


def describe_position(fair_value, price):
    """
    Plain-language position of the price against the range AND the base,
    so 'within the range' and 'X% above base' never read as a contradiction.
    """

    position = _valuation_position(fair_value, price)

    if position is None:
        return None

    if position == "below":
        return "below the entire fair-value range"

    if position == "above":
        return "above the entire fair-value range"

    upside = fair_value["upside_base"]

    if upside <= -10:
        return "within the broad uncertainty range but above the base estimate"

    if upside >= 10:
        return "within the broad uncertainty range but below the base estimate"

    return "within the fair-value range and close to the base estimate"


def _valuation_position(fair_value, price):

    if not fair_value.get("available"):
        return None

    if price < fair_value["low"]:
        return "below"

    if price > fair_value["high"]:
        return "above"

    return "within"


def build_reasons(analysis):

    fundamental = analysis["fundamental_score"]
    fair_value = analysis["fair_value"]
    technical = analysis["technical_score"]
    market = analysis["market_score"]
    news = analysis["news"]

    bullish, not_bullish = [], []

    # Fundamentals
    for item in fundamental.get("metrics", []):

        if item["assessment"] == "Strong":
            bullish.append(f"Strong {_fmt_metric(item)}")

        elif item["assessment"] == "Weak":
            not_bullish.append(f"Weak {_fmt_metric(item)}")

    # Valuation
    if fair_value.get("available"):

        upside = fair_value["upside_base"]

        # Phrase from the fair value's side so the percentage keeps its
        # meaning: upside = fair value / price - 1.
        if upside >= 10:
            bullish.append(
                f"Base fair-value estimate is {upside:.0f}% above the price"
            )
        elif upside <= -10:
            not_bullish.append(
                f"Base fair-value estimate is {-upside:.0f}% below the price"
            )

        current_pe = analysis["inputs"].get("current_pe")
        peer_pe = analysis["peer_analysis"].get("median_pe")
        fundamental_score = analysis["fundamental_score"].get("score")

        if (
            is_valid(current_pe)
            and is_valid(peer_pe)
            and current_pe > peer_pe * 1.2
            and is_valid(fundamental_score)
            and fundamental_score >= config.STRONG_FUNDAMENTAL
        ):
            not_bullish.append(
                f"P/E {current_pe:.1f} vs peer median {peer_pe:.1f}: a premium "
                "that strong fundamentals may partly justify, which "
                "peer-median valuation does not capture"
            )

        position = _valuation_position(fair_value, analysis["current_price"])

        if position == "below":
            bullish.append("Price is below even the low end of the fair-value range")
        elif position == "above":
            not_bullish.append("Price is above even the high end of the fair-value range")

    # What the price assumes
    expectations = analysis.get("expectations", {})
    assessment = expectations.get("assessment")

    if expectations.get("available") and expectations.get("summary"):
        if assessment == "Undemanding":
            bullish.append(expectations["summary"])
        elif assessment in ("Demanding", "Very demanding"):
            not_bullish.append(expectations["summary"])

    # Scenario payoff
    scenarios = analysis.get("scenarios", {})

    if scenarios.get("available"):

        # Bull cases inherit recent high multiples and best-year
        # growth, so the payoff RATIO is optimistic by construction.
        # Only downside protection counts as a bullish reason.
        bear = scenarios["cases"]["bear"]["upside"]
        base = scenarios["cases"]["base"]["upside"]

        if bear >= -10:
            bullish.append(
                f"Limited scenario downside: bear case {bear:+.0f}% "
                f"over {scenarios['horizon_years']} years"
            )
        elif base <= -15:
            not_bullish.append(
                f"Even the base scenario is {base:+.0f}% vs the current price"
            )

    # Current market condition (context only)
    if technical.get("label") == "Strong":
        bullish.append("Positive technical momentum")
    elif technical.get("label") == "Weak":
        not_bullish.append("Weak technical trend")

    if market.get("label") == "Strong":
        bullish.append("Outperforming market/sector")
    elif market.get("label") == "Weak":
        not_bullish.append("Underperforming market/sector")

    # News (sentiment is context, not a signal)
    news_score = news.get("news_score")

    if is_valid(news_score):
        if news_score >= 60:
            bullish.append("Recent news sentiment is positive")
        elif news_score <= 40:
            not_bullish.append("Recent news sentiment is negative")

    return bullish, not_bullish


def build_risks(analysis):

    risks = []

    profile = analysis["company_profile"]
    metrics = analysis["fundamental_metrics"]["values"]
    method_results = analysis["method_results"]
    fair_value = analysis["fair_value"]
    context = analysis["market_context"]

    revenue_growth = metrics.get("revenue_growth")
    profit_growth = metrics.get("profit_growth")

    if is_valid(profit_growth) and profit_growth < 0:
        risks.append(f"Earnings declining ({profit_growth:.1f}% YoY)")

    if is_valid(revenue_growth) and revenue_growth < 0:
        risks.append(f"Revenue declining ({revenue_growth:.1f}% YoY)")

    if not profile.get("positive_earnings"):
        risks.append("Company is not currently profitable")
    elif profile.get("earnings_issue"):
        risks.append("Earnings quality: " + profile["earnings_issue"])

    family = profile.get("valuation_family")

    debt_to_equity = metrics.get("debt_to_equity")

    if (
        family == "operating"
        and is_valid(debt_to_equity)
        and debt_to_equity > 1.5
    ):
        risks.append(f"High leverage (debt/equity {debt_to_equity:.2f}x)")

    leverage = metrics.get("leverage")

    if (
        profile.get("company_type") == "nbfc"
        and is_valid(leverage)
        and leverage > 8
    ):
        risks.append(f"High balance-sheet leverage (assets/equity {leverage:.1f}x)")

    dcf = method_results.get("dcf", {})

    if dcf.get("available") and dcf["base"] > 0:

        width = (dcf["high"] - dcf["low"]) / dcf["base"]

        if width > 0.4:
            risks.append(
                "DCF value is highly sensitive to growth and "
                "discount-rate assumptions"
            )

    fcf_conversion = metrics.get("fcf_conversion")

    if (
        dcf.get("available")
        and is_valid(fcf_conversion)
        and fcf_conversion < 0.5
    ):
        risks.append(
            f"Low FCF conversion ({fcf_conversion:.2f}x net income): DCF may "
            "understate value if capex is growth investment"
        )

    if fair_value.get("widened_for_disagreement"):
        risks.append(
            "Valuation methods disagree; the range was widened to reflect it"
        )

    sector_return = context.get("sector_return")

    if is_valid(sector_return) and sector_return < -5:
        risks.append(
            f"Sector basket fell {abs(sector_return):.1f}% (absolute) over "
            f"{context.get('window', 30)} days"
        )

    beta = analysis.get("beta")

    if is_valid(beta) and beta > 1.3:
        risks.append(f"High market sensitivity (beta {beta:.2f})")

    scenarios = analysis.get("scenarios", {})

    if scenarios.get("available"):

        bear = scenarios["cases"]["bear"]

        if bear["upside"] <= -30:
            risks.append(
                f"Bear case ({bear['growth'] * 100:.0f}% growth, "
                f"{bear['exit_pe']:.0f}x exit P/E) implies "
                f"{bear['upside']:.0f}% over {scenarios['horizon_years']} years"
            )

    position = profile.get("cycle_position")

    if position == "peak":
        risks.append(
            "Cyclical near a peak: current margin "
            f"{profile['current_operating_margin']:.1f}% vs mid-cycle "
            f"{profile['mid_cycle_operating_margin']:.1f}%; a low P/E on peak "
            "earnings can be a trap"
        )
    elif position == "trough":
        risks.append(
            "Cyclical near a trough: current margin "
            f"{profile['current_operating_margin']:.1f}% vs mid-cycle "
            f"{profile['mid_cycle_operating_margin']:.1f}%; trailing P/E "
            "overstates how expensive it is"
        )

    dcf_result = method_results.get("dcf", {})
    terminal_share = dcf_result.get("terminal_share")

    if dcf_result.get("available") and terminal_share and terminal_share > 0.70:
        risks.append(
            f"{terminal_share * 100:.0f}% of the DCF value comes from the "
            "terminal value (beyond year 10): highly assumption-dependent"
        )

    liquidity = analysis.get("liquidity") or {}

    if liquidity.get("illiquid"):
        risks.append(
            f"Illiquid: median daily traded value about Rs "
            f"{liquidity['median_traded_value'] / 1e7:,.1f} crore over "
            f"{liquidity['days']} days; prices are easier to move and "
            "harder to exit"
        )

    company_type = profile.get("company_type")

    if company_type in EXPORTER_TYPES:
        risks.append(
            "Rupee sensitivity: largely export revenue, so a stronger rupee "
            "would cut earnings (a weak-rupee tailwind can reverse)"
        )

    if profile.get("cyclical") or company_type in ("energy", "materials"):
        risks.append(
            "Commodity sensitivity: earnings move with input/output commodity "
            "prices (e.g. crude, metals, coal)"
        )

    events = (analysis.get("news") or {}).get("events") or {}

    for item in events.get("risks", [])[:2]:
        risks.append(f"News event: {item}")

    if profile.get("newly_listed"):
        risks.append("Recently listed: limited trading history")

    return risks


def build_data_limitations(analysis):

    limitations = list(analysis.get("warnings", []))

    company_type = analysis["company_profile"].get("company_type")

    if company_type in ("bank", "nbfc"):
        limitations.append(
            "Asset quality (GNPA/NNPA), capital adequacy and provision "
            "coverage are not available from the current data source"
        )

    if company_type == "insurance":
        limitations.append(
            "Embedded value (P/EV) is not available; valuation uses P/E and P/B"
        )

    profile = analysis["company_profile"]

    for key in ("cyclical_note", "capex_note"):
        if profile.get(key):
            limitations.append(profile[key])

    if profile.get("holding_company"):
        limitations.append(
            "Holding/investment company: sum-of-the-parts with a holding "
            "discount is needed and is not implemented"
        )

    if company_type == "real_estate":
        limitations.append(
            "Real estate: developers are best valued on net asset value of "
            "land bank and projects (not implemented); earnings are lumpy"
        )

    if company_type == "pharma":
        limitations.append(
            "Pharma: the product pipeline and US generic pricing are not modelled"
        )

    missing = analysis["fundamental_score"].get("missing", [])

    if missing:
        limitations.append("Unavailable metrics: " + ", ".join(missing))

    return limitations


MIN_METHODS = 2

# Business types whose revenue is mostly in foreign currency.
EXPORTER_TYPES = {"technology", "pharma"}


def not_rated_reason(analysis):
    profile = analysis["company_profile"]
    fair_value = analysis["fair_value"]

    if (
        profile.get("valuation_family") == "operating"
        and not profile.get("earnings_usable", True)
    ):
        return (
            "No buy/avoid verdict: the company has no usable earnings, so its "
            "value depends on the margin it reaches once mature, which can "
            "only be assumed. The fair-value range below is assumption-driven "
            "and wide."
        )

    gate = consensus_gate(fair_value, analysis.get("inputs") or {})

    if (
        gate
        and profile.get("earnings_usable", True)
        and not profile.get("holding_company")
        and len(fair_value.get("methods_used", [])) >= MIN_METHODS
    ):
        return "No buy/avoid verdict: " + gate

    if profile.get("holding_company"):
        return (
            "No buy/avoid verdict: this looks like a holding/investment "
            "company, whose value lies in its stakes and needs a "
            "sum-of-the-parts valuation (not implemented). Multiples below "
            "are indicative only."
        )

    return (
        f"No buy/avoid verdict: only {len(fair_value.get('methods_used', []))} "
        f"valuation method could be applied; at least {MIN_METHODS} are "
        "required to cross-check a fair value."
    )


def determine_stance(analysis):
    """
    ATTRACTIVE / WATCH / AVOID / NOT RATED / INSUFFICIENT DATA

    Based on valuation upside, fundamental quality and confidence.

    NOT RATED: operating companies without usable earnings (loss-making
    or barely profitable). Their value hinges on a future margin the
    engine can only assume, so it reports what the price requires
    instead of a verdict.
    """

    fair_value = analysis["fair_value"]
    confidence = analysis["confidence"]["score"]
    fundamental = analysis["fundamental_score"].get("score")
    profile = analysis["company_profile"]


    if (
        not fair_value.get("available")
        or confidence < config.MIN_CONFIDENCE_FOR_STANCE
    ):
        return "INSUFFICIENT DATA"

    if (
        profile.get("valuation_family") == "operating"
        and not profile.get("earnings_usable", True)
    ):
        return "NOT RATED"

    # Holding companies need a sum-of-the-parts valuation.
    if profile.get("holding_company"):
        return "NOT RATED"

    # A fair value far from analyst consensus means the model's methods
    # likely do not fit this company.
    if consensus_gate(fair_value, analysis.get("inputs") or {}):
        return "NOT RATED"

    # Never issue a verdict on a single method.
    if len(fair_value.get("methods_used", [])) < MIN_METHODS:
        return "NOT RATED"

    upside = fair_value["upside_base"]

    # Expensive, but fundamentally strong: "quality at a premium".
    # Peer-median multiples systematically understate franchises
    # that deserve a premium, so this is WATCH, not AVOID.
    if upside <= config.AVOID_MAX_UPSIDE:
        if is_valid(fundamental) and fundamental >= config.STRONG_FUNDAMENTAL:
            return "WATCH"
        return "AVOID"

    if (
        is_valid(fundamental)
        and fundamental < config.WEAK_FUNDAMENTAL
        and upside < config.ATTRACTIVE_MIN_UPSIDE
    ):
        return "AVOID"

    if (
        upside >= config.ATTRACTIVE_MIN_UPSIDE
        and is_valid(fundamental)
        and fundamental >= config.ATTRACTIVE_MIN_FUNDAMENTAL
        and confidence >= config.ATTRACTIVE_MIN_CONFIDENCE
    ):
        return "ATTRACTIVE"

    return "WATCH"


def build_interpretation(analysis, stance):

    sentences = []

    fundamental = analysis["fundamental_score"]
    fair_value = analysis["fair_value"]

    if stance == "NOT RATED":
        expectations = analysis.get("expectations") or {}
        sentences.append(not_rated_reason(analysis))
        if expectations.get("summary"):
            sentences.append(expectations["summary"])

    if fundamental.get("score") is not None:
        sentences.append(
            f"Fundamental quality is {fundamental['label'].lower()} "
            f"({fundamental['score']:.0f}/100) on "
            f"{analysis['company_profile']['company_type'].replace('_', ' ')} metrics."
        )
    else:
        sentences.append("Fundamental quality could not be scored reliably.")

    position = describe_position(fair_value, analysis["current_price"])

    if position is not None:
        methods = ", ".join(fair_value["methods_used"])
        sentences.append(
            f"The price is {position} (methods: {methods})."
        )
    else:
        sentences.append(
            "No reliable fair-value estimate could be produced."
        )

    technical = analysis["technical_score"].get("label", "Unavailable")
    market = analysis["market_score"].get("label", "Unavailable")

    sentences.append(
        f"Current market condition: technical {technical.lower()}, "
        f"market/sector {market.lower()}."
    )

    confidence = analysis["confidence"]

    sentences.append(
        f"Overall: {stance} (confidence {confidence['label'].upper()}, "
        f"{confidence['score']}/100)."
    )

    sentences.append(
        "This is an analytical assessment, not a guaranteed prediction "
        "or investment advice."
    )

    return " ".join(sentences)


def explain(analysis):

    bullish, not_bullish = build_reasons(analysis)

    stance = determine_stance(analysis)

    verdicts = {
        "quality": analysis["fundamental_score"].get("label", "Unavailable"),
        "valuation": valuation_verdict(
            analysis["fair_value"], analysis["current_price"]
        ),
        "timing": timing_verdict(
            analysis["technical_score"],
            analysis["latest_technical"]
            if analysis.get("latest_technical") is not None else {},
        ),
        "triggers": verdict_triggers(
            analysis["fair_value"], analysis["current_price"], stance
        ),
    }

    return {
        "stance": stance,
        "verdicts": verdicts,
        "why_bullish": bullish,
        "why_not_bullish": not_bullish,
        "risks": build_risks(analysis),
        "data_limitations": build_data_limitations(analysis),
        "interpretation": build_interpretation(analysis, stance),
    }
