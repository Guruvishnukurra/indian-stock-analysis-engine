import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import main
from src.api.db import Database
from src.api.serialize import serialize_analysis, to_jsonable


def fake_analysis(ticker, include_news):

    dates = pd.date_range("2025-01-01", periods=300, freq="B", tz="Asia/Kolkata")

    technical = pd.DataFrame({
        "Close": np.linspace(100, 130, 300),
        "SMA_50": 110.0, "SMA_200": np.nan, "RSI_14": 55.0,
    }, index=dates)

    return {
        "ticker": ticker,
        "status": "ok",
        "current_price": 130.0,
        "fundamental_data": pd.DataFrame(
            {"Revenue": [1.0, 2.0], "ROE": [10.0, np.inf]},
            index=pd.to_datetime(["2024-03-31", "2025-03-31"]),
        ),
        "quarterly_data": pd.DataFrame(),
        "technical_data": technical,
        "latest_technical": technical.iloc[-1],
        "market_features": pd.DataFrame(),
        "fair_value": {
            "available": True, "low_rounded": 120.0, "base_rounded": 150.0,
            "high_rounded": 180.0, "upside_base": 15.4,
        },
        "confidence": {"score": 70, "label": "Medium"},
        "explanation": {"stance": "WATCH"},
        "method_results": {
            "dcf": {"available": True, "sensitivity": pd.DataFrame(
                [[1.0, 2.0]], index=["g=5%"], columns=["WACC=11%", "WACC=12%"]
            )},
        },
        "news": {"news": pd.DataFrame(), "news_score": None},
    }


@pytest.fixture
def client(tmp_path, monkeypatch):

    monkeypatch.setattr(main, "run_analysis", fake_analysis)

    main.app.state.db = Database(f"sqlite:///{tmp_path.as_posix()}/test.db")

    with TestClient(main.app) as test_client:
        yield test_client

    del main.app.state.db


def wait_for(client, job_id, timeout=10):

    deadline = time.time() + timeout

    while time.time() < deadline:
        body = client.get(f"/analyses/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)

    raise AssertionError("job did not finish")


def test_analysis_job_lifecycle(client):

    response = client.post("/analyses", json={"ticker": "tcs", "include_news": False})

    assert response.status_code == 202
    created = response.json()
    assert created["ticker"] == "TCS.NS"
    assert created["reused"] is False

    body = wait_for(client, created["job_id"])

    assert body["status"] == "done"
    assert body["summary"]["stance"] == "WATCH"
    assert body["result"]["fair_value"]["base_rounded"] == 150.0
    assert "disclaimer" in body
    # Infinite and missing values become null; frames become JSON.
    assert body["result"]["fundamentals_annual"][1]["ROE"] is None
    assert body["result"]["price_history"][-1]["SMA_200"] is None
    assert body["result"]["method_results"]["dcf"]["sensitivity"]["g=5%"]["WACC=12%"] == 2.0


def test_recent_result_is_reused(client):

    first = client.post("/analyses", json={"ticker": "TCS.NS", "include_news": False}).json()
    wait_for(client, first["job_id"])

    second = client.post("/analyses", json={"ticker": "TCS", "include_news": False}).json()

    assert second["reused"] is True
    assert second["job_id"] == first["job_id"]

    forced = client.post(
        "/analyses", json={"ticker": "TCS", "include_news": False, "force": True}
    ).json()

    assert forced["reused"] is False


def test_latest_and_history(client):

    job = client.post("/analyses", json={"ticker": "INFY", "include_news": False}).json()
    wait_for(client, job["job_id"])

    assert client.get("/stocks/infy/latest").json()["status"] == "done"

    history = client.get("/stocks/INFY.NS/history").json()["history"]

    assert history[0]["stance"] == "WATCH"


def test_invalid_ticker_rejected(client):

    response = client.post("/analyses", json={"ticker": "../etc/passwd"})

    assert response.status_code == 422


def test_unknown_job_is_404(client):

    assert client.get("/analyses/nope").status_code == 404


def test_engine_failure_is_reported(client, monkeypatch):

    def broken(ticker, include_news):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "run_analysis", broken)

    job = client.post("/analyses", json={"ticker": "X", "include_news": False}).json()

    body = wait_for(client, job["job_id"])

    assert body["status"] == "failed"
    assert "boom" in body["error"]


def test_serializer_handles_numpy_and_nan():

    assert to_jsonable({"a": np.float64("nan"), "b": np.int64(3), "c": pd.NaT}) == {
        "a": None, "b": 3, "c": None,
    }

    assert serialize_analysis({"status": "failed", "reason": "x"})["reason"] == "x"


def test_results_from_older_engine_are_not_reused(client):

    job = client.post("/analyses", json={"ticker": "TCS", "include_news": False}).json()
    wait_for(client, job["job_id"])

    # Simulate a result saved by an older engine version.
    db = main.app.state.db
    stored = db.get_job(job["job_id"])
    db.update_job(job["job_id"], result={**stored.result, "engine_version": "old"})

    again = client.post("/analyses", json={"ticker": "TCS", "include_news": False}).json()

    assert again["reused"] is False


def test_root_points_people_to_the_dashboard(client):

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "http://localhost:5173" in response.text
    assert client.get("/favicon.ico").status_code == 204
