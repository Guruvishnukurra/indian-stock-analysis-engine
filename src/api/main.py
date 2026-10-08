"""
FastAPI backend for the analysis engine.

An analysis takes ~20-60 s (data, peers, news, local LLM), so
requests create a JOB that runs in a background worker; clients
poll the job. Recent results are reused instead of recomputed.

Run:  uvicorn src.api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.db import Database, utcnow
from src.api.serialize import serialize_analysis


ROOT = Path(__file__).resolve().parents[2]

# Bump whenever the analysis output changes shape or method, so results
# saved by an older engine are recomputed instead of reused.
ENGINE_VERSION = "2026.10.09-2"

RESULT_MAX_AGE = timedelta(hours=int(os.environ.get("RESULT_MAX_AGE_HOURS", "6")))
MAX_WORKERS = int(os.environ.get("ANALYSIS_WORKERS", "2"))

TICKER_PATTERN = re.compile(r"^[A-Z0-9&\-]{1,20}(\.(NS|BO))?$")

DISCLAIMER = (
    "Analytical assessment for research and education. Not investment "
    "advice, not a recommendation to buy or sell, and not a guaranteed "
    "prediction."
)


def normalize_ticker(raw):
    """'tcs' -> 'TCS.NS'; rejects anything that is not an NSE/BSE symbol."""

    ticker = raw.strip().upper()

    if not TICKER_PATTERN.match(ticker):
        raise HTTPException(422, f"Invalid ticker '{raw}'. Use e.g. TCS or TCS.NS.")

    if "." not in ticker:
        ticker += ".NS"

    return ticker


def run_analysis(ticker, include_news):
    """Indirection so tests can replace the engine."""

    from src.analysis import analyze_stock

    return analyze_stock(ticker, include_news=include_news)


def summarize(result):

    fair_value = result.get("fair_value") or {}
    explanation = result.get("explanation") or {}
    confidence = result.get("confidence") or {}

    return {
        "price": result.get("current_price"),
        "stance": explanation.get("stance"),
        "fair_value_low": fair_value.get("low_rounded"),
        "fair_value_base": fair_value.get("base_rounded"),
        "fair_value_high": fair_value.get("high_rounded"),
        "upside_base": fair_value.get("upside_base"),
        "confidence": confidence.get("score"),
        "confidence_label": confidence.get("label"),
    }


def execute_job(db, job_id, ticker, include_news):

    db.update_job(job_id, status="running")

    try:
        analysis = run_analysis(ticker, include_news)

        result = serialize_analysis(analysis)
        result["engine_version"] = ENGINE_VERSION

        if analysis.get("status") != "ok":
            db.update_job(
                job_id, status="failed", finished_at=utcnow(),
                error=analysis.get("reason", "Analysis failed."), result=result,
            )
            return

        db.update_job(
            job_id, status="done", finished_at=utcnow(),
            result=result, summary=summarize(result),
        )

    except Exception as error:
        db.update_job(
            job_id, status="failed", finished_at=utcnow(),
            error=f"{type(error).__name__}: {error}",
        )


def job_payload(job, include_result=True):

    payload = {
        "job_id": job.id,
        "ticker": job.ticker,
        "status": job.status,
        "include_news": job.include_news,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": job.error,
        "summary": job.summary,
        "disclaimer": DISCLAIMER,
    }

    if include_result and job.status == "done":
        payload["result"] = job.result

    return payload


def is_fresh(job):

    created = job.created_at

    if created.tzinfo is None:          # SQLite drops the time zone
        created = created.replace(tzinfo=timezone.utc)

    return utcnow() - created < RESULT_MAX_AGE


@asynccontextmanager
async def lifespan(app):

    app.state.db = getattr(app.state, "db", None) or Database()
    app.state.db.mark_interrupted()
    app.state.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    yield

    app.state.executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(
    title="Indian Stock Analysis Engine",
    version="0.4.0",
    description=(
        "Explainable fundamental, valuation and market-condition analysis "
        "for NSE/BSE companies. " + DISCLAIMER
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., examples=["TCS.NS"])
    include_news: bool = True
    force: bool = Field(False, description="Recompute even if a recent result exists.")


@app.get("/health")
def health():

    from src.llm import LLM_MODEL, llm_available

    try:
        import torch
        gpu = torch.cuda.is_available()
    except Exception:
        gpu = False

    return {
        "status": "ok",
        "local_llm": {"model": LLM_MODEL, "available": llm_available()},
        "gpu": gpu,
    }


@app.post("/analyses", status_code=202)
def create_analysis(request: AnalysisRequest, http: Request):

    db = http.app.state.db

    ticker = normalize_ticker(request.ticker)

    if not request.force:

        recent = db.latest_done(ticker, include_news=request.include_news)

        if (
            recent
            and is_fresh(recent)
            and (recent.result or {}).get("engine_version") == ENGINE_VERSION
        ):
            return {**job_payload(recent, include_result=False), "reused": True}

        running = db.active_job(ticker, include_news=request.include_news)

        if running:
            return {**job_payload(running, include_result=False), "reused": True}

    job = db.create_job(ticker, request.include_news)

    http.app.state.executor.submit(
        execute_job, db, job.id, ticker, request.include_news
    )

    return {**job_payload(job, include_result=False), "reused": False}


@app.get("/analyses/{job_id}")
def get_analysis(job_id: str, http: Request):

    job = http.app.state.db.get_job(job_id)

    if job is None:
        raise HTTPException(404, "Job not found.")

    return job_payload(job)


@app.get("/stocks/{ticker}/latest")
def latest_analysis(ticker: str, http: Request):

    job = http.app.state.db.latest_done(normalize_ticker(ticker))

    if job is None:
        raise HTTPException(404, "No completed analysis for this ticker yet.")

    return job_payload(job)


@app.get("/stocks/{ticker}/history")
def analysis_history(
    ticker: str, http: Request, limit: int = Query(50, ge=1, le=500)
):

    jobs = http.app.state.db.history(normalize_ticker(ticker), limit=limit)

    return {
        "ticker": normalize_ticker(ticker),
        "history": [
            {"job_id": j.id, "created_at": j.created_at.isoformat(), **(j.summary or {})}
            for j in jobs
        ],
    }


@app.get("/validation")
def validation_evidence():
    """
    The evidence behind the engine's AI/ML components, so a reader
    can check claims instead of trusting them.
    """

    files = {
        "ml_trend": ROOT / "models" / "trend_validation.json",
        "peer_selection": ROOT / "data" / "reference" / "peer_method_evaluation.json",
        "news_events_test": ROOT / "data" / "reference" / "news_event_evaluation_test.json",
        "metric_distributions": ROOT / "data" / "reference" / "metric_distributions.json",
        "consensus_comparison": ROOT / "data" / "reference" / "consensus_comparison.json",
    }

    evidence = {}

    for name, path in files.items():
        try:
            evidence[name] = json.loads(path.read_text())
        except Exception:
            evidence[name] = None

    return evidence
