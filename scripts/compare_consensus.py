"""
Sanity check: engine fair value vs analyst consensus targets.

Consensus is NOT ground truth (analysts herd and are optimistic on
average), but a large SYSTEMATIC gap would reveal a bias in the
engine's assumptions (e.g. discount rates, peer selection).

Universe: current NIFTY 50 (NSE list). Companies with fewer than
5 analyst opinions are skipped.

Usage:  python scripts/compare_consensus.py
Writes data/reference/consensus_comparison.json and .csv
"""

import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import analyze_stock
from src.cache import DAY, cached
from src.data import get_info


ROOT = Path(__file__).resolve().parents[1]

MIN_ANALYSTS = 5


@cached("universe", 7 * DAY)
def get_nifty50_symbols():

    response = requests.get(
        "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()

    data = pd.read_csv(io.StringIO(response.text))

    return [f"{s}.NS" for s in data["Symbol"].astype(str)]


def collect():

    rows = []

    for ticker in get_nifty50_symbols():

        info = get_info(ticker)

        target = info.get("targetMeanPrice")
        analysts = info.get("numberOfAnalystOpinions") or 0

        if not target or analysts < MIN_ANALYSTS:
            continue

        try:
            analysis = analyze_stock(ticker, include_news=False)
        except Exception as error:
            print(f"{ticker}: failed ({error})", file=sys.stderr)
            continue

        fair_value = analysis.get("fair_value") or {}

        if not fair_value.get("available"):
            continue

        price = analysis["current_price"]

        rows.append({
            "ticker": ticker,
            "type": analysis["company_profile"]["company_type"],
            "price": price,
            "engine_low": fair_value["low"],
            "engine_base": fair_value["base"],
            "engine_high": fair_value["high"],
            "consensus": target,
            "analysts": analysts,
            "confidence": analysis["confidence"]["score"],
            "stance": analysis["explanation"]["stance"],
        })

        print(f"{ticker}: engine {fair_value['base']:.0f} vs consensus {target:.0f}",
              file=sys.stderr)

    return pd.DataFrame(rows)


def summarize(data):

    log_gap = np.log(data["engine_base"] / data["consensus"])

    engine_upside = data["engine_base"] / data["price"] - 1
    consensus_upside = data["consensus"] / data["price"] - 1

    inside = (
        (data["consensus"] >= data["engine_low"])
        & (data["consensus"] <= data["engine_high"])
    )

    def block(mask):
        gap = log_gap[mask]
        return {
            "companies": int(mask.sum()),
            "median_engine_vs_consensus": round(float(np.exp(gap.median()) - 1), 3),
            "median_abs_gap": round(float(np.exp(gap.abs().median()) - 1), 3),
            "consensus_inside_engine_range": round(float(inside[mask].mean()), 3),
        }

    high_confidence = data["confidence"] >= 75

    by_type = {
        company_type: block(data["type"] == company_type)
        for company_type in sorted(data["type"].unique())
        if (data["type"] == company_type).sum() >= 3
    }

    return {
        "universe": "NIFTY 50 with >= 5 analyst opinions",
        "all": block(pd.Series(True, index=data.index)),
        "high_confidence_only": block(high_confidence),
        "upside_rank_correlation": round(
            float(engine_upside.corr(consensus_upside, method="spearman")), 3
        ),
        "by_company_type": by_type,
        "note": (
            "Positive median_engine_vs_consensus = engine above consensus. "
            "Consensus is a reference point, not ground truth."
        ),
    }


def main():

    warnings.filterwarnings("ignore")

    data = collect()

    output = ROOT / "data" / "reference"

    data.to_csv(output / "consensus_comparison.csv", index=False)

    summary = summarize(data)

    (output / "consensus_comparison.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
