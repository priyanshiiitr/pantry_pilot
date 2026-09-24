"""POST /api/tick — run one round of the worker's jobs, on request.

Why this exists: the worker (pantrypilot/worker/) is a process that never exits,
which free serverless and free web hosting won't run. Rather than requiring a
paid always-on worker just to demo the project, this endpoint does exactly one
pass of the same three jobs, so an external scheduler (cron-job.org, GitHub
Actions, Render Cron) can drive the agents by calling it on a timer.

It is the same code either way — worker/jobs.py — so nothing about the agents
changes with how they are triggered. See docs/aws-deployment.md, where the same
jobs map onto EventBridge.

Protected by TICK_SECRET rather than a login, because the caller is a scheduler
with no session. Without that secret set, the endpoint refuses to run at all:
left open, anyone could drive an agent run and spend the model budget.
"""

import logging
import secrets
import threading

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from pantrypilot.config import settings
from pantrypilot.worker.jobs import expire_stale_dispatch_requests, pick_up_new_offers, resume_answered_decisions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["worker"])

# Each job is isolated, so one failure can't stop the others — the same
# guarantee the scheduled worker gives. pick_up_new_offers runs last because it
# is the slow one, and the quick housekeeping shouldn't queue behind it.
JOBS = (
    ("expire_stale_dispatch_requests", expire_stale_dispatch_requests),
    ("resume_answered_decisions", resume_answered_decisions),
    ("pick_up_new_offers", pick_up_new_offers),
)

# Only one tick's work runs at a time. A scheduler firing every minute would
# otherwise stack up overlapping agent runs, since one run can take several
# minutes on a rate-limited model tier — and they would then compete for the
# same token budget and make each other slower still.
_tick_lock = threading.Lock()


def run_jobs_once() -> None:
    """Run every job once, skipping entirely if a previous tick is still going."""
    if not _tick_lock.acquire(blocking=False):
        logger.info("Tick skipped: the previous one is still running.")
        return
    try:
        for name, job in JOBS:
            try:
                job()
            except Exception:
                logger.exception("Tick job %s failed", name)
    finally:
        _tick_lock.release()


@router.post("/tick", status_code=202)
def run_one_tick(background_tasks: BackgroundTasks, x_tick_secret: str = Header(default="")) -> dict[str, object]:
    """Start one pass of the worker's jobs, and answer straight away.

    Deliberately does NOT wait for the work. pick_up_new_offers runs the whole
    agent team, which takes minutes on a free model tier, while cron services
    time out in around thirty seconds — so a scheduler waiting for the result
    records every successful run as a failure and retries it.

    202 means "accepted, started", which is the honest answer here: whether the
    agents succeed is visible in the activity log, not in this response.
    """
    if not settings.tick_secret:
        raise HTTPException(status_code=503, detail="TICK_SECRET is not configured, so /api/tick is disabled.")
    # compare_digest, not ==, so a wrong secret can't be guessed from timing.
    if not secrets.compare_digest(x_tick_secret, settings.tick_secret):
        raise HTTPException(status_code=401, detail="Bad tick secret.")

    already_running = _tick_lock.locked()
    background_tasks.add_task(run_jobs_once)
    return {
        "started": not already_running,
        "detail": "A previous tick is still running; this one will be skipped."
        if already_running
        else "Agent jobs started in the background.",
    }
