"""Tests for POST /api/tick (web/routes/tick.py).

This is the one endpoint reachable without a login, because the caller is an
external scheduler with no session. These pin down that it stays shut unless a
secret is both configured and correct — left open, anyone on the internet could
drive agent runs and spend the model budget.
"""

import pytest
from fastapi.testclient import TestClient

from pantrypilot.config import settings
from pantrypilot.web.routes import tick

SECRET = "test-tick-secret"


@pytest.fixture
def tick_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tick_secret", SECRET)


@pytest.fixture
def no_jobs_run(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the real jobs so no agent, model or network is touched."""
    ran: list[str] = []
    monkeypatch.setattr(
        tick,
        "JOBS",
        (
            ("expire_stale_dispatch_requests", lambda: ran.append("expire")),
            ("resume_answered_decisions", lambda: ran.append("resume")),
            ("pick_up_new_offers", lambda: ran.append("pick_up")),
        ),
    )
    return ran


def test_tick_runs_every_job(client: TestClient, tick_enabled: None, no_jobs_run: list[str]) -> None:
    """One call does one pass of the same three jobs the worker schedules."""
    response = client.post("/api/tick", headers={"X-Tick-Secret": SECRET})

    assert response.status_code == 200
    assert response.json()["ran"] == {
        "expire_stale_dispatch_requests": "ok",
        "resume_answered_decisions": "ok",
        "pick_up_new_offers": "ok",
    }
    assert no_jobs_run == ["expire", "resume", "pick_up"]


def test_the_slow_job_runs_last(client: TestClient, tick_enabled: None, no_jobs_run: list[str]) -> None:
    """Picking up new offers can take minutes; housekeeping shouldn't be starved behind it."""
    client.post("/api/tick", headers={"X-Tick-Secret": SECRET})

    assert no_jobs_run[-1] == "pick_up"


def test_a_failing_job_does_not_stop_the_others(
    client: TestClient, tick_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same isolation the scheduled worker gives: one bad job never blocks the rest."""

    def explode() -> None:
        raise RuntimeError("model provider is down")

    ran: list[str] = []
    monkeypatch.setattr(
        tick, "JOBS", (("resume_answered_decisions", explode), ("pick_up_new_offers", lambda: ran.append("pick_up")))
    )

    body = client.post("/api/tick", headers={"X-Tick-Secret": SECRET}).json()["ran"]

    assert "failed" in body["resume_answered_decisions"]
    assert body["pick_up_new_offers"] == "ok"
    assert ran == ["pick_up"]


def test_a_wrong_secret_is_refused(client: TestClient, tick_enabled: None, no_jobs_run: list[str]) -> None:
    response = client.post("/api/tick", headers={"X-Tick-Secret": "wrong"})

    assert response.status_code == 401
    assert no_jobs_run == []


def test_a_missing_secret_is_refused(client: TestClient, tick_enabled: None, no_jobs_run: list[str]) -> None:
    """No header at all must not fall through to an empty-string match."""
    response = client.post("/api/tick")

    assert response.status_code == 401
    assert no_jobs_run == []


def test_the_endpoint_is_disabled_when_no_secret_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, no_jobs_run: list[str]
) -> None:
    """Unconfigured means off, not open.

    Otherwise a deployment that forgot TICK_SECRET would expose a way for anyone
    to trigger agent runs, and an empty header would match an empty secret.
    """
    monkeypatch.setattr(settings, "tick_secret", "")

    response = client.post("/api/tick", headers={"X-Tick-Secret": ""})

    assert response.status_code == 503
    assert no_jobs_run == []
