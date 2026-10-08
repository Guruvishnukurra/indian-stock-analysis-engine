"""
Optional ML trend module (about 40 trading days: Bullish / Neutral / Bearish).

Kept separate from valuation. A trend is shown only if the model
passed the walk-forward validation gate (scripts/validate_ml.py):
out-of-sample balanced accuracy must beat the BEST simple baseline
(majority class, momentum, the engine's technical score) by
config.ML_MIN_BALANCED_ACCURACY_EDGE.

If validation has not been run, or the model failed, the module
reports itself unavailable and cites the evidence. The rest of the
analysis never depends on it, and it never overrides valuation.
"""

import json


from src.ml.walkforward import LABELS, MODEL_PATH, RESULTS_PATH


def load_validation():

    if not RESULTS_PATH.exists():
        return None

    try:
        return json.loads(RESULTS_PATH.read_text())
    except Exception:
        return None


def _evidence(results):

    gate = results["gate"]
    summary = results["summary"]

    model = summary[gate["best_model"]]["balanced_accuracy"]
    baseline = summary[gate["best_baseline"]]["balanced_accuracy"]

    return (
        f"walk-forward balanced accuracy {model * 100:.1f}% vs "
        f"{baseline * 100:.1f}% for the best baseline "
        f"({gate['best_baseline']}); edge {gate['edge'] * 100:.1f}pp, "
        f"{gate['required_edge'] * 100:.0f}pp required "
        f"({results['n_stocks']} stocks, test years "
        f"{results['test_years'][0]}-{results['test_years'][-1]})"
    )


def get_ml_trend(ticker, price_data=None, market_data=None):

    results = load_validation()

    if results is None:
        return {
            "available": False,
            "reason": (
                "Model has not been validated "
                "(run scripts/validate_ml.py)."
            ),
        }

    if not results["gate"]["passed"] or not MODEL_PATH.exists():
        return {
            "available": False,
            "reason": (
                "Model does not demonstrate sufficient out-of-sample "
                "predictive performance: " + _evidence(results) + "."
            ),
            "validation": results["gate"],
        }

    if price_data is None or market_data is None:
        return {
            "available": False,
            "reason": "Price or market history unavailable for features.",
        }

    import joblib

    from src.ml.features import FEATURE_COLUMNS, build_features
    from src.ml.dataset import _naive

    close = _naive(price_data["Close"])
    market = _naive(market_data["Close"]).reindex(close.index).ffill()

    features = build_features(close, market)[FEATURE_COLUMNS].iloc[[-1]]

    if features.isna().any(axis=None):
        return {
            "available": False,
            "reason": "Not enough price history for the model's features.",
        }

    model = joblib.load(MODEL_PATH)

    probabilities = model.predict_proba(features.values)[0]

    best = int(probabilities.argmax())

    return {
        "available": True,
        "trend": str(LABELS[best]),
        "probabilities": {
            str(label): round(float(p), 3)
            for label, p in zip(LABELS, probabilities)
        },
        "evidence": _evidence(results),
        "horizon_trading_days": results["horizon_trading_days"],
    }
