"""
Walk-forward validation of the trend model.

For each test year Y:
    train on samples whose label was KNOWN before Y starts (purged)
    class thresholds = tertiles of TRAINING forward returns
    test on samples dated in Y

Models are compared with baselines on the same test samples:
    majority      always the most common training class
    momentum      sign of the past 60-day return
    technical     the engine's rule-based technical score

The model passes the gate only if its balanced accuracy beats the
BEST baseline by config.ML_MIN_BALANCED_ACCURACY_EDGE, pooled over
all test years.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config
from src.ml.features import FEATURE_COLUMNS


LABELS = np.array(["Bearish", "Neutral", "Bullish"])

BASELINES = ["majority", "momentum", "technical"]
MODELS = ["logistic", "gradient_boosting"]

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "models"
RESULTS_PATH = ARTIFACT_DIR / "trend_validation.json"
MODEL_PATH = ARTIFACT_DIR / "trend_model.joblib"


def make_models():
    return {
        "logistic": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, C=0.1),
        ),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=200,
            min_samples_leaf=100,
            l2_regularization=1.0,
            random_state=0,
        ),
    }


def to_classes(returns, low, high):
    return np.where(returns <= low, 0, np.where(returns >= high, 2, 1))


def signal_to_class(signal):
    """-1/0/+1 signal -> Bearish/Neutral/Bullish class index."""
    return np.sign(signal).astype(int) + 1


def long_short_spread(predicted, forward_returns):
    """Mean forward return of predicted Bullish minus predicted Bearish."""

    bull = forward_returns[predicted == 2]
    bear = forward_returns[predicted == 0]

    if len(bull) < 20 or len(bear) < 20:
        return None

    return float(bull.mean() - bear.mean())


def run_walk_forward(panel, test_years):

    panel = panel.dropna(subset=FEATURE_COLUMNS + ["forward_return"]).copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel["label_known"] = pd.to_datetime(panel["label_known"])

    pooled = {
        name: {"y": [], "pred": [], "ret": []}
        for name in BASELINES + MODELS
    }

    per_year = []

    for year in test_years:

        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year + 1}-01-01")

        # Purge: train only on labels already known before the test year.
        train = panel[panel["label_known"] < start]
        test = panel[(panel["date"] >= start) & (panel["date"] < end)]

        if len(train) < 1000 or len(test) < 100:
            continue

        low, high = train["forward_return"].quantile([1 / 3, 2 / 3])

        y_train = to_classes(train["forward_return"].values, low, high)
        y_test = to_classes(test["forward_return"].values, low, high)

        predictions = {
            "majority": np.full(len(test), np.bincount(y_train).argmax()),
            "momentum": signal_to_class(test["ret_60"].values),
            "technical": signal_to_class(test["tech_signal"].values),
        }

        for name, model in make_models().items():
            model.fit(train[FEATURE_COLUMNS].values, y_train)
            predictions[name] = model.predict(test[FEATURE_COLUMNS].values)

        row = {"year": year, "n_train": int(len(train)), "n_test": int(len(test))}

        for name, predicted in predictions.items():
            row[name] = round(balanced_accuracy_score(y_test, predicted), 4)
            pooled[name]["y"].extend(y_test)
            pooled[name]["pred"].extend(predicted)
            pooled[name]["ret"].extend(test["forward_return"].values)

        per_year.append(row)

    summary = {}

    for name, values in pooled.items():

        y = np.array(values["y"])
        predicted = np.array(values["pred"])
        returns = np.array(values["ret"])

        spread = long_short_spread(predicted, returns)

        summary[name] = {
            "balanced_accuracy": round(balanced_accuracy_score(y, predicted), 4),
            "long_short_spread_40d": None if spread is None else round(spread, 4),
        }

    return per_year, summary


def evaluate_gate(summary):

    best_baseline = max(BASELINES, key=lambda b: summary[b]["balanced_accuracy"])
    best_model = max(MODELS, key=lambda m: summary[m]["balanced_accuracy"])

    edge = (
        summary[best_model]["balanced_accuracy"]
        - summary[best_baseline]["balanced_accuracy"]
    )

    return {
        "best_model": best_model,
        "best_baseline": best_baseline,
        "edge": round(edge, 4),
        "required_edge": config.ML_MIN_BALANCED_ACCURACY_EDGE,
        "passed": bool(edge >= config.ML_MIN_BALANCED_ACCURACY_EDGE),
    }


def validate_and_save(panel, test_years, universe_note):

    per_year, summary = run_walk_forward(panel, test_years)

    gate = evaluate_gate(summary)

    results = {
        "horizon_trading_days": 40,
        "universe": universe_note,
        "n_samples": int(len(panel)),
        "n_stocks": int(panel["ticker"].nunique()),
        "test_years": [r["year"] for r in per_year],
        "per_year": per_year,
        "summary": summary,
        "gate": gate,
        "caveats": [
            "Universe is current NIFTY 100 members: survivorship bias "
            "flatters any long-biased signal.",
            "Price-only features; no point-in-time fundamentals.",
            "Overlapping 40-day labels across stocks are correlated; "
            "the effective sample size is far smaller than n_samples.",
        ],
    }

    ARTIFACT_DIR.mkdir(exist_ok=True)

    if gate["passed"]:

        # Final model: all samples whose labels are known.
        clean = panel.dropna(subset=FEATURE_COLUMNS + ["forward_return"])
        low, high = clean["forward_return"].quantile([1 / 3, 2 / 3])
        model = make_models()[gate["best_model"]]
        model.fit(
            clean[FEATURE_COLUMNS].values,
            to_classes(clean["forward_return"].values, low, high),
        )
        joblib.dump(model, MODEL_PATH)
        results["model_file"] = MODEL_PATH.name

    elif MODEL_PATH.exists():
        MODEL_PATH.unlink()      # never keep a model that failed the gate

    RESULTS_PATH.write_text(json.dumps(results, indent=2))

    return results
