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
    """One call does one pass of the same three jobs the worker schedules.

    202, not 200: the endpoint answers before the work finishes. TestClient runs
    background tasks before returning, so the jobs have still run by the time we
    look.
    """
    response = client.post("/api/tick", headers={"X-Tick-Secret": SECRET})

    assert response.status_code == 202
    assert response.json()["started"] is True
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

    response = client.post("/api/tick", headers={"X-Tick-Secret": SECRET})

    assert response.status_code == 202
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


def test_a_trailing_slash_in_a_configured_origin_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copying a URL from the address bar gives you a trailing slash.

    A browser's Origin header is scheme://host:port with no path, so the two
    never match and CORS fails silently — the deployed site just looks
    permanently logged out, with nothing in the error naming the cause.
    """
    monkeypatch.setattr(settings, "frontend_origins", "https://app.vercel.app/, https://other.app/ ")

    assert settings.allowed_origins == ["https://app.vercel.app", "https://other.app"]


def test_origins_without_slashes_are_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_origins", "https://app.vercel.app")

    assert settings.allowed_origins == ["https://app.vercel.app"]


def test_no_configured_origins_means_no_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local development proxies /api, so CORS shouldn't be involved at all."""
    monkeypatch.setattr(settings, "frontend_origins", "")

    assert settings.allowed_origins == []


def test_the_response_does_not_wait_for_the_agents(client: TestClient, tick_enabled: None, monkeypatch) -> None:
    """The whole point of 202: a slow agent run must not become a cron timeout.

    pick_up_new_offers runs the full agent team, which takes minutes on a free
    model tier, while cron services give up after about thirty seconds. Waiting
    made every successful run look like a failure — and get retried.
    """
    from fastapi import BackgroundTasks

    scheduled: list[object] = []
    monkeypatch.setattr(BackgroundTasks, "add_task", lambda self, fn, *a, **k: scheduled.append(fn))

    response = client.post("/api/tick", headers={"X-Tick-Secret": SECRET})

    assert response.status_code == 202
    assert len(scheduled) == 1  # handed off, not executed inline


def test_an_overlapping_tick_is_skipped_not_queued(tick_enabled: None, no_jobs_run: list[str]) -> None:
    """A minute-by-minute schedule must not stack up concurrent agent runs.

    They would compete for the same rate-limited token budget and make each
    other slower, so a tick arriving while one is in flight does nothing.
    """
    tick._tick_lock.acquire()
    try:
        tick.run_jobs_once()
    finally:
        tick._tick_lock.release()

    assert no_jobs_run == []


def test_the_lock_is_released_even_if_a_job_raises(tick_enabled: None, monkeypatch) -> None:
    """A crashed job must not wedge the endpoint into skipping forever."""

    def explode() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(tick, "JOBS", (("pick_up_new_offers", explode),))
    tick.run_jobs_once()

    assert not tick._tick_lock.locked()
