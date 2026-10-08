"""
Central, documented assumptions for the analysis engine.

Everything here is an explicit input, NOT a fitted parameter.
Values are starting points chosen for Indian listed equities and
should be revisited when market conditions change materially.
Nothing in this file is specific to any single company.
"""

# =========================================================
# MARKET ASSUMPTIONS (India)
# =========================================================

# Approximate 10-year Government of India bond yield.
RISK_FREE_RATE = 0.065

# Equity risk premium for India (mature-market premium plus
# country risk premium). Damodaran's India estimates have been
# in the ~7% range; 6.5% is used as a round, moderate value.
EQUITY_RISK_PREMIUM = 0.065

# Pre-tax spread over the risk-free rate for corporate debt.
DEBT_SPREAD = 0.02

# Indian corporate tax rate (new regime, approx.).
TAX_RATE = 0.25

# Beta is noisy; Blume-adjust it toward 1 and bound it so a
# single noisy estimate cannot produce an absurd discount rate.
BETA_BOUNDS = (0.6, 1.6)

# Market benchmark.
MARKET_INDEX = "^NSEI"

# =========================================================
# DCF ASSUMPTIONS
# =========================================================

DCF_TERMINAL_GROWTH = 0.05     # long-run nominal growth (below nominal GDP)
DCF_HIGH_GROWTH_YEARS = 5      # years at the base growth rate
DCF_FADE_YEARS = 5             # years fading linearly to terminal growth
DCF_GROWTH_BOUNDS = (0.03, 0.15)
DCF_DEFAULT_GROWTH = 0.08      # used only if no growth history; flagged
DCF_FCF_NORMALIZATION_YEARS = 3

# Sensitivity steps (one-step shocks define the DCF range).
DCF_GROWTH_STEP = 0.02
DCF_WACC_STEP = 0.01

# =========================================================
# PEER SYSTEM
# =========================================================

PEER_COUNT = 10
MIN_PEERS_FOR_QUARTILES = 4

# Bound on the ROE adjustment applied to peer P/B so a single
# extreme ROE does not dominate.
ROE_ADJUSTMENT_BOUNDS = (0.5, 2.0)

# =========================================================
# HISTORICAL P/E
# =========================================================

# Annual results are not public on the fiscal year-end date.
# Use EPS only after this lag to avoid look-ahead bias.
REPORTING_LAG_DAYS = 60
MIN_HISTORICAL_PE_YEARS = 2

# =========================================================
# VALUATION WEIGHTS BY COMPANY TYPE
# =========================================================
# Weights are renormalised over methods that are actually
# available, so a missing method never drags the result to zero.

# DCF was 45%. Reduced (judgement, not fitted) after the consensus check
# (scripts/compare_consensus.py, 48 NIFTY 50 companies): the DCF sat a
# median 58% below price while peer P/E (-9%) and own-history P/E (+24%)
# did not, i.e. it disagrees structurally with every other method because
# Indian large caps price a longer growth runway than a 10-year DCF holds.
# Historical P/E is raised from 5% now that it is computed from real data
# with split/bonus and look-ahead guards. The DCF stays fully reported.
OPERATING_WEIGHTS = {
    "dcf": 0.25,
    "peer_pe": 0.55,
    "historical_pe": 0.20,
}

FINANCIAL_BALANCE_SHEET_WEIGHTS = {   # banks, NBFCs, insurers
    "peer_pe": 0.50,
    "peer_pb": 0.45,
    "historical_pe": 0.05,
}

ASSET_LIGHT_FINANCIAL_WEIGHTS = {     # brokers, AMCs, exchanges
    "peer_pe": 0.70,
    "peer_pb": 0.25,
    "historical_pe": 0.05,
}

# Loss-making operating companies: no earnings-based method is
# valid. Peer EV/Sales (debt-aware) is a weak fallback, flagged as such.
LOSS_MAKING_WEIGHTS = {
    "dcf": 0.50,
    "peer_evs": 0.50,
}

# =========================================================
# CONFIDENCE
# =========================================================

CONFIDENCE_LABELS = [
    (75, "High"),
    (55, "Medium"),
    (35, "Low"),
    (0, "Very Low"),
]

# =========================================================
# FINAL STANCE
# =========================================================

ATTRACTIVE_MIN_UPSIDE = 15.0
AVOID_MAX_UPSIDE = -15.0
ATTRACTIVE_MIN_FUNDAMENTAL = 55.0
WEAK_FUNDAMENTAL = 40.0
STRONG_FUNDAMENTAL = 70.0
MIN_CONFIDENCE_FOR_STANCE = 35.0
ATTRACTIVE_MIN_CONFIDENCE = 50.0

# =========================================================
# ML TREND GATE
# =========================================================
# An ML trend model may be shown only if, on walk-forward
# out-of-sample data, it beats the majority-class baseline
# by at least this margin in balanced accuracy.
ML_MIN_BALANCED_ACCURACY_EDGE = 0.05
