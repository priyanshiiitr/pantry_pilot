"""Recording what an agent run did: one `agent_runs` row per invocation, and the
detailed `agent_log` timeline of tool calls and decisions within it.

DETERMINISTIC CODE: this only writes down what already happened. It never decides
anything — compare with agents/hooks/reasoning_log_hook.py, which turns Strands'
tool-call events into calls to the functions here.

Each function opens its own short-lived database session, the same pattern used
by the agent tools (agents/tools/*), because this is called from agent code that
runs outside any HTTP request and has no session of its own to reuse.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot import database
from pantrypilot.database import utc_now
from pantrypilot.models import AgentLog, AgentRun

# Note: we call database.SessionLocal() (not `from ... import SessionLocal`) so that
# tests can monkeypatch pantrypilot.database.SessionLocal to a temporary database —
# a plain `from` import would freeze in the real one at import time and never see the swap.


def start_agent_run(trigger: str, offer_id: int | None = None) -> int:
    """Record that an agent run is starting, and return its id."""
    with database.SessionLocal() as session:
        run = AgentRun(offer_id=offer_id, trigger=trigger)
        session.add(run)
        session.commit()
        return run.id


def finish_agent_run(
    run_id: int, *, stop_reason: str | None, outcome: dict[str, Any] | None = None, error: str | None = None
) -> None:
    """Record that an agent run finished, with why it stopped and what it produced."""
    with database.SessionLocal() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            return
        run.finished_at = utc_now()
        run.stop_reason = stop_reason
        run.outcome = outcome
        run.error = error
        session.commit()


def log_event(
    run_id: int | None,
    offer_id: int | None,
    agent_name: str,
    event_type: str,
    summary: str,
    *,
    tool_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add one line to the activity timeline (a tool call, a result, a decision, ...)."""
    with database.SessionLocal() as session:
        session.add(
            AgentLog(
                run_id=run_id,
                offer_id=offer_id,
                agent_name=agent_name,
                event_type=event_type,
                tool_name=tool_name,
                summary=summary,
                details=details,
            )
        )
        session.commit()


def list_recent_log_entries(session: Session, limit: int = 200) -> list[AgentLog]:
    """Return the most recent activity log entries, newest first. Used by the admin dashboard."""
    query = select(AgentLog).order_by(AgentLog.created_at.desc(), AgentLog.id.desc()).limit(limit)
    return list(session.scalars(query))
