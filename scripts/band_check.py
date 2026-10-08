"""
Measure real distributions of fundamental metrics for Indian
companies by company type, to check the scoring bands.

Universe: Yahoo's top companies in representative industries
(biased toward larger, established companies; documented).
Output: 25th / 50th / 75th percentiles per metric and type.

Usage:  python scripts/band_check.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import get_info
from src.peer_universe import get_industry_companies


INDUSTRIES = {
    "technology": ["information-technology-services", "software-application"],
    "pharma": ["drug-manufacturers-specialty-generic"],
    "consumer_defensive": ["household-personal-products", "packaged-foods"],
    "automobile": ["auto-parts", "auto-manufacturers"],
    "industrial": ["specialty-industrial-machinery", "engineering-construction"],
    "materials": ["specialty-chemicals", "steel"],
    "energy": ["oil-gas-refining-marketing"],
    "utilities": ["utilities-regulated-electric"],
    "bank": ["banks-regional"],
    "nbfc": ["credit-services"],
    "capital_markets": ["capital-markets"],
}

PER_INDUSTRY = 20

# Yahoo info field -> (engine metric, multiplier to percent/ratio)
FIELDS = {
    "returnOnEquity": ("roe", 100),
    "returnOnAssets": ("roa", 100),
    "operatingMargins": ("operating_margin", 100),
    "profitMargins": ("net_margin", 100),
    "revenueGrowth": ("revenue_growth", 100),
    "earningsGrowth": ("profit_growth", 100),
    "debtToEquity": ("debt_to_equity", 0.01),   # Yahoo reports %
}


def collect():

    rows = []

    for company_type, industries in INDUSTRIES.items():

        for industry in industries:

            companies = get_industry_companies(industry)

            for ticker in companies.index[:PER_INDUSTRY]:

                try:
                    info = get_info(ticker)
                except Exception:
                    continue

                row = {"type": company_type, "ticker": ticker}

                for field, (metric, scale) in FIELDS.items():
                    value = info.get(field)
                    row[metric] = value * scale if isinstance(value, (int, float)) else None

                rows.append(row)

        print(f"{company_type}: {sum(r['type'] == company_type for r in rows)} companies",
              file=sys.stderr)

    return pd.DataFrame(rows)


def main():

    data = collect()

    metrics = [m for m, _ in FIELDS.values()]

    summary = {}

    for company_type, group in data.groupby("type"):

        summary[company_type] = {}

        for metric in metrics:

            values = pd.to_numeric(group[metric], errors="coerce").dropna()

            if len(values) < 8:
                continue

            summary[company_type][metric] = {
                "n": int(len(values)),
                "p25": round(values.quantile(0.25), 1),
                "p50": round(values.quantile(0.50), 1),
                "p75": round(values.quantile(0.75), 1),
            }

    output = Path(__file__).resolve().parents[1] / "data" / "reference" / "metric_distributions.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2))

    for company_type, metrics_summary in summary.items():
        print(f"\n{company_type}")
        for metric, s in metrics_summary.items():
            print(f"  {metric:<17} n={s['n']:<3} p25={s['p25']:>7}  p50={s['p50']:>7}  p75={s['p75']:>7}")


if __name__ == "__main__":
    main()
