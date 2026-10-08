# Indian Stock Analysis Engine

Explainable analysis of NSE/BSE companies: fundamentals, sector-aware
scoring, multi-method fair-value **ranges**, confidence, market-implied
expectations, bear/base/bull scenarios, AI-tagged news events, a
fact-checked AI-written thesis, and an honestly validated ML trend module.

> Analytical assessment for research and education. Not investment advice.

## How verdicts work

- **Fair value** = core methods only (configured weight >= 10%). Low-weight
  references such as own-history P/E are shown as *context* and never move
  the base or range; the range always spans every core method's estimate.
- **Valuation score** averages each core method's premium/discount to the
  price (-50% -> 0, +50% -> 100), separate from fundamental quality.
- **NOT RATED**: loss-making or barely profitable companies get no
  buy/avoid verdict. A growth-stage (path-to-profitability) DCF reports
  which mature operating margin the price requires, compared with what
  profitable peers actually earn.
- **Peers**: same ownership (PSU/private), ranked by business-description
  similarity, excluding companies under 20% of the target's market cap.

## Run

```bash
pip install -r requirements.txt
python -m pytest tests -q                          # 81 offline tests
python -m uvicorn src.api.main:app --port 8000     # API, docs at /docs
```

From Python:

```python
from src.analysis import analyze_stock
from src.report import generate_report
generate_report(analyze_stock("TCS.NS"))
```

Optional local LLM for news-event tagging and the thesis (free, runs on
your GPU): install [Ollama](https://ollama.com) and
`ollama pull qwen2.5:7b-instruct`. Without it, everything else still works.
The thesis is written only from engine-computed facts; every number in it
is checked against those facts, and advice language or a verdict that
contradicts the engine's stance causes it to be rejected.

Cache: Yahoo/NSE data is cached under `data/cache/` (`src.cache.clear_cache()`
to reset).

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/analyses` | Start an analysis job (`{"ticker": "TCS", "include_news": true}`); reuses results under 6 h old unless `force` |
| GET | `/analyses/{job_id}` | Poll status; full result when `done` |
| GET | `/stocks/{ticker}/latest` | Latest completed analysis |
| GET | `/stocks/{ticker}/history` | Past stances, fair values, confidence |
| GET | `/validation` | The evidence behind the AI/ML components |
| GET | `/health` | Local LLM and GPU availability |

Storage: SQLite at `data/app.db` by default; set `DATABASE_URL` for PostgreSQL.

## Validation evidence (re-run the scripts to refresh)

| Component | Script | Result (2026-10-08) |
|---|---|---|
| ML trend (40-day) | `scripts/validate_ml.py` | Walk-forward balanced accuracy 36.0% vs 33.3% baseline; **fails** the 5pp gate, so it is reported as unavailable |
| Technical score | same | No predictive value (33.3%): kept as context only |
| Peer selection | `scripts/evaluate_peers.py` | Ownership + description similarity + 20% size floor is best (P/E typical miss 57% to 50%, P/B 77% to 63% vs top-by-market-cap) |
| News events (local LLM, two-pass) | `scripts/evaluate_news_events.py test` / `test2` | On 120 held-out headlines: 86% of reported catalysts/risks are genuine company events (68% single-pass), 76% have the exact type; recall 55%, i.e. about half of events are not shown. Labels drafted by Claude, pending human check |
| Score bands | `scripts/band_check.py` | Calibrated to sector quartiles of Indian companies |
| Fair value vs analyst consensus | `scripts/compare_consensus.py` | 48 NIFTY 50 companies. With DCF at 45% weight the engine sat a median 39% below consensus; the driver was the DCF (median 58% below price vs peer P/E -9%, own-history P/E +24%, consensus +28%). DCF weight was cut to 25% (judgement, documented in `src/config.py`): gap now -31%, consensus inside the engine's range 52% (was 46%). Rank correlation with consensus ~0: the engine's relative calls are independent of analysts |

## Known limitations

- Yahoo Finance data: about 4 years of statements, no point-in-time history, occasional internal inconsistencies (checked and flagged).
- PSU detection covers NSE PSU index members only (e.g. IDBI Bank and LIC are missed).
- The fair-value backtest needs historical fundamentals from another source.
- News-event labels need human verification (`data/reference/news_labels*.csv`).
  A second LLM pass verifies every reported item; about 1 in 7 shown items
  may still be wrong, and about half of real events are not shown.
- The DCF is structurally conservative for Indian large caps, which trade at
  40-60x free cash flow: a 10-year DCF at ~12% cost of capital and 5%
  terminal growth cannot reach those prices. With 45% DCF weight this pulls
  blended fair values well below market and consensus. Its weight was
  therefore reduced from 45% to 25%; it remains fully reported as a
  conservative intrinsic anchor, with sensitivity grid and reverse DCF.
- Holding companies and conglomerates (e.g. Grasim, Reliance) are valued
  on consolidated numbers against operating peers; sum-of-the-parts is not
  implemented.
- Demergers (e.g. Tata Motors PV/CV) are not detected: statements may still
  describe the pre-demerger company.
