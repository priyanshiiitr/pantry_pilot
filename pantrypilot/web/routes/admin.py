"""Admin-only endpoints, under /api/admin.

DETERMINISTIC CODE: reads the database and records the admin's decision. It
never calls the model itself — answering a decision here just saves the choice;
the worker resumes the agent on its own schedule (see worker/jobs.py), so this
endpoint stays fast even though resuming can take a while.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import DecisionStatus, Role, User
from pantrypilot.services.activity_log import list_recent_log_entries
from pantrypilot.services.decisions import answer_decision, get_decision, list_pending_decisions
from pantrypilot.services.offers import list_all_offers
from pantrypilot.web.schemas import AgentLogEntryOut, AnswerDecisionRequest, DecisionOut, OfferAdminOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/offers", response_model=list[OfferAdminOut])
def list_all_offers_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[OfferAdminOut]:
    """List every offer in the system, newest first, with the restaurant's name attached.

    `_user` isn't read here — it exists only so Depends(require_role(...)) runs and
    blocks non-admins before this function body executes.
    """
    return [OfferAdminOut.from_offer(offer) for offer in list_all_offers(db)]


@router.get("/activity", response_model=list[AgentLogEntryOut])
def list_activity_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[AgentLogEntryOut]:
    """List the most recent agent activity: every tool call, result and decision, newest first."""
    return [AgentLogEntryOut.model_validate(entry) for entry in list_recent_log_entries(db)]


@router.get("/decisions", response_model=list[DecisionOut])
def list_pending_decisions_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[DecisionOut]:
    """List every decision waiting for an admin, newest first — the Decisions inbox."""
    return [DecisionOut.from_decision(decision) for decision in list_pending_decisions(db)]


@router.get("/decisions/{decision_id}", response_model=DecisionOut)
def get_decision_route(
    decision_id: int, _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> DecisionOut:
    """Return one decision's full card."""
    try:
        decision = get_decision(db, decision_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Decision not found.") from error
    return DecisionOut.from_decision(decision)


@router.post("/decisions/{decision_id}/answer", response_model=DecisionOut)
def answer_decision_route(
    decision_id: int,
    payload: AnswerDecisionRequest,
    user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> DecisionOut:
    """Record the admin's choice. The worker picks it up and resumes the agent
    on its own schedule (see worker/jobs.py:resume_answered_decisions) — this
    endpoint only saves the choice, it doesn't call the model itself."""
    try:
        decision = get_decision(db, decision_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Decision not found.") from error
    if decision.status != DecisionStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"This decision is already '{decision.status}'.")
    answer_decision(db, decision, payload.chosen_option, payload.admin_note, user.id)
    return DecisionOut.from_decision(decision)
