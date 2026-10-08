"""
Scoring.

Design rules:
- Every metric is mapped linearly between an explicit
  "weak" bound (score 0) and "strong" bound (score 100).
- The metrics and bounds depend on the company type: a bank is
  not judged on operating margin, an IT company is not judged
  on net interest margin.
- Missing metrics are excluded and reported, never scored as bad.
- Bounds are CALIBRATED to the cross-section of Indian listed
  companies, NOT fitted to returns (see scripts/band_check.py and
  data/reference/metric_distributions.json, measured 2026-10-08):
    * level metrics (margins, ROE, leverage): sector 25th -> 75th
      percentile where the sector sample has >= 15 companies,
      i.e. "weak" = bottom quartile of Indian peers;
    * growth metrics (noisy single-period snapshots): pooled
      revenue-growth quartiles, weak floored at 0. Profit/EPS
      growth use the same "strong" bar because their own upper
      quartile is dominated by recoveries from a weak base;
    * debt/equity: an absolute risk threshold, not a ranking.
  Where the sample was too small, the earlier documented
  starting points are kept (marked "uncalibrated").
"""

from src.periods import fy_label, quarter_label
from src.utils import (
    interpolate_score,
    is_positive,
    is_valid,
    label_from_thresholds,
    latest_valid,
    latest_valid_dated,
    valid_values,
)


SCORE_LABELS = [
    (67, "Strong"),
    (40, "Moderate"),
    (0, "Weak"),
]

MIN_METRICS_FOR_SCORE = 3


# =========================================================
# METRIC DEFINITIONS
# =========================================================

METRIC_INFO = {
    "revenue_growth": ("Revenue growth (YoY)", "%"),
    "profit_growth": ("Profit growth (YoY)", "%"),
    "eps_growth": ("EPS growth (YoY)", "%"),
    "operating_margin": ("Operating margin", "%"),
    "net_margin": ("Net margin", "%"),
    "roe": ("Return on equity", "%"),
    "roa": ("Return on assets", "%"),
    "debt_to_equity": ("Debt / equity", "x"),
    "fcf_conversion": ("FCF / net income", "x"),
    "nii_growth": ("Net interest income growth", "%"),
    "nim_proxy": ("NII / total assets (NIM proxy)", "%"),
    "leverage": ("Assets / equity", "x"),
    "profit_consistency": ("Share of profitable years", "x"),
}

# Pooled quartiles of revenue growth: operating p25 8% / p75 30%
# (n=242); banks+NBFCs p25 10% / p75 30% (n=40).
OPERATING_GROWTH = [
    ("revenue_growth", 8, 30),
    ("profit_growth", 0, 30),
    ("eps_growth", 0, 30),
]

FINANCIAL_GROWTH_BAND = (10, 30)

# Operating-margin bands: sector 25th -> 75th percentile.
OPERATING_MARGIN_BANDS = {
    "technology": (12, 19),            # n=40
    "pharma": (16, 25),                # n=20
    "consumer_defensive": (9, 19),     # n=38
    "automobile": (6, 12),             # n=39
    "industrial": (8, 18),             # n=40
    "energy": (8, 16),                 # n=19
    "materials": (9, 21),              # n=40
    # Uncalibrated (sample too small or not measured):
    "healthcare_services": (8, 20),
    "consumer_cyclical": (4, 15),
    "utilities": (15, 30),
    "telecom": (15, 35),
    "real_estate": (10, 30),
    "other": (5, 18),
}


def operating_metrics(company_type):

    margin_weak, margin_strong = OPERATING_MARGIN_BANDS.get(
        company_type, OPERATING_MARGIN_BANDS["other"]
    )

    roe_band = (12, 30) if company_type == "technology" else (8, 20)
    debt_band = (1.0, 0.1) if company_type == "technology" else (1.5, 0.3)

    return OPERATING_GROWTH + [
        ("operating_margin", margin_weak, margin_strong),
        ("roe", *roe_band),
        ("debt_to_equity", *debt_band),     # lower is better
        ("fcf_conversion", 0.2, 1.0),
    ]


FINANCIAL_METRICS = {
    # Bank ROE/ROA samples were n=14/13 (< 15): uncalibrated.
    # Measured quartiles (ROE 12.9-16.0%, ROA 1.0-1.8%) suggest
    # these bands are lenient; revisit with a larger sample.
    "bank": [
        ("roe", 8, 17),
        ("roa", 0.5, 1.8),
        ("nim_proxy", 2.0, 4.0),
        ("nii_growth", *FINANCIAL_GROWTH_BAND),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("eps_growth", *FINANCIAL_GROWTH_BAND),
    ],
    "nbfc": [
        ("roe", 8, 20),
        ("roa", 1.0, 4.0),
        # NBFC debt/equity quartiles 3.9-5.8x (n=20), expressed as
        # assets/equity (~ D/E + 1); lower is better.
        ("leverage", 6.8, 4.9),
        ("nii_growth", *FINANCIAL_GROWTH_BAND),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("eps_growth", *FINANCIAL_GROWTH_BAND),
    ],
    "insurance": [
        ("roe", 8, 18),
        ("revenue_growth", *FINANCIAL_GROWTH_BAND),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("eps_growth", *FINANCIAL_GROWTH_BAND),
    ],
    "capital_markets": [
        ("roe", 10, 30),
        ("revenue_growth", *FINANCIAL_GROWTH_BAND),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("net_margin", 18, 42),             # n=19
        ("profit_consistency", 0.5, 1.0),
    ],
    "asset_management": [
        ("roe", 10, 30),
        ("revenue_growth", *FINANCIAL_GROWTH_BAND),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("net_margin", 20, 45),
        ("profit_consistency", 0.5, 1.0),
    ],
    "other_financial": [
        ("roe", 8, 18),
        ("profit_growth", *FINANCIAL_GROWTH_BAND),
        ("eps_growth", *FINANCIAL_GROWTH_BAND),
    ],
}


def metric_specs(company_type):

    if company_type in FINANCIAL_METRICS:
        return FINANCIAL_METRICS[company_type]

    return operating_metrics(company_type)


# =========================================================
# METRIC EXTRACTION
# =========================================================

def _latest_with_fallback(quarterly_data, quarterly_col,
                          fundamental_data, annual_col):
    """Prefer the latest quarterly YoY figure, else annual. Period-tagged."""

    value, date = latest_valid_dated(quarterly_data, quarterly_col)

    if value is not None:
        return value, f"{quarter_label(date)} vs a year earlier"

    value, date = latest_valid_dated(fundamental_data, annual_col)

    if value is not None:
        return value, f"{fy_label(date)} vs prior year"

    return None, None


def extract_fundamental_metrics(
    fundamental_data,
    quarterly_data,
    normalized_fcf=None,
    ttm=None
):
    """
    Collect every metric the engine can compute.
    Values are None when unavailable.
    """

    metrics = {}
    sources = {}

    for key, q_col, a_col in [
        ("revenue_growth", "Revenue_YoY", "Revenue_Growth"),
        ("profit_growth", "Net_Profit_YoY", "Net_Income_Growth"),
        ("eps_growth", "EPS_YoY", "EPS_Growth"),
    ]:
        metrics[key], sources[key] = _latest_with_fallback(
            quarterly_data, q_col, fundamental_data, a_col
        )

    annual_columns = {
        "operating_margin": "Operating_Margin",
        "net_margin": "Net_Margin",
        "roe": "ROE",
        "roa": "ROA",
        "debt_to_equity": "Debt_to_Equity",
        "nii_growth": "NII_Growth",
        "nim_proxy": "NIM_Proxy",
        "leverage": "Assets_to_Equity",
    }

    for key, column in annual_columns.items():
        value, date = latest_valid_dated(fundamental_data, column)
        metrics[key] = value
        sources[key] = fy_label(date) if value is not None else None

    # Margins: prefer trailing twelve months (more current), built only
    # from four consecutive quarters; numerator and denominator always
    # come from the same period.
    if ttm and ttm.get("available"):
        for key, field in (("operating_margin", "Operating_Margin"),
                           ("net_margin", "Net_Margin")):
            if ttm.get(field) is not None:
                metrics[key] = ttm[field]
                sources[key] = ttm["label"]

    # FCF conversion uses normalised FCF vs latest net income.
    net_income = latest_valid(fundamental_data, "Net_Income")

    if is_valid(normalized_fcf) and is_positive(net_income):
        metrics["fcf_conversion"] = normalized_fcf / net_income
        sources["fcf_conversion"] = (
            f"average FCF over recent years / {fy_label(latest_valid_dated(fundamental_data, 'Net_Income')[1])} net income"
        )
    else:
        metrics["fcf_conversion"] = None
        sources["fcf_conversion"] = None

    incomes = valid_values(fundamental_data, "Net_Income")

    if len(incomes) >= 3:
        metrics["profit_consistency"] = (
            sum(1 for v in incomes if v > 0) / len(incomes)
        )
        sources["profit_consistency"] = f"last {len(incomes)} fiscal years"
    else:
        metrics["profit_consistency"] = None
        sources["profit_consistency"] = None

    return {"values": metrics, "sources": sources}


# =========================================================
# FUNDAMENTAL SCORE
# =========================================================

def calculate_fundamental_score(extracted_metrics, company_type):
    """
    Sector-aware fundamental quality score.

    Returns a dict with the score, the per-metric breakdown
    and which metrics were unavailable.
    """

    values = extracted_metrics["values"]
    sources = extracted_metrics["sources"]

    breakdown = []
    missing = []

    for key, weak, strong in metric_specs(company_type):

        label, unit = METRIC_INFO[key]

        value = values.get(key)

        score = interpolate_score(value, weak, strong)

        if score is None:
            missing.append(label)
            continue

        breakdown.append({
            "key": key,
            "label": label,
            "value": value,
            "unit": unit,
            "score": score,
            "assessment": label_from_thresholds(score, SCORE_LABELS),
            "weak_bound": weak,
            "strong_bound": strong,
            "source": sources.get(key),
        })

    if len(breakdown) < MIN_METRICS_FOR_SCORE:
        return {
            "score": None,
            "label": "Unavailable",
            "reason": (
                f"Only {len(breakdown)} of "
                f"{len(breakdown) + len(missing)} metrics available."
            ),
            "metrics": breakdown,
            "missing": missing,
            "coverage": len(breakdown) / max(1, len(breakdown) + len(missing)),
        }

    score = sum(item["score"] for item in breakdown) / len(breakdown)

    return {
        "score": score,
        "label": label_from_thresholds(score, SCORE_LABELS),
        "metrics": breakdown,
        "missing": missing,
        "coverage": len(breakdown) / (len(breakdown) + len(missing)),
    }


# =========================================================
# VALUATION SCORE
# =========================================================

VALUATION_SCALE = 50   # +/- percent at which a method scores 100 / 0


def calculate_valuation_score(
    method_upsides=None,
    method_weights=None,
    current_pe=None,
    peer_median_pe=None
):
    """
    Valuation ATTRACTIVENESS, kept separate from fundamental quality.

    Each credible (core) method's discount/premium to the price is
    mapped onto 0-100 (-50% -> 0, 0% -> 50, +50% -> 100) and the
    scores are weight-averaged. So a stock that is expensive against
    one method but fair against another scores in between, instead of
    collapsing to 0 because one blended estimate is below the price.

    Falls back to P/E relative to the peer median. Returns None if
    neither is available (it is NOT imputed as 50).
    """

    if method_upsides:

        parts = []

        for label, upside in method_upsides.items():
            score = interpolate_score(upside, -VALUATION_SCALE, VALUATION_SCALE)
            if score is not None:
                parts.append((score, (method_weights or {}).get(label, 1.0)))

        total = sum(w for _, w in parts)

        if parts and total > 0:
            return {
                "score": sum(sc * w for sc, w in parts) / total,
                "basis": (
                    "Premium/discount to price across "
                    + ", ".join(method_upsides)
                ),
                "by_method": method_upsides,
            }

    if is_positive(current_pe) and is_positive(peer_median_pe):

        discount = (peer_median_pe / current_pe - 1) * 100

        return {
            "score": interpolate_score(discount, -VALUATION_SCALE, VALUATION_SCALE),
            "basis": "P/E relative to peer median",
        }

    return {"score": None, "basis": "Unavailable"}


# =========================================================
# TECHNICAL (CURRENT MARKET CONDITION)
# =========================================================

def calculate_technical_score(row):
    """
    Trend/momentum condition. Each available signal votes;
    missing signals (e.g. SMA 200 for a recent listing) are
    skipped rather than counted as bearish.
    """

    signals = []

    def value(name):
        v = row.get(name) if hasattr(row, "get") else None
        return float(v) if is_valid(v) else None

    close = value("Close")

    for window in (20, 50, 200):

        sma = value(f"SMA_{window}")

        if close is not None and sma is not None:
            above = close > sma
            signals.append((
                1 if above else -1,
                f"Price {'above' if above else 'below'} {window}-day SMA"
            ))

    rsi = value("RSI_14")

    if rsi is not None:
        if rsi > 70:
            signals.append((-1, f"RSI {rsi:.0f}: overbought"))
        elif rsi < 30:
            signals.append((0, f"RSI {rsi:.0f}: oversold (possible rebound, weak trend)"))
        elif rsi >= 50:
            signals.append((1, f"RSI {rsi:.0f}: positive momentum"))
        else:
            signals.append((-1, f"RSI {rsi:.0f}: negative momentum"))

    macd = value("MACD")
    macd_signal = value("MACD_Signal")

    if macd is not None and macd_signal is not None:
        bullish = macd > macd_signal
        signals.append((
            1 if bullish else -1,
            f"MACD {'above' if bullish else 'below'} signal line"
        ))

    return_30d = value("Return_30D")

    if return_30d is not None:
        signals.append((
            1 if return_30d > 0 else -1,
            f"30-day return {return_30d:+.1f}%"
        ))

    if not signals:
        return {
            "score": None,
            "label": "Unavailable",
            "signals": [],
        }

    score = 50 + 50 * sum(s for s, _ in signals) / len(signals)

    label = "Strong" if score >= 65 else "Weak" if score <= 35 else "Neutral"

    return {
        "score": score,
        "label": label,
        "signals": signals,
    }


# =========================================================
# MARKET / SECTOR CONTEXT
# =========================================================

def calculate_market_sector_score(context):
    """
    Relative strength vs market and sector, plus the market
    regime. Uses whichever pieces are available.
    """

    parts = []
    notes = []

    window = context.get("window", 30)

    relative_market = context.get("relative_to_market")

    if relative_market is not None:
        parts.append(interpolate_score(relative_market, -10, 10))
        notes.append(
            f"{relative_market:+.1f}pp vs NIFTY over {window}D"
        )

    relative_sector = context.get("relative_to_sector")

    if relative_sector is not None:
        parts.append(interpolate_score(relative_sector, -10, 10))
        notes.append(
            f"{relative_sector:+.1f}pp vs sector over {window}D"
        )

    above = context.get("market_above_200dma")

    if above is not None:
        parts.append(65.0 if above else 35.0)
        notes.append(
            "NIFTY above its 200-day average"
            if above
            else "NIFTY below its 200-day average"
        )

    if not parts:
        return {"score": None, "label": "Unavailable", "notes": []}

    score = sum(parts) / len(parts)

    label = "Strong" if score >= 60 else "Weak" if score <= 40 else "Neutral"

    return {"score": score, "label": label, "notes": notes}


# =========================================================
# QUALITY + VALUE
# =========================================================

def calculate_quality_value_score(
    fundamental_score,
    valuation_score
):
    """
    50% fundamental quality + 50% valuation.
    Returns None if either side is unavailable, rather than
    silently substituting a neutral value.
    """

    if not is_valid(fundamental_score) or not is_valid(valuation_score):
        return None

    return (
        fundamental_score * 0.50
        + valuation_score * 0.50
    )
