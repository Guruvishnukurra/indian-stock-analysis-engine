"""
Plain-text report. Every value may be missing; nothing here
should ever raise on None.
"""

import sys

from src.utils import is_valid, round_price


WIDTH = 60


def _money(value):
    if is_valid(value) and value <= 0:
        return "₹0"          # e.g. a bear case where debt/losses exceed value

    rounded = round_price(value) if is_valid(value) else None

    if rounded is None:
        return "Unavailable"

    # Whole rupees unless the rounding step itself is fractional.
    if rounded == int(rounded):
        return f"₹{rounded:,.0f}"

    return f"₹{rounded:,.2f}".rstrip("0")


def _pct(value, signed=True):
    if not is_valid(value):
        return "Unavailable"
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def _score(value):
    return f"{value:.0f}/100" if is_valid(value) else "Unavailable"


def _num(value, digits=2):
    return f"{value:.{digits}f}" if is_valid(value) else "Unavailable"


def _section(title):
    print()
    print(title)
    print("-" * WIDTH)


def _bullets(items, marker):
    if not items:
        print(f"  {marker} None")
    for item in items:
        print(f"  {marker} {item}")


def print_header(analysis):
    print("=" * WIDTH)
    print(f"{analysis['company_name']} ({analysis['ticker']}) — STOCK ANALYSIS")
    print("=" * WIDTH)

    profile = analysis["company_profile"]

    print(f"Sector / industry : {analysis['sector']} / {analysis['industry']}")
    print(
        f"Analysed as       : {profile['company_type'].replace('_', ' ')} "
        f"(classification certainty: {profile['classification_certainty']})"
    )
    print(f"Current price     : ₹{analysis['current_price']:,.2f}")


def print_scores(analysis):
    scores = analysis["scores"]

    _section("QUALITY + VALUE")
    print(f"Quality + Value     : {_score(scores['quality_value'])}")
    print(
        f"Fundamental quality : {_score(scores['fundamental'])} "
        f"({analysis['fundamental_score']['label']})"
    )
    print(
        f"Valuation           : {_score(scores['valuation'])} "
        f"(basis: {scores['valuation_basis']})"
    )


def print_fair_value(analysis):
    fair_value = analysis["fair_value"]
    confidence = analysis["confidence"]

    _section("FAIR VALUE")

    if not fair_value.get("available"):
        print(f"Unavailable — {fair_value.get('reason')}")
    else:
        print(
            f"Estimated range : {_money(fair_value['low'])} – "
            f"{_money(fair_value['high'])}"
        )
        print(f"Base estimate   : {_money(fair_value['base'])}")

        from src.explain import describe_position

        print(
            f"Price position  : "
            f"{describe_position(fair_value, analysis['current_price'])}"
        )

        dispersion = fair_value.get("dispersion") or {}

        if dispersion.get("coefficient_of_variation") is not None:
            spread = ", ".join(
                f"{label} {_pct(upside)}"
                for label, upside in fair_value["method_upsides"].items()
            )
            print(
                f"Method spread   : {dispersion['coefficient_of_variation'] * 100:.0f}% "
                f"dispersion ({spread} vs price)"
            )

        for label, context in fair_value.get("context_methods", {}).items():
            print(
                f"Context only    : {label} {_money(context['base'])} "
                f"({_pct(context['upside'])} vs price; not in base or range)"
            )
        print(
            f"Potential upside: {_pct(fair_value['upside_low'])} to "
            f"{_pct(fair_value['upside_high'])} "
            f"(base {_pct(fair_value['upside_base'])})"
        )

    print(f"Confidence      : {confidence['label']} — {confidence['score']}/100")

    inputs = analysis.get("inputs", {})

    if is_valid(inputs.get("consensus_target")):
        print(
            f"Analyst consensus (reference only, not used): "
            f"{_money(inputs['consensus_target'])} "
            f"({inputs.get('analyst_count') or '?'} analysts)"
        )

    if confidence["reasons"]:
        print("Reasons:")
        _bullets(confidence["reasons"], "✓")

    if confidence["concerns"]:
        print("Concerns:")
        _bullets(confidence["concerns"], "⚠")


def print_valuation_breakdown(analysis):
    results = analysis["method_results"]
    weights = analysis["fair_value"].get("weights_used", {})

    _section("VALUATION BREAKDOWN")

    labels = {
        "dcf": "DCF",
        "peer_pe": "Peer P/E",
        "historical_pe": "Historical P/E",
        "peer_pb": "Peer P/B",
        "peer_evs": "Peer EV/Sales",
        "growth_dcf": "Growth DCF",
    }

    for method, label in labels.items():

        result = results.get(method, {})

        if result.get("available"):
            weight = weights.get(method, 0) * 100
            print(
                f"{label:<15}: {_money(result['base'])} "
                f"(range {_money(result['low'])} – {_money(result['high'])}, "
                f"weight {weight:.0f}%)"
            )
            print(f"{'':<17}{result.get('range_basis', '')}")
        else:
            print(f"{label:<15}: — {result.get('reason', 'Unavailable')}")

    growth = results.get("growth_dcf", {})

    if growth.get("available"):

        a = growth["assumptions"]
        peers = a["peer_margins"]

        print()
        print(
            f"Growth-stage DCF: revenue growth starts at {a['start_growth'] * 100:.0f}% "
            f"and fades over {a['years']} years; operating margin moves from "
            f"{a['current_margin'] * 100:.1f}% to the mature target; WACC "
            f"{a['wacc'] * 100:.1f}%"
        )
        print(
            f"Mature margin targets from {peers['count']} peers: "
            f"bear {peers['low']:.1f}% / base {peers['median']:.1f}% / "
            f"bull {peers['high']:.1f}%"
        )

        for name, case in growth["cases"].items():
            print(
                f"  {name.title():<5} growth {case['start_growth'] * 100:4.0f}%  "
                f"target margin {case['target_margin'] * 100:5.1f}%  "
                f"-> {_money(case['value'])}"
            )

    dcf = results.get("dcf", {})

    if dcf.get("available"):

        a = dcf["assumptions"]

        print()
        print(
            f"DCF assumptions: growth {a['growth'] * 100:.1f}% "
            f"({a['growth_basis']}), WACC {a['wacc'] * 100:.1f}%, "
            f"terminal growth {a['terminal_growth'] * 100:.1f}%"
        )
        print("DCF sensitivity (₹ per share):")
        print(dcf["sensitivity"].map(
            lambda v: f"{round_price(v):,.0f}" if is_valid(v) else "n/a"
        ).to_string())


def print_expectations(analysis):
    expectations = analysis.get("expectations", {})

    _section("WHAT THE PRICE ASSUMES")

    if not expectations.get("available"):
        print(f"Unavailable — {expectations.get('reason')}")
        return

    print(f"Method     : {expectations['method']}")
    print(f"Assessment : {expectations.get('assessment')}")

    if expectations.get("summary"):
        print(expectations["summary"])


def print_scenarios(analysis):
    scenarios = analysis.get("scenarios", {})

    _section(f"SCENARIOS ({scenarios.get('horizon_years', 3)}-YEAR, VALUE TODAY)")

    if not scenarios.get("available"):
        print(f"Unavailable — {scenarios.get('reason')}")
        return

    print(f"{'':<6}{'Growth':>9}{'Exit P/E':>10}{'Value':>12}{'vs price':>11}")

    for name in ("bear", "base", "bull"):
        case = scenarios["cases"][name]
        print(
            f"{name.title():<6}{case['growth'] * 100:>8.1f}%"
            f"{case['exit_pe']:>9.1f}x{_money(case['value']):>12}"
            f"{_pct(case['upside']):>11}"
        )

    print(f"Payoff     : {scenarios['payoff_summary']}")
    print(f"Growth     : {scenarios['growth_basis']}")
    print(f"Exit P/E   : {scenarios['multiple_basis']} ranges")
    print(
        f"Discount   : cost of equity {scenarios['cost_of_equity'] * 100:.1f}%. "
        f"{scenarios['note']}"
    )

    if scenarios.get("limited_history"):
        print("⚠ Fewer than 3 years of growth history: scenarios are thin.")


def print_fundamentals(analysis):
    fundamental = analysis["fundamental_score"]

    _section(
        f"FUNDAMENTALS ({analysis['company_profile']['company_type'].replace('_', ' ')} metrics)"
    )

    for item in fundamental.get("metrics", []):

        value = (
            f"{item['value']:.1f}%"
            if item["unit"] == "%"
            else f"{item['value']:.2f}x"
        )

        print(
            f"{item['label']:<32}: {value:>9}  "
            f"[{item['assessment']}, {item['score']:.0f}/100]"
        )

    if fundamental.get("missing"):
        print("Unavailable: " + ", ".join(fundamental["missing"]))


def print_market_condition(analysis):
    technical = analysis["technical_score"]
    market = analysis["market_score"]
    context = analysis["market_context"]
    latest = analysis["latest_technical"]

    _section("CURRENT MARKET CONDITION")

    print(f"Technical          : {technical['label']} ({_score(technical['score'])})")
    print(f"RSI (14)           : {_num(latest.get('RSI_14'), 1)}")
    print(f"30D return         : {_pct(context.get('stock_return'))}")
    print(f"vs NIFTY (30D)     : {_pct(context.get('relative_to_market'))}")
    print(
        f"vs sector (30D)    : {_pct(context.get('relative_to_sector'))} "
        f"[{analysis['sector_benchmark']['name']}]"
    )
    print(f"Beta vs NIFTY      : {_num(analysis.get('beta'))}")
    print(f"Market/sector      : {market['label']} ({_score(market['score'])})")

    for _, text in technical.get("signals", []):
        print(f"  • {text}")


def print_news(analysis):
    news = analysis["news"]

    _section("NEWS")

    print(f"Sentiment     : {news.get('label')}")
    print(f"News score    : {_score(news.get('news_score'))}")

    if news.get("sentiment_basis"):
        print(f"Scored on     : {news['sentiment_basis']}")

    print(
        f"Articles      : {news.get('raw_article_count', news.get('article_count', 0))} fetched, "
        f"{news.get('duplicates_removed', 0)} duplicates removed"
    )

    events = news.get("events")

    if events:
        noise = events.get("noise_share")
        if noise is not None:
            print(
                f"Material events: {events['material_share'] * 100:.0f}% of headlines; "
                f"{noise * 100:.0f}% were price-move commentary or off-topic"
            )
        print("Key catalysts:")
        _bullets(events["catalysts"], "+")
        print("Key event risks:")
        _bullets(events["risks"], "-")
        if events.get("other_material"):
            print("Other material events (no clear direction):")
            _bullets(events["other_material"], "·")
        print(f"({events['accuracy_note']})")

    if not events and news.get("top_positive"):
        print("Most positive headlines:")
        _bullets(news["top_positive"], "+")

    if not events and news.get("top_negative"):
        print("Most negative headlines:")
        _bullets(news["top_negative"], "-")

    print("Note: sentiment is context, not a trading signal.")

    events = news.get("events")

    if events is None and news.get("label") not in ("Not requested",):
        print("Event tagging unavailable (local LLM not running).")


def print_ml(analysis):
    ml = analysis["ml_trend"]

    _section("ML TREND OUTLOOK")

    if not ml.get("available"):
        print(f"ML Trend: Unavailable — {ml.get('reason')}")
        return

    print(
        f"{ml['horizon_trading_days']}-trading-day trend: {ml['trend'].upper()}"
    )

    for label, probability in ml["probabilities"].items():
        print(f"  {label:<8}: {probability * 100:.0f}%")

    print(f"Validation: {ml['evidence']}")
    print("The trend model never overrides the valuation view.")


def print_interpretation(analysis):
    explanation = analysis["explanation"]

    _section("WHY BULLISH")
    _bullets(explanation["why_bullish"], "+")

    _section("WHY NOT BULLISH")
    _bullets(explanation["why_not_bullish"], "-")

    _section("RISKS")
    _bullets(explanation["risks"], "⚠")

    thesis = analysis.get("thesis") or {}

    if thesis.get("available"):
        _section("AI-WRITTEN THESIS (numbers verified)")
        print(thesis["text"])
        print(f"({thesis['note']})")

    _section("FINAL INTERPRETATION")
    print(f"Overall: {explanation['stance']}")
    print()
    print(explanation["interpretation"])

    if explanation["data_limitations"]:
        _section("DATA LIMITATIONS")
        _bullets(explanation["data_limitations"], "·")


def _ensure_unicode_output():
    """
    Windows consoles often default to a code page without the rupee
    sign, which would crash printing. Switch stdout to UTF-8 where
    supported (Jupyter's stream already handles Unicode).
    """

    try:
        if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def generate_report(analysis):

    _ensure_unicode_output()

    if analysis.get("status") != "ok":
        print(f"{analysis['ticker']}: analysis failed — {analysis.get('reason')}")
        return

    print_header(analysis)
    print_scores(analysis)
    print_fair_value(analysis)
    print_valuation_breakdown(analysis)
    print_expectations(analysis)
    print_scenarios(analysis)
    print_fundamentals(analysis)
    print_market_condition(analysis)
    print_news(analysis)
    print_ml(analysis)
    print_interpretation(analysis)

    print()
    print("=" * WIDTH)
