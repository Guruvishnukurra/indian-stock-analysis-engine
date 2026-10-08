"""
Which peer-selection method produces the best comparables?

Test (standard in the comparables literature): for every company
with a valid multiple, predict its multiple as the median of its
selected peers' multiples (the company itself excluded) and
measure the error |log(predicted / actual)|. Better peers ->
smaller error. The market's own pricing is the ground truth.

Methods compared (all within the same Yahoo industry):
    market_cap            top 10 by market cap (original engine rule)
    ownership             same ownership (PSU/private) first, then top 10 by market cap
    similarity            top 10 by business-description similarity
    ownership+similarity  same ownership, then top 10 by similarity
    hybrid                same ownership, top 15 by similarity, then top 10 by market cap

Usage:  python scripts/evaluate_peers.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.band_check import INDUSTRIES
from src.data import get_info
from src.embeddings import embed_text
from src.ownership import ownership_lookup
from src.peer_universe import get_industry_companies


PEERS = 10
MIN_PEERS = 3

MULTIPLES = {"PE": "trailingPE", "PB": "priceToBook"}


def load_universe(per_industry=40):

    classify, _ = ownership_lookup()

    rows = []

    for industries in INDUSTRIES.values():
        for industry in industries:
            for ticker in get_industry_companies(industry).index[:per_industry]:
                try:
                    info = get_info(ticker)
                except Exception:
                    continue
                rows.append({
                    "ticker": ticker,
                    "industry": industry,
                    "market_cap": info.get("marketCap"),
                    "summary": info.get("longBusinessSummary"),
                    "PE": info.get("trailingPE"),
                    "PB": info.get("priceToBook"),
                    "EPS": info.get("trailingEps"),
                    "ownership": classify(ticker),
                })

    data = pd.DataFrame(rows).drop_duplicates("ticker")

    for column in ("market_cap", "PE", "PB", "EPS"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data[data["summary"].apply(lambda s: isinstance(s, str) and len(s) > 50)]

    data["vector"] = data["summary"].map(embed_text)

    return data.reset_index(drop=True)


def select(method, target, candidates):

    if method in ("ownership", "ownership+similarity", "hybrid"):
        same = candidates[candidates["ownership"] == target["ownership"]]
        if len(same) >= 5:
            candidates = same

    if method in ("market_cap", "ownership"):
        return candidates.nlargest(PEERS, "market_cap")

    similarity = candidates["vector"].map(lambda v: float(np.dot(v, target["vector"])))

    candidates = candidates.assign(similarity=similarity)

    if method == "hybrid":
        return candidates.nlargest(15, "similarity").nlargest(PEERS, "market_cap")

    return candidates.nlargest(PEERS, "similarity")


def evaluate(data):

    methods = ["market_cap", "ownership", "similarity", "ownership+similarity", "hybrid"]

    results = {}

    for multiple in MULTIPLES:

        errors = {m: [] for m in methods}

        for _, target in data.iterrows():

            actual = target[multiple]

            if not (actual and actual > 0):
                continue

            if multiple == "PE" and not (target["EPS"] and target["EPS"] > 0):
                continue

            pool = data[
                (data["industry"] == target["industry"])
                & (data["ticker"] != target["ticker"])
                & (data[multiple] > 0)
                & data["market_cap"].notna()
            ]

            if multiple == "PE":
                pool = pool[pool["EPS"] > 0]

            if len(pool) < MIN_PEERS + 2:
                continue

            for method in methods:
                peers = select(method, target, pool)
                if len(peers) < MIN_PEERS:
                    continue
                predicted = peers[multiple].median()
                errors[method].append(abs(np.log(predicted / actual)))

        results[multiple] = {
            method: {
                "companies": len(values),
                "median_abs_log_error": round(float(np.median(values)), 4),
                "mean_abs_log_error": round(float(np.mean(values)), 4),
            }
            for method, values in errors.items()
            if values
        }

    return results


def main():

    data = load_universe()

    print(f"Universe: {len(data)} companies with descriptions", file=sys.stderr)

    results = evaluate(data)

    output = Path(__file__).resolve().parents[1] / "data" / "reference" / "peer_method_evaluation.json"
    output.write_text(json.dumps(results, indent=2))

    for multiple, by_method in results.items():
        print(f"\n{multiple}  (median |log error|; lower = better peers)")
        for method, r in sorted(by_method.items(), key=lambda kv: kv[1]["median_abs_log_error"]):
            print(f"  {method:<22} {r['median_abs_log_error']:.3f}  "
                  f"(~{(np.exp(r['median_abs_log_error']) - 1) * 100:.0f}% typical miss, "
                  f"n={r['companies']})")


if __name__ == "__main__":
    main()
