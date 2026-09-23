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

from fastapi import APIRouter, Header, HTTPException

from pantrypilot.config import settings
from pantrypilot.worker.jobs import expire_stale_dispatch_requests, pick_up_new_offers, resume_answered_decisions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["worker"])

# Each job is isolated, so one failure can't stop the others — the same
# guarantee the scheduled worker gives.
JOBS = (
    ("expire_stale_dispatch_requests", expire_stale_dispatch_requests),
    ("resume_answered_decisions", resume_answered_decisions),
    ("pick_up_new_offers", pick_up_new_offers),
)


@router.post("/tick")
def run_one_tick(x_tick_secret: str = Header(default="")) -> dict[str, object]:
    """Run each worker job once. Returns which ones succeeded.

    pick_up_new_offers runs last because it is the slow one: the quick
    housekeeping jobs shouldn't be starved if an agent run takes minutes and the
    caller times out.
    """
    if not settings.tick_secret:
        raise HTTPException(status_code=503, detail="TICK_SECRET is not configured, so /api/tick is disabled.")
    # compare_digest, not ==, so a wrong secret can't be guessed from timing.
    if not secrets.compare_digest(x_tick_secret, settings.tick_secret):
        raise HTTPException(status_code=401, detail="Bad tick secret.")

    results: dict[str, str] = {}
    for name, job in JOBS:
        try:
            job()
            results[name] = "ok"
        except Exception as error:
            logger.exception("Tick job %s failed", name)
            results[name] = f"failed: {error}"

    return {"ran": results}
