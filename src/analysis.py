"""
Analysis orchestrator.

Pipeline (each stage is failure-tolerant):

    data -> fundamentals -> company profile -> peers
         -> technical -> market/sector context
         -> valuation methods -> fair-value range
         -> scores -> confidence -> news -> ML trend
         -> explanation

A missing metric makes a method unavailable and lowers
confidence; it never crashes the analysis.
"""

from src import config
from src.benchmarks import select_sector_benchmark
from src.company_profile import assess_company_profile
from src.confidence import calculate_confidence
from src.data import fetch_company_data, fetch_index_history
from src.data_quality import (
    calculate_data_quality_score,
    check_data_consistency,
)
from src.expectations import market_implied_expectations
from src.explain import explain
from src.fair_value import build_fair_value_range
from src.fundamentals import post_break_data, prepare_fundamental_data
from src.growth_stage import growth_stage_valuation
from src.periods import build_ttm, fy_label, normalized_eps, quarter_label
from src.market import (
    calculate_beta,
    calculate_correlation,
    calculate_market_features,
    summarize_market_context,
)
from src.ml_trend import get_ml_trend
from src.news import analyze_news
from src.peer_selection import build_peer_analysis, get_peer_financials
from src.ownership import ownership_lookup
from src.peer_universe import get_peer_tickers
from src.quarterly import build_quarterly_fundamentals
from src.scenarios import run_scenarios
from src.scoring import (
    calculate_fundamental_score,
    calculate_market_sector_score,
    calculate_quality_value_score,
    calculate_technical_score,
    calculate_valuation_score,
    extract_fundamental_metrics,
)
from src.technical import calculate_technical_features
from src.thesis import write_thesis
from src.utils import is_positive, latest_valid, latest_valid_dated, safe_float
from src.valuation import (
    ev_sales_valuation,
    historical_pe_valuation,
    peer_multiple_valuation,
    roe_adjusted_pb_valuation,
    run_dcf,
)
from src.valuation_selector import (
    get_valuation_weights,
    select_valuation_methods,
)


MAX_PEER_CANDIDATES = 25


# =========================================================
# STAGES
# =========================================================

def _run_safely(stage, warnings, default, *args, **kwargs):
    """Run one stage; on failure record a warning and continue."""

    try:
        return stage(*args, **kwargs)
    except Exception as error:
        warnings.append(f"{stage.__name__} failed: {error}")
        return default


def get_market_inputs(info, fundamental_data, latest_price):
    """
    Per-share inputs, with fallbacks derived from statements.
    """

    shares = (
        safe_float(info.get("sharesOutstanding"))
        or safe_float(info.get("impliedSharesOutstanding"))
    )

    trailing_eps = safe_float(info.get("trailingEps"))

    if trailing_eps is None:
        trailing_eps = latest_valid(fundamental_data, "EPS")

    if shares is None:
        net_income = latest_valid(fundamental_data, "Net_Income")
        eps = latest_valid(fundamental_data, "EPS")
        if is_positive(net_income) and is_positive(eps):
            shares = net_income / eps

    market_cap = safe_float(info.get("marketCap"))

    if market_cap is None and shares is not None:
        market_cap = latest_price * shares

    book_value_per_share = safe_float(info.get("bookValue"))

    equity = latest_valid(fundamental_data, "Equity")

    if book_value_per_share is None and is_positive(equity) and shares:
        book_value_per_share = equity / shares

    # Trailing-twelve-month revenue, else the latest fiscal year.
    revenue = (
        safe_float(info.get("totalRevenue"))
        or latest_valid(fundamental_data, "Revenue")
    )

    debt = latest_valid(fundamental_data, "Debt")
    cash = latest_valid(fundamental_data, "Cash_And_Investments")

    if debt is None and cash is None:
        net_debt = None
    else:
        net_debt = (debt or 0.0) - (cash or 0.0)

    roe = latest_valid(fundamental_data, "ROE")

    if roe is None and safe_float(info.get("returnOnEquity")) is not None:
        roe = info["returnOnEquity"] * 100

    return {
        "shares_outstanding": shares,
        "trailing_eps": trailing_eps,
        "market_cap": market_cap,
        "book_value_per_share": book_value_per_share,
        "revenue": revenue,
        "net_debt": net_debt,
        "roe": roe,
        "current_pe": safe_float(info.get("trailingPE")),
        # Reference only: never used in valuation or scoring.
        "consensus_target": safe_float(info.get("targetMeanPrice")),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "current_pb": safe_float(info.get("priceToBook")),
    }


ILLIQUID_TRADED_VALUE = 5e7     # Rs 5 crore median daily traded value
LIQUIDITY_DAYS = 60


def assess_liquidity(price_data):
    """Median daily traded value (close x volume) over recent sessions."""

    if (
        price_data is None
        or price_data.empty
        or "Volume" not in price_data.columns
    ):
        return {"illiquid": None}

    recent = price_data.tail(LIQUIDITY_DAYS)

    traded = (recent["Close"] * recent["Volume"]).median()

    if not is_positive(traded):
        return {"illiquid": None}

    return {
        "illiquid": bool(traded < ILLIQUID_TRADED_VALUE),
        "median_traded_value": float(traded),
        "days": len(recent),
    }


SMALL_CAP = 1e11            # Rs 10,000 crore
MAX_RISK_PREMIUM = 0.03


def company_risk_premium(company_profile, inputs, fundamental_data):
    """
    Company-specific risk premium added to the CAPM cost of equity, so
    discount rates reflect more than beta. Returns (premium, reasons).
    """

    items = []

    if not company_profile.get("earnings_usable", True):
        items.append((0.02, "+2pp: earnings negative or not yet proven"))

    market_cap = inputs.get("market_cap")

    if is_positive(market_cap) and market_cap < SMALL_CAP:
        items.append((0.01, "+1pp: small company (market cap under Rs 10,000 crore)"))

    debt_to_equity = latest_valid(fundamental_data, "Debt_to_Equity")

    if (
        company_profile.get("valuation_family") == "operating"
        and debt_to_equity is not None
        and debt_to_equity > 1.5
    ):
        items.append((0.01, f"+1pp: high leverage (debt/equity {debt_to_equity:.1f}x)"))

    premium = min(sum(p for p, _ in items), MAX_RISK_PREMIUM)

    return premium, [text for _, text in items]


def growth_model_basis(ttm, quarterly_data, fundamental_data):
    """
    Revenue, margin and growth for the growth-stage model, always taken
    from one consistent period (TTM if available, else the latest FY);
    growth is the latest quarter's year-on-year change, labelled.
    """

    growth, growth_date = latest_valid_dated(quarterly_data, "Revenue_YoY")
    growth_label = (
        f"revenue growth: {quarter_label(growth_date)} vs a year earlier"
        if growth is not None else None
    )

    if growth is None:
        growth, growth_date = latest_valid_dated(fundamental_data, "Revenue_Growth")
        growth_label = (
            f"revenue growth: {fy_label(growth_date)} vs prior year"
            if growth is not None else None
        )

    if (
        ttm.get("available")
        and ttm.get("Revenue")
        and ttm.get("Operating_Margin") is not None
    ):
        return {
            "revenue": ttm["Revenue"],
            "margin": ttm["Operating_Margin"],
            "growth": growth,
            "label": f"revenue and margin: {ttm['label']}; {growth_label}",
        }

    revenue, date = latest_valid_dated(fundamental_data, "Revenue")
    margin, margin_date = latest_valid_dated(fundamental_data, "Operating_Margin")

    if revenue is not None and margin is not None and date == margin_date:
        return {
            "revenue": revenue,
            "margin": margin,
            "growth": growth,
            "label": f"revenue and margin: {fy_label(date)}; {growth_label}",
        }

    return {"revenue": None, "margin": None, "growth": growth, "label": "unavailable"}


def run_peer_stage(ticker, info):

    peer_tickers = get_peer_tickers(
        info.get("industryKey"),
        target_ticker=ticker
    )[:MAX_PEER_CANDIDATES]

    if not peer_tickers:
        return [], {
            "selected_peers": None,
            "median_pe": None,
            "peer_count": 0,
            "multiples": {},
            "median_peer_roe": None,
        }

    peer_data = get_peer_financials(peer_tickers)

    classify_ownership, _ = ownership_lookup()

    peer_data["Ownership"] = peer_data["Ticker"].map(classify_ownership)

    target_ownership = classify_ownership(ticker)

    peer_analysis = build_peer_analysis(
        peer_data=peer_data,
        target_ticker=ticker,
        number_of_peers=config.PEER_COUNT,
        target_ownership=target_ownership,
        target_summary=info.get("longBusinessSummary"),
        target_market_cap=safe_float(info.get("marketCap")),
    )

    peer_analysis["target_ownership"] = target_ownership

    return peer_tickers, peer_analysis


def run_market_stage(price_data, company_type, peer_tickers):

    market_data = fetch_index_history(config.MARKET_INDEX)

    benchmark = select_sector_benchmark(company_type, peer_tickers)

    market_features = calculate_market_features(
        price_data,
        market_data,
        benchmark["data"]
    )

    if market_features.empty:
        return market_features, benchmark, {}, None, None, None

    beta = calculate_beta(
        market_features["Stock_Return"],
        market_features["Market_Return"]
    )

    market_correlation = calculate_correlation(
        market_features["Stock_Return"],
        market_features["Market_Return"]
    )

    sector_correlation = calculate_correlation(
        market_features["Stock_Return"],
        market_features["Sector_Return"]
    )

    context = summarize_market_context(market_features)

    return (
        market_features,
        benchmark,
        context,
        beta,
        market_correlation,
        sector_correlation,
    )


def _unavailable(reason):
    return {"available": False, "reason": reason}


def run_valuation_methods(
    company_profile,
    fundamental_data,
    quarterly_data,
    price,
    growth_data,
    price_data,
    inputs,
    peer_analysis,
    beta,
    warnings
):
    """
    Run every applicable method. Inapplicable methods are
    recorded with the profile's reason; failures are recorded
    with their error, never raised.
    """

    multiples = peer_analysis.get("multiples", {})

    def summary(multiple):
        return multiples.get(multiple, {}).get("summary")

    def peers(multiple):
        return multiples.get(multiple, {}).get("selected_peers")

    methods = {
        "dcf": lambda: run_dcf(
            growth_data,
            inputs["shares_outstanding"],
            beta,
            inputs["market_cap"],
            company_profile.get("normalized_fcf"),
            risk_premium=inputs["risk_premium"],
        ),
        "peer_pe": lambda: peer_multiple_valuation(
            inputs["trailing_eps"], summary("PE"), "P/E"
        ),
        "historical_pe": lambda: historical_pe_valuation(
            price_data, fundamental_data, inputs["trailing_eps"]
        ),
        "peer_pb": lambda: roe_adjusted_pb_valuation(
            inputs["book_value_per_share"],
            inputs["roe"],
            peers("PB"),
            summary("PB"),
        ),
        "growth_dcf": lambda: growth_stage_valuation(
            revenue=inputs["growth_basis"]["revenue"],
            revenue_growth_pct=inputs["growth_basis"]["growth"],
            operating_margin_pct=inputs["growth_basis"]["margin"],
            net_debt=inputs["net_debt"],
            shares=inputs["shares_outstanding"],
            raw_beta=beta,
            market_cap=inputs["market_cap"],
            total_debt=latest_valid(fundamental_data, "Debt"),
            peer_data=peers("EVS") if peers("EVS") is not None else peers("PE"),
            price=price,
            basis_label=inputs["growth_basis"]["label"],
            risk_premium=inputs["risk_premium"],
        ),
        "peer_evs": lambda: ev_sales_valuation(
            inputs["revenue"],
            inputs["net_debt"],
            inputs["shares_outstanding"],
            summary("EVS"),
        ),
    }

    results = {}

    for method, compute in methods.items():

        if not company_profile.get(f"{method}_applicable", False):
            results[method] = _unavailable(
                company_profile.get(f"{method}_reason", "Not applicable.")
            )
            continue

        try:
            results[method] = compute()
        except Exception as error:
            warnings.append(f"{method} valuation failed: {error}")
            results[method] = _unavailable(f"Calculation failed: {error}")

    return results


# =========================================================
# MAIN ENTRY POINT
# =========================================================

def analyze_stock(
    ticker,
    include_news=True,
    use_finbert=True,
    use_llm=True
):
    """
    use_llm: allow the local LLM (news-event tagging and the verified
    thesis). Everything works without it.
    """

    # ---------------------------------------------------------
    # 1. Data
    # ---------------------------------------------------------

    bundle = fetch_company_data(ticker)

    warnings = list(bundle["warnings"])

    info = bundle["info"] or {}

    price_data = bundle["price_data"]

    if price_data is None or price_data.empty or "Close" not in price_data:
        return {
            "ticker": ticker,
            "status": "failed",
            "reason": "No price data available; cannot analyse.",
            "warnings": warnings,
        }

    latest_price = float(price_data["Close"].iloc[-1])

    company_name = info.get("longName") or ticker
    sector = info.get("sector")
    industry = info.get("industry")

    # ---------------------------------------------------------
    # 2. Fundamentals
    # ---------------------------------------------------------

    fundamental_data = prepare_fundamental_data(
        bundle["income_stmt"],
        bundle["balance_sheet"],
        bundle["cash_flow"]
    )

    quarterly_data = build_quarterly_fundamentals(
        income_stmt=bundle["quarterly_income_stmt"]
    )

    inputs = get_market_inputs(info, fundamental_data, latest_price)

    # Period hygiene: TTM only from four consecutive quarters.
    ttm = build_ttm(quarterly_data)

    if ttm.get("available") and ttm.get("Revenue"):
        inputs["revenue"] = ttm["Revenue"]
        inputs["revenue_basis"] = ttm["label"]
    else:
        inputs["revenue_basis"] = "Yahoo trailing revenue"

    inputs["growth_basis"] = growth_model_basis(ttm, quarterly_data, fundamental_data)

    # One-off items stripped from earnings used by P/E methods.
    inputs["trailing_eps_reported"] = inputs["trailing_eps"]

    adjusted_eps, eps_note = normalized_eps(
        inputs["trailing_eps"], quarterly_data, inputs["shares_outstanding"]
    )

    inputs["trailing_eps"] = adjusted_eps
    inputs["eps_adjustment"] = eps_note

    if eps_note:
        prefix = "Adjustment: " if adjusted_eps != inputs["trailing_eps_reported"] else "Note: "
        warnings.append(prefix + eps_note)

    consistency = check_data_consistency(info, fundamental_data, ttm)

    if "roe" in consistency["preferred"]:
        inputs["roe"] = consistency["preferred"]["roe"]

    warnings.extend("Note: " + n for n in consistency["notes"])

    # Growth history excludes years before a merger/large raise.
    growth_data, structural_break = post_break_data(fundamental_data)

    if structural_break is not None:
        warnings.append(
            f"Balance sheet jumped in FY{structural_break.year} "
            "(merger, acquisition or large capital raise); growth "
            "estimates use only the years from then on."
        )

    # ---------------------------------------------------------
    # 3. Company profile
    # ---------------------------------------------------------

    company_profile = assess_company_profile(
        fundamental_data=fundamental_data,
        quarterly_data=quarterly_data,
        sector=sector,
        industry=industry,
        trailing_eps=inputs["trailing_eps"],
        price_history_days=len(price_data),
        business_summary=info.get("longBusinessSummary"),
    )

    premium, premium_reasons = company_risk_premium(
        company_profile, inputs, fundamental_data
    )

    inputs["risk_premium"] = premium
    inputs["risk_premium_reasons"] = premium_reasons

    # Cyclicals: P/E-based methods use mid-cycle earnings, not the
    # current (possibly peak or trough) profit.
    if (
        company_profile.get("cyclical")
        and company_profile.get("mid_cycle_net_margin") is not None
        and is_positive(inputs["revenue"])
        and is_positive(inputs["shares_outstanding"])
    ):
        mid_eps = (
            company_profile["mid_cycle_net_margin"] / 100
            * inputs["revenue"] / inputs["shares_outstanding"]
        )
        if mid_eps > 0:
            warnings.append(
                f"Adjustment: cyclical, so P/E methods use mid-cycle EPS "
                f"{mid_eps:.2f} (median net margin "
                f"{company_profile['mid_cycle_net_margin']:.1f}% x current revenue) "
                f"instead of trailing EPS {inputs['trailing_eps']:.2f}."
                if is_positive(inputs["trailing_eps"])
                else f"Adjustment: cyclical, P/E methods use mid-cycle EPS {mid_eps:.2f}."
            )
            inputs["trailing_eps"] = mid_eps

    data_quality = calculate_data_quality_score(
        fundamental_data,
        quarterly_data
    )

    data_quality["consistency_issues"] = consistency["issues"]

    # ---------------------------------------------------------
    # 4. Peers
    # ---------------------------------------------------------

    peer_tickers, peer_analysis = _run_safely(
        run_peer_stage,
        warnings,
        ([], {"selected_peers": None, "median_pe": None,
              "peer_count": 0, "multiples": {}, "median_peer_roe": None}),
        ticker,
        info,
    )

    # ---------------------------------------------------------
    # 5. Technical + market/sector context
    # ---------------------------------------------------------

    technical_data = calculate_technical_features(price_data)

    liquidity = assess_liquidity(price_data)

    latest_technical = technical_data.iloc[-1]

    (
        market_features,
        sector_benchmark,
        market_context,
        beta,
        market_correlation,
        sector_correlation,
    ) = _run_safely(
        run_market_stage,
        warnings,
        (None, {"name": "Unavailable", "source": "unavailable"},
         {}, None, None, None),
        price_data,
        company_profile["company_type"],
        peer_tickers,
    )

    # ---------------------------------------------------------
    # 6. Valuation
    # ---------------------------------------------------------

    method_results = run_valuation_methods(
        company_profile,
        fundamental_data,
        quarterly_data,
        latest_price,
        growth_data,
        price_data,
        inputs,
        peer_analysis,
        beta,
        warnings,
    )

    valuation_weights = get_valuation_weights(company_profile)

    fair_value = build_fair_value_range(
        method_results,
        valuation_weights,
        latest_price
    )

    valuation_selection = select_valuation_methods(
        company_profile,
        method_results
    )

    # What the current price assumes, and bear/base/bull outcomes.
    # Both are reported alongside the fair value, not blended into it.
    unavailable = {"available": False, "reason": "Calculation failed."}

    expectations = _run_safely(
        market_implied_expectations,
        warnings,
        unavailable,
        company_profile,
        method_results,
        inputs,
        growth_data,
        latest_price,
        beta,
    )

    scenarios = _run_safely(
        run_scenarios,
        warnings,
        unavailable,
        company_profile,
        method_results,
        inputs,
        growth_data,
        quarterly_data,
        latest_price,
        beta,
    )

    # ---------------------------------------------------------
    # 7. Scores
    # ---------------------------------------------------------

    fundamental_metrics = extract_fundamental_metrics(
        fundamental_data,
        quarterly_data,
        normalized_fcf=company_profile.get("normalized_fcf"),
        ttm=ttm,
    )

    if "roe" in consistency["preferred"]:
        fundamental_metrics["values"]["roe"] = consistency["preferred"]["roe"]
        fundamental_metrics["sources"]["roe"] = "Yahoo summary (statement ROE inconsistent)"

    fundamental_score = calculate_fundamental_score(
        fundamental_metrics,
        company_profile["company_type"]
    )

    label_weights = {
        label: fair_value["weights_used"][method]
        for method, label in zip(
            fair_value.get("weights_used", {}),
            fair_value.get("methods_used", []),
        )
    }

    valuation_score = calculate_valuation_score(
        method_upsides=fair_value.get("method_upsides"),
        method_weights=label_weights,
        current_pe=inputs["current_pe"],
        peer_median_pe=peer_analysis.get("median_pe"),
    )

    technical_score = calculate_technical_score(latest_technical)

    market_score = calculate_market_sector_score(market_context or {})

    quality_value = calculate_quality_value_score(
        fundamental_score["score"],
        valuation_score["score"]
    )

    # ---------------------------------------------------------
    # 8. Confidence
    # ---------------------------------------------------------

    confidence = calculate_confidence(
        data_quality,
        fair_value,
        method_results,
        fundamental_data,
        company_profile,
        peer_analysis,
    )

    # ---------------------------------------------------------
    # 9. News + ML (both optional, both separate)
    # ---------------------------------------------------------

    if include_news:
        news_analysis = analyze_news(
            ticker=ticker,
            company_name=company_name,
            limit=100,
            use_finbert=use_finbert,
            use_llm_events=use_llm,
        )
    else:
        news_analysis = {
            "news_score": None,
            "label": "Not requested",
            "article_count": 0,
            "top_positive": [],
            "top_negative": [],
            "warnings": [],
        }

    ml_trend = _run_safely(
        get_ml_trend,
        warnings,
        {"available": False, "reason": "ML module failed."},
        ticker,
        price_data,
        fetch_index_history(config.MARKET_INDEX),
    )

    # ---------------------------------------------------------
    # 10. Result
    # ---------------------------------------------------------

    result = {
        "ticker": ticker,
        "status": "ok",
        "company_name": company_name,
        "sector": sector,
        "industry": industry,
        "current_price": latest_price,
        "inputs": inputs,

        "fundamental_data": fundamental_data,
        "quarterly_data": quarterly_data,
        "company_profile": company_profile,
        "data_quality": data_quality,
        "structural_break": structural_break,
        "ttm": {k: v for k, v in ttm.items() if k != "end"},

        "fundamental_metrics": fundamental_metrics,
        "fundamental_score": fundamental_score,

        "technical_data": technical_data,
        "liquidity": liquidity,
        "latest_technical": latest_technical,
        "technical_score": technical_score,

        "market_features": market_features,
        "sector_benchmark": {
            k: v for k, v in sector_benchmark.items() if k != "data"
        },
        "market_context": market_context or {},
        "market_score": market_score,
        "beta": beta,
        "market_correlation": market_correlation,
        "sector_correlation": sector_correlation,

        "peer_analysis": peer_analysis,
        "method_results": method_results,
        "valuation_selection": valuation_selection,
        "valuation_weights": valuation_weights,
        "fair_value": fair_value,
        "expectations": expectations,
        "scenarios": scenarios,
        "confidence": confidence,

        "news": news_analysis,
        "ml_trend": ml_trend,

        "scores": {
            "fundamental": fundamental_score["score"],
            "valuation": valuation_score["score"],
            "valuation_basis": valuation_score["basis"],
            "technical": technical_score["score"],
            "market_sector": market_score["score"],
            "quality_value": quality_value,
            "confidence": confidence["score"],
        },

        "warnings": (
            warnings
            + consistency["issues"]
            + news_analysis.get("warnings", [])
        ),
    }

    # Backward-compatible summary of point values.
    result["valuation"] = {
        "dcf_fair_value": method_results["dcf"].get("base"),
        "peer_fair_value": method_results["peer_pe"].get("base"),
        "historical_pe_fair_value": method_results["historical_pe"].get("base"),
        "pb_fair_value": method_results["peer_pb"].get("base"),
        "ev_sales_fair_value": method_results["peer_evs"].get("base"),
        "combined_fair_value": fair_value.get("base"),
        "upside": fair_value.get("upside_base"),
        "peer_median_pe": peer_analysis.get("median_pe"),
        "current_pe": inputs["current_pe"],
        "current_pb": inputs["current_pb"],
        "weights": fair_value.get("weights_used", {}),
    }

    result["explanation"] = explain(result)

    if use_llm:
        result["thesis"] = _run_safely(
            write_thesis,
            result["warnings"],
            {"available": False, "reason": "Thesis writer failed."},
            result,
        )
    else:
        result["thesis"] = {"available": False, "reason": "LLM not requested."}

    return result
