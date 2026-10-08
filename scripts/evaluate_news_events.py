"""
Accuracy of news event classification vs labelled headlines.

Labels: data/reference/news_labels.csv. Draft labels were written
by Claude; a human may correct them in the human_event_type /
human_direction columns, which then take precedence.

Compares the local LLM with a simple keyword-rule baseline.

Usage:  python scripts/evaluate_news_events.py [dev|test]

    dev   data/reference/news_labels.csv       (used to write the prompt
                                                and keyword rules: optimistic)
    test  data/reference/news_labels_test.csv  (held out; labelled before
                                                either classifier was run)
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import LLM_MODEL, llm_available
from src.news_events import MATERIAL_TYPES, classify_headlines


ROOT = Path(__file__).resolve().parents[1]

KEYWORDS = [
    ("rating_target", r"target|buy call|'buy'|upside|downgrade|upgrade|retains|initiates coverage|brokerage"),
    ("earnings", r"\bq[1-4]\b|results|net profit|earnings|revenue|business update|loan growth"),
    ("corporate_action", r"dividend|buyback|bonus|split|debenture|qip|rights issue|lock-in|stake to"),
    ("m_and_a", r"acquire|acquisition|merger|stake|block deal|ipo|invests"),
    ("regulatory_legal", r"sebi|rbi|penalty|probe|warning|tax|nod|court|lawsuit"),
    ("management", r"\bceo\b|\bmd\b|appoint|resign|chairman|succession"),
    ("macro_sector", r"sensex|nifty 50|market|crude|repo|economy"),
    ("price_move", r"shares? (rise|fall|gain|jump|slip|decline|surge|trade)|prediction|price"),
]


def keyword_classify(headline):

    text = headline.lower()

    for event_type, pattern in KEYWORDS:
        if re.search(pattern, text):
            return event_type

    return "other"


LABEL_FILES = {
    "dev": "news_labels.csv",
    "test": "news_labels_test.csv",
}


def load_labels(split):

    data = pd.read_csv(
        ROOT / "data" / "reference" / LABEL_FILES[split], encoding="utf-8"
    )

    human_type = data["human_event_type"].fillna("").astype(str).str.strip()
    human_direction = data["human_direction"].fillna("").astype(str).str.strip()

    data["true_type"] = human_type.where(human_type != "", data["event_type"])
    data["true_direction"] = human_direction.where(human_direction != "", data["direction"])
    data["human_checked"] = (human_type != "") | (human_direction != "")

    return data


def score(true_types, predicted_types, true_dirs=None, predicted_dirs=None):

    true_types = pd.Series(list(true_types))
    predicted_types = pd.Series(list(predicted_types))

    material_true = true_types.isin(MATERIAL_TYPES)
    material_pred = predicted_types.isin(MATERIAL_TYPES)

    result = {
        "event_type_accuracy": round(float((true_types == predicted_types).mean()), 3),
        "material_vs_noise_accuracy": round(float((material_true == material_pred).mean()), 3),
        "material_recall": round(float((material_pred & material_true).sum() / max(1, material_true.sum())), 3),
        "material_precision": round(float((material_pred & material_true).sum() / max(1, material_pred.sum())), 3),
    }

    if true_dirs is not None:
        both = material_true & material_pred
        dirs_true = pd.Series(list(true_dirs))[both]
        dirs_pred = pd.Series(list(predicted_dirs))[both]
        result["direction_accuracy_on_material"] = (
            round(float((dirs_true == dirs_pred).mean()), 3) if both.any() else None
        )

    return result


def main():

    if not llm_available():
        sys.exit(f"Local model {LLM_MODEL} is not available in Ollama.")

    split = sys.argv[1] if len(sys.argv) > 1 else "test"

    data = load_labels(split)

    predictions = []

    for company, group in data.groupby("company", sort=False):
        classified = classify_headlines(company, group["headline"].tolist())
        if classified is None:
            sys.exit("LLM classification failed.")
        predictions.extend(zip(group.index, classified))

    predicted = pd.DataFrame(
        [{"idx": i, "llm_type": (c or {}).get("event_type", "other"),
          "llm_direction": (c or {}).get("direction", "neutral")}
         for i, c in predictions]
    ).set_index("idx")

    data = data.join(predicted)
    data["keyword_type"] = data["headline"].map(keyword_classify)

    results = {
        "model": LLM_MODEL,
        "split": split,
        "n_headlines": int(len(data)),
        "human_checked": int(data["human_checked"].sum()),
        "llm": score(data["true_type"], data["llm_type"],
                     data["true_direction"], data["llm_direction"]),
        "keyword_baseline": score(data["true_type"], data["keyword_type"]),
        "confusion": pd.crosstab(data["true_type"], data["llm_type"]).to_dict(),
    }

    (ROOT / "data" / "reference" / f"news_event_evaluation_{split}.json").write_text(
        json.dumps(results, indent=2)
    )

    disagreements = data[data["true_type"] != data["llm_type"]]
    disagreements[["headline", "true_type", "llm_type"]].to_csv(
        ROOT / "data" / "reference" / f"news_event_disagreements_{split}.csv", encoding="utf-8"
    )

    print(json.dumps({k: results[k] for k in ("model", "split", "n_headlines", "human_checked", "llm", "keyword_baseline")}, indent=2))
    print(f"\n{len(disagreements)} disagreements:")
    for _, row in disagreements.iterrows():
        print(f"  label={row.true_type:<16} llm={row.llm_type:<16} {row.headline[:90]}")


if __name__ == "__main__":
    main()
