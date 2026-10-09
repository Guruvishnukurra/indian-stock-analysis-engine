"""
Export showcase analyses as static snapshots for the dashboard's demo mode.

Each snapshot is the exact API payload (serialized engine result plus the
engine version), saved under frontend/public/demo/<TICKER>.json, with a
manifest listing what exists and when it was computed. The dashboard opens
these instantly and labels them as snapshots with their date.

    python scripts/export_demo.py              # default showcase set
    python scripts/export_demo.py TCS ITC      # selected tickers
    python scripts/export_demo.py --no-news    # faster, no news/LLM
    python scripts/export_demo.py --evidence   # only the validation evidence

The validation evidence (the /validation payload) and the golden-set
snapshot are exported too, so the Evidence page works without the API.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import ENGINE_VERSION, run_analysis  # noqa: E402
from src.api.serialize import serialize_analysis  # noqa: E402

OUT = ROOT / "frontend" / "public" / "demo"

SHOWCASE = [
    ("TCS", "IT services, steady compounder"),
    ("HDFCBANK", "Private bank"),
    ("ATHERENERG", "Loss-making EV maker"),
    ("TATASTEEL", "Cyclical metals"),
    ("BAJFINANCE", "Consumer lender (NBFC)"),
    ("WAAREEENER", "Capex-heavy solar"),
    ("INFY", "IT services"),
    ("ITC", "Consumer conglomerate"),
]


def export(symbol, include_news):

    ticker = f"{symbol}.NS"
    started = time.time()
    analysis = run_analysis(ticker, include_news)

    if analysis.get("status") != "ok":
        print(f"  {symbol}: skipped ({analysis.get('reason', 'failed')})")
        return None

    result = serialize_analysis(analysis)
    result["engine_version"] = ENGINE_VERSION

    (OUT / f"{symbol}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"  {symbol}: ok in {time.time() - started:.0f}s")

    return {
        "symbol": symbol,
        "ticker": result.get("ticker", ticker),
        "name": result.get("company_name"),
        "stance": (result.get("explanation") or {}).get("stance"),
        "price": result.get("current_price"),
    }


def export_evidence():

    from src.api.main import validation_evidence

    (OUT / "validation.json").write_text(json.dumps(validation_evidence(), ensure_ascii=False), encoding="utf-8")
    golden = ROOT / "tests" / "golden" / "last_snapshot.json"
    if golden.exists():
        (OUT / "golden.json").write_text(golden.read_text(encoding="utf-8"), encoding="utf-8")
    print("Evidence: validation.json and golden.json written")


def main():

    OUT.mkdir(parents=True, exist_ok=True)
    export_evidence()
    if "--evidence" in sys.argv:
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    include_news = "--no-news" not in sys.argv
    wanted = {a.upper() for a in args}
    targets = [(s, d) for s, d in SHOWCASE if not wanted or s in wanted]
    targets += [(s, "") for s in wanted if s not in {t for t, _ in SHOWCASE}]

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"items": []}
    items = {i["symbol"]: i for i in manifest.get("items", [])}

    print(f"Exporting {len(targets)} snapshot(s), news={'on' if include_news else 'off'}")

    for symbol, description in targets:
        try:
            entry = export(symbol, include_news)
        except Exception as error:  # keep going: one bad ticker must not stop the set
            print(f"  {symbol}: error {error}")
            continue
        if entry:
            entry["description"] = description or items.get(symbol, {}).get("description", "")
            entry["exported_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            items[symbol] = entry

    order = [s for s, _ in SHOWCASE] + sorted(s for s in items if s not in dict(SHOWCASE))
    manifest = {
        "engine_version": ENGINE_VERSION,
        "items": [items[s] for s in order if s in items],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {len(manifest['items'])} snapshot(s) in {OUT}")


if __name__ == "__main__":
    main()
