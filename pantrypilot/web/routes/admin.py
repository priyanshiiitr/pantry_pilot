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
from pantrypilot.services.dashboard import (
    get_dashboard_stats,
    get_recent_activity_for_user,
    get_user_or_raise,
    get_user_status_label,
    list_all_users,
)
from pantrypilot.services.decisions import answer_decision, get_decision, list_pending_decisions
from pantrypilot.services.memory import deactivate_fact, get_subject_name, list_active_facts
from pantrypilot.services.offers import list_all_offers
from pantrypilot.web.schemas import (
    AdminUserDetailOut,
    AdminUserOut,
    AgentLogEntryOut,
    AgentMemoryOut,
    AnswerDecisionRequest,
    DashboardStatsOut,
    DecisionOut,
    DriverProfileOut,
    OfferAdminOut,
    PantryProfileOut,
    RestaurantProfileOut,
)

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


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> DashboardStatsOut:
    """The stat cards on the admin home page."""
    return DashboardStatsOut(**get_dashboard_stats(db))


@router.get("/users", response_model=list[AdminUserOut])
def list_all_users_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[AdminUserOut]:
    """List every restaurant, pantry, driver and admin account."""
    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            display_name=user.display_name,
            status_label=get_user_status_label(user),
            created_at=user.created_at,
        )
        for user in list_all_users(db)
    ]


@router.get("/users/{user_id}", response_model=AdminUserDetailOut)
def get_user_detail_route(
    user_id: int, _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> AdminUserDetailOut:
    """One user's profile fields (reusing the same schemas they see themselves)
    plus a short list of their recent activity."""
    try:
        user = get_user_or_raise(db, user_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="User not found.") from error

    profile: dict = {}
    if user.role == Role.RESTAURANT and user.restaurant is not None:
        profile = RestaurantProfileOut.model_validate(user.restaurant).model_dump()
    elif user.role == Role.PANTRY and user.pantry is not None:
        profile = PantryProfileOut.model_validate(user.pantry).model_dump()
    elif user.role == Role.DRIVER and user.driver is not None:
        profile = DriverProfileOut.model_validate(user.driver).model_dump()

    return AdminUserDetailOut(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        created_at=user.created_at,
        profile=profile,
        recent_activity=get_recent_activity_for_user(db, user),
    )


@router.get("/memory", response_model=list[AgentMemoryOut])
def list_memory_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[AgentMemoryOut]:
    """List every fact the agents can currently recall, newest first."""
    return [
        AgentMemoryOut(
            id=fact.id,
            subject_type=fact.subject_type,
            subject_id=fact.subject_id,
            subject_name=get_subject_name(db, fact.subject_type, fact.subject_id),
            fact=fact.fact,
            source=fact.source,
            created_at=fact.created_at,
        )
        for fact in list_active_facts(db)
    ]


@router.delete("/memory/{fact_id}")
def delete_memory_route(
    fact_id: int, _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> dict[str, str]:
    """Stop the agents from recalling this fact (soft delete — see services/memory.py)."""
    try:
        deactivate_fact(db, fact_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Fact not found.") from error
    return {"status": "deleted"}
