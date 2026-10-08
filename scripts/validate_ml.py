"""
Walk-forward validation of the ML trend model (price-only).

Usage:  python scripts/validate_ml.py

Writes models/trend_validation.json, and the model itself only
if it passes the gate.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ml.dataset import build_panel
from src.ml.walkforward import validate_and_save


def main():

    panel = build_panel()

    print(
        f"Panel: {len(panel)} samples, {panel['ticker'].nunique()} stocks, "
        f"{panel['date'].min():%Y-%m} to {panel['date'].max():%Y-%m}"
    )

    results = validate_and_save(
        panel,
        test_years=range(2019, 2026),
        universe_note="Current NIFTY 100 constituents (NSE list)",
    )

    print(json.dumps(
        {key: results[key] for key in ("per_year", "summary", "gate")},
        indent=2,
    ))


if __name__ == "__main__":
    main()
