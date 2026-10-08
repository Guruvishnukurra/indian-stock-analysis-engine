"""
Golden-set regression harness. Run after every change.

    python scripts/run_golden.py

For each stock in tests/golden/golden_set.json:
  1. structural expectations (type, routing flags, methods, verdicts)
  2. universal sanity (base/price ratio, allowed stances, report prints
     without 'nan', confidence within 0-100)
  3. hand-checked fair-value range, where the user has filled it in
Then:
  4. sector distribution check: flags company types where every rated
     verdict is the same, or the median base/price gap is extreme -
     signs of a method flaw rather than a market view
  5. change report vs the previous run's snapshot

Network access is required (live data, cached).
"""

import contextlib
import io
import json
import math
import sys
import warnings
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import analyze_stock          # noqa: E402
from src.report import generate_report          # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "golden_set.json"
SNAPSHOT = ROOT / "tests" / "golden" / "last_snapshot.json"

EXTREME_SECTOR_GAP = 0.5        # |median log(base/price)| above this is flagged
CHANGE_THRESHOLD = 0.15         # base estimate moved > 15% since last run


def snapshot_of(analysis):

    profile = analysis["company_profile"]
    fair_value = analysis["fair_value"]

    return {
        "status": analysis.get("status"),
        "company_type": profile.get("company_type"),
        "stance": analysis["explanation"]["stance"],
        "price": analysis["current_price"],
        "base": fair_value.get("base"),
        "methods": fair_value.get("methods_used", []),
        "confidence": analysis["confidence"]["score"],
        "cyclical": bool(profile.get("cyclical")),
        "capex_heavy": bool(profile.get("capex_heavy")),
        "holding_company": bool(profile.get("holding_company")),
        "earnings_usable": bool(profile.get("earnings_usable", True)),
        "ownership": analysis["peer_analysis"].get("target_ownership"),
        "expectations_available": bool((analysis.get("expectations") or {}).get("available")),
    }


def check(stock, snap, report_text, sanity):

    failures = []
    expect = stock.get("expect", {})

    for key in ("company_type", "cyclical", "capex_heavy", "holding_company",
                "earnings_usable", "ownership", "expectations_available"):
        if key in expect and snap.get(key) != expect[key]:
            failures.append(f"{key}: expected {expect[key]}, got {snap.get(key)}")

    for method in expect.get("methods_include", []):
        if method not in snap["methods"]:
            failures.append(f"method {method} expected but not used")

    for method in expect.get("methods_exclude", []):
        if method in snap["methods"]:
            failures.append(f"method {method} must not be used")

    if "stance_in" in expect and snap["stance"] not in expect["stance_in"]:
        failures.append(f"stance {snap['stance']} not in {expect['stance_in']}")

    if snap["stance"] in expect.get("stance_not", []):
        failures.append(f"stance {snap['stance']} is not allowed")

    if snap["stance"] not in sanity["all_stances"]:
        failures.append(f"unknown stance {snap['stance']}")

    if not 0 <= snap["confidence"] <= 100:
        failures.append(f"confidence out of range: {snap['confidence']}")

    if snap["base"] and snap["price"]:
        low, high = sanity["base_to_price_ratio"]
        ratio = snap["base"] / snap["price"]
        if not low <= ratio <= high and snap["stance"] in sanity["rated_stances"]:
            failures.append(f"rated with implausible base/price ratio {ratio:.2f}")

    if " nan" in report_text.lower() or "nan%" in report_text.lower():
        failures.append("report contains 'nan'")

    checked = stock.get("fair_value_checked")

    if checked and snap["base"] and not checked[0] <= snap["base"] <= checked[1]:
        failures.append(
            f"base {snap['base']:.0f} outside hand-checked range {checked[0]}-{checked[1]}"
        )

    return failures


def distribution_flags(snapshots, sanity):

    by_type = defaultdict(list)

    for snap in snapshots.values():
        if snap.get("status") == "ok":
            by_type[snap["company_type"]].append(snap)

    flags = []

    for company_type, items in sorted(by_type.items()):

        rated = [s for s in items if s["stance"] in sanity["rated_stances"]]

        gaps = [
            math.log(s["base"] / s["price"])
            for s in items
            if s["base"] and s["price"] and s["base"] > 0
        ]

        if len(rated) >= 2 and len({s["stance"] for s in rated}) == 1:
            flags.append(
                f"{company_type}: all {len(rated)} rated stocks are {rated[0]['stance']}"
            )

        if len(gaps) >= 2:
            gaps.sort()
            median = gaps[len(gaps) // 2]
            if abs(median) > EXTREME_SECTOR_GAP:
                flags.append(
                    f"{company_type}: median base/price {math.exp(median):.2f}x "
                    f"across {len(gaps)} stocks"
                )

    return flags


def main():

    warnings.filterwarnings("ignore")
    sys.stdout.reconfigure(encoding="utf-8")

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    sanity = golden["sanity"]

    previous = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}

    snapshots, failures = {}, {}

    for stock in golden["stocks"]:

        ticker = stock["ticker"]

        try:
            analysis = analyze_stock(ticker, include_news=False, use_llm=False)
        except Exception as error:
            failures[ticker] = [f"crashed: {type(error).__name__}: {error}"]
            continue

        if analysis.get("status") != "ok":
            failures[ticker] = [f"analysis failed: {analysis.get('reason')}"]
            continue

        buffer = io.StringIO()

        try:
            with contextlib.redirect_stdout(buffer):
                generate_report(analysis)
        except Exception as error:
            failures[ticker] = [f"report crashed: {error}"]
            continue

        snap = snapshot_of(analysis)
        snapshots[ticker] = snap

        problems = check(stock, snap, buffer.getvalue(), sanity)

        if problems:
            failures[ticker] = problems

    print(f"\nGOLDEN SET: {len(golden['stocks']) - len(failures)}/{len(golden['stocks'])} passed")

    for ticker, problems in failures.items():
        print(f"  FAIL {ticker}")
        for problem in problems:
            print(f"       - {problem}")

    flags = distribution_flags(snapshots, sanity)

    print("\nSECTOR DISTRIBUTION")
    for flag in flags or ["no skewed sectors"]:
        print(f"  ! {flag}" if flags else f"  {flag}")

    print("\nCHANGES SINCE LAST RUN")
    changes = 0
    for ticker, snap in snapshots.items():
        old = previous.get(ticker)
        if not old:
            continue
        notes = []
        if old["stance"] != snap["stance"]:
            notes.append(f"stance {old['stance']} -> {snap['stance']}")
        if old.get("base") and snap.get("base"):
            move = snap["base"] / old["base"] - 1
            if abs(move) > CHANGE_THRESHOLD:
                notes.append(f"base {old['base']:.0f} -> {snap['base']:.0f} ({move * 100:+.0f}%)")
        if notes:
            changes += 1
            print(f"  {ticker}: " + "; ".join(notes))
    if not changes:
        print("  none" if previous else "  (first run: snapshot saved)")

    print("\nSTANCES")
    for ticker, snap in snapshots.items():
        base = f"{snap['base']:.0f}" if snap["base"] else "-"
        print(f"  {ticker:15} {snap['company_type']:20} {snap['stance']:18} "
              f"price {snap['price']:9.0f}  base {base:>8}  conf {snap['confidence']}")

    SNAPSHOT.write_text(json.dumps(snapshots, indent=1))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
