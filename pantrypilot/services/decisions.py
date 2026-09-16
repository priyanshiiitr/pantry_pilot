"""The admin Decisions inbox: saving a paused agent's question, and recording
the admin's answer.

DETERMINISTIC CODE: no AI involved. This never decides anything itself — it
only stores the agent's own escalation (see agents/tools/human_tools.py) and
the admin's own choice, and marks the handoff points in between.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Decision, DecisionKind, DecisionStatus


def create_decision(
    session: Session, offer_id: int, interrupt_id: str, interrupt_name: str, card: dict[str, Any]
) -> Decision:
    """Save a new pending decision from an agent's ask_admin interrupt."""
    decision = Decision(
        offer_id=offer_id,
        kind=DecisionKind.AGENT_ESCALATION,
        interrupt_id=interrupt_id,
        interrupt_name=interrupt_name,
        card=card,
        status=DecisionStatus.PENDING,
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


def list_pending_decisions(session: Session) -> list[Decision]:
    """Return every decision waiting for an admin, newest first."""
    query = (
        select(Decision)
        .where(Decision.status == DecisionStatus.PENDING)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
    )
    return list(session.scalars(query))


def list_answered_decisions(session: Session) -> list[Decision]:
    """Return decisions an admin has answered but the agent hasn't resumed yet.

    Used by the worker (worker/jobs.py:resume_answered_decisions) — answering is
    a fast, deterministic API call; actually resuming calls the model, which can
    take a while, so it happens separately on the worker's own schedule.
    """
    query = (
        select(Decision)
        .where(Decision.status == DecisionStatus.ANSWERED)
        .order_by(Decision.answered_at, Decision.id)
    )
    return list(session.scalars(query))


def get_decision(session: Session, decision_id: int) -> Decision:
    """Return one decision, or raise LookupError if it doesn't exist."""
    decision = session.get(Decision, decision_id)
    if decision is None:
        raise LookupError(f"No decision with id {decision_id}.")
    return decision


def answer_decision(
    session: Session, decision: Decision, chosen_option: str, admin_note: str | None, answered_by_user_id: int
) -> None:
    """Record the admin's choice. Does NOT resume the agent — see list_answered_decisions."""
    decision.status = DecisionStatus.ANSWERED
    decision.chosen_option = chosen_option
    decision.admin_note = admin_note
    decision.answered_by_user_id = answered_by_user_id
    decision.answered_at = utc_now()
    session.commit()


def mark_decision_resumed(session: Session, decision: Decision) -> None:
    """Record that the agent successfully picked back up after this decision."""
    decision.status = DecisionStatus.RESUMED
    decision.resumed_at = utc_now()
    session.commit()


def mark_decision_failed(session: Session, decision: Decision) -> None:
    """Record that resuming the agent for this decision raised an error.

    The decision stays visible (status=failed) rather than silently vanishing,
    so an admin knows to look into it — the details land in agent_runs.error.
    """
    decision.status = DecisionStatus.FAILED
    session.commit()
