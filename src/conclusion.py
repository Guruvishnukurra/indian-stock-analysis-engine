"""
Bottom-line conclusion: one or two plain sentences saying what the
analysis means.

Built from the engine's own numbers with fixed templates (no language
model), so every figure is exact and relationships cannot be reversed.
The template depends on the situation: pre-profit growth company,
holding company, model misfit (far from consensus), or a rated stock.
"""

from src.utils import is_valid


def _money(value):
    if not is_valid(value):
        return "n/a"
    return f"₹{value:,.0f}" if value >= 100 else f"₹{value:,.2f}"


def _growth_phrase(growth):

    if not is_valid(growth):
        return None
    if growth > 40:
        return f"growing extremely fast (revenue +{growth:.0f}% year on year)"
    if growth > 20:
        return f"growing fast (revenue +{growth:.0f}% year on year)"
    if growth > 8:
        return f"growing steadily (revenue +{growth:.0f}% year on year)"
    if growth > 0:
        return f"growing slowly (revenue +{growth:.0f}% year on year)"
    return f"shrinking (revenue {growth:.0f}% year on year)"


def _quality_phrase(fundamental):

    label = fundamental.get("label")

    strong = sorted(
        (m for m in fundamental.get("metrics", []) if m["assessment"] == "Strong"),
        key=lambda m: -m["score"],
    )[:2]

    evidence = ", ".join(
        f"{m['label'].lower()} {m['value']:.0f}{'%' if m['unit'] == '%' else 'x'}"
        for m in strong
    )

    if label == "Strong":
        phrase = "a high-quality business"
    elif label == "Moderate":
        phrase = "a reasonably sound business"
    elif label == "Weak":
        phrase = "a business with weak fundamentals"
    else:
        return "a business whose quality could not be scored"

    return f"{phrase} ({evidence})" if evidence and label != "Weak" else phrase


def _growth_company(analysis, name, price):

    metrics = analysis["fundamental_metrics"]["values"]
    growth_dcf = analysis["method_results"].get("growth_dcf", {})
    implied = growth_dcf.get("implied_margin")
    peers = growth_dcf.get("assumptions", {}).get("peer_margins") or {}

    growth = _growth_phrase(metrics.get("revenue_growth")) or "growing"

    opening = f"{name} is {growth} but is not yet profitable."

    if implied is None or not peers:
        return (
            f"{opening} Its value depends on the profit margin it reaches once "
            "mature, which the model cannot pin down, so it gives no verdict."
        )

    if implied > peers["high"] * 1.25:
        judgement = "a level the model considers unrealistic"
    elif implied > peers["high"]:
        judgement = "a level the model considers very demanding"
    elif implied > peers["median"]:
        judgement = "an achievable but above-average level"
    else:
        judgement = "a level that looks achievable"

    base = analysis["fair_value"].get("base")

    caution = (
        f"The model cannot establish that {name} is worth {_money(base)}; "
        if is_valid(base) else ""
    )

    text = (
        f"{opening} {caution}what it does establish is that {_money(price)} "
        f"requires the company to eventually earn an operating margin of about "
        f"{implied:.0f}%, versus {peers['low']:.0f}-{peers['high']:.0f}% for "
        f"established profitable peers: {judgement}, i.e. exceptionally strong "
        "long-term execution."
    )

    simulation = growth_dcf.get("simulation") or {}

    if simulation:
        share = simulation["share_justifying_price"]
        text += (
            f" {share * 100:.0f}% of {simulation['runs']:,} simulated futures "
            "based on real peers' margins justify the current price."
            if share > 0 else
            f" None of {simulation['runs']:,} simulated futures based on real "
            "peers' margins justify the current price."
        )

    funding = growth_dcf.get("funding") or {}

    if funding.get("funding_gap") and funding.get("gap_share_of_market_cap"):
        text += (
            f" It also likely needs new funding of roughly "
            f"{funding['gap_share_of_market_cap'] * 100:.0f}% of its market cap "
            "before turning cash-positive (dilution risk)."
        )

    return text


def _rated(analysis, name, price, stance):

    fair_value = analysis["fair_value"]
    verdicts = analysis["explanation"]["verdicts"]
    quality = _quality_phrase(analysis["fundamental_score"])
    valuation = verdicts["valuation"]["label"]
    timing = verdicts["timing"]["label"]

    value_text = (
        f"the model's fair-value estimate of {_money(fair_value['base'])} "
        f"(range {_money(fair_value['low'])}-{_money(fair_value['high'])})"
    )

    if valuation == "Undervalued":
        core = f"{name} is {quality} trading below {value_text}"
    elif valuation == "Overvalued":
        joiner = "but" if "weak" not in quality else "and"
        core = (
            f"{name} is {quality}, {joiner} at {_money(price)} the price is above "
            f"{value_text}"
        )
    else:
        core = f"{name} is {quality} trading close to {value_text}"

    if timing == "Weak":
        tail = "; the short-term price trend is weak."
    elif timing == "Strong":
        tail = "; the short-term price trend is strong."
    else:
        tail = "."

    verdict = {
        "ATTRACTIVE": "On these numbers the stock looks attractive",
        "WATCH": "On these numbers it is one to watch rather than act on",
        "AVOID": "On these numbers the valuation does not offer a margin of safety",
    }[stance]

    return f"{core}{tail} {verdict}."


def build_conclusion(analysis):

    name = analysis.get("company_name") or analysis.get("ticker")
    price = analysis.get("current_price")
    profile = analysis["company_profile"]
    explanation = analysis["explanation"]
    stance = explanation["stance"]

    if stance == "INSUFFICIENT DATA":
        return (
            f"There is not enough reliable data to value {name}, so the model "
            "gives no verdict."
        )

    if stance == "NOT RATED":

        if (
            profile.get("valuation_family") == "operating"
            and not profile.get("earnings_usable", True)
        ):
            return _growth_company(analysis, name, price)

        if profile.get("holding_company"):
            return (
                f"{name} is a holding/investment company: its value lies in the "
                "stakes it owns, which needs a sum-of-the-parts valuation the "
                "model does not do, so it gives no verdict."
            )

        consensus = (analysis.get("inputs") or {}).get("consensus_target")
        base = analysis["fair_value"].get("base")

        if is_valid(consensus) and is_valid(base):
            return (
                f"The model's methods do not seem to fit {name}: its fair-value "
                f"estimate ({_money(base)}) is far from the analyst consensus "
                f"({_money(consensus)}), likely because the market prices in "
                "something the model cannot capture (such as a long growth "
                "runway), so it gives no verdict."
            )

        return (
            f"Too few valuation methods apply to {name} to cross-check a fair "
            "value, so the model gives no verdict."
        )

    return _rated(analysis, name, price, stance)
