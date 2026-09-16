"""Numbers and summaries for the admin dashboard: stat cards, the users list,
and one user's detail view.

DETERMINISTIC CODE: pure aggregation queries. No AI involved.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Decision,
    DecisionStatus,
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    Offer,
    OfferStatus,
    Role,
    User,
)

# Every status an offer can be in before it's finished one way or another.
ACTIVE_OFFER_STATUSES = [
    OfferStatus.POSTED,
    OfferStatus.AGENT_WORKING,
    OfferStatus.NEEDS_HUMAN,
    OfferStatus.DRIVER_REQUESTED,
    OfferStatus.DRIVER_ASSIGNED,
    OfferStatus.PICKED_UP,
]


def _start_of_today_utc() -> datetime:
    """Midnight UTC today — a simple day boundary for "completed today" stats."""
    return utc_now().replace(hour=0, minute=0, second=0, microsecond=0)


def get_dashboard_stats(session: Session) -> dict[str, Any]:
    """Overview numbers shown as stat cards on the admin home page."""
    active_offers = (
        session.scalar(select(func.count()).select_from(Offer).where(Offer.status.in_(ACTIVE_OFFER_STATUSES))) or 0
    )
    pending_decisions = (
        session.scalar(select(func.count()).select_from(Decision).where(Decision.status == DecisionStatus.PENDING))
        or 0
    )

    today_start = _start_of_today_utc()
    completed_today = (
        session.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(Delivery.status == DeliveryStatus.DELIVERED, Delivery.delivered_at >= today_start)
        )
        or 0
    )
    kg_today, meals_today = session.execute(
        select(func.coalesce(func.sum(Delivery.kg), 0.0), func.coalesce(func.sum(Delivery.meals), 0)).where(
            Delivery.status == DeliveryStatus.DELIVERED, Delivery.delivered_at >= today_start
        )
    ).one()
    kg_total, meals_total = session.execute(
        select(func.coalesce(func.sum(Delivery.kg), 0.0), func.coalesce(func.sum(Delivery.meals), 0)).where(
            Delivery.status == DeliveryStatus.DELIVERED
        )
    ).one()

    return {
        "active_offers": active_offers,
        "pending_decisions": pending_decisions,
        "completed_today": completed_today,
        "kg_saved_today": round(float(kg_today), 1),
        "meals_saved_today": int(meals_today),
        "kg_saved_total": round(float(kg_total), 1),
        "meals_saved_total": int(meals_total),
    }


def list_all_users(session: Session) -> list[User]:
    """Return every restaurant/pantry/driver/admin account, grouped by role."""
    return list(session.scalars(select(User).order_by(User.role, User.display_name)))


def get_user_status_label(user: User) -> str:
    """A short, human status for the users list — role-specific, blank if not applicable."""
    if user.role == Role.DRIVER and user.driver is not None:
        return "On duty" if user.driver.on_duty else "Off duty"
    if user.role == Role.PANTRY and user.pantry is not None:
        return "Accepting donations" if user.pantry.accepting_donations else "Paused"
    return ""


def get_user_or_raise(session: Session, user_id: int) -> User:
    """Return one user, or raise LookupError if they don't exist."""
    user = session.get(User, user_id)
    if user is None:
        raise LookupError(f"No user with id {user_id}.")
    return user


def get_recent_activity_for_user(session: Session, user: User) -> list[dict[str, Any]]:
    """A short list of this user's recent activity, shaped differently per role."""
    if user.role == Role.RESTAURANT and user.restaurant is not None:
        offers = session.scalars(
            select(Offer)
            .where(Offer.restaurant_id == user.restaurant.id)
            .order_by(Offer.created_at.desc(), Offer.id.desc())
            .limit(5)
        )
        return [{"title": offer.title, "status": offer.status, "created_at": offer.created_at} for offer in offers]

    if user.role == Role.PANTRY and user.pantry is not None:
        deliveries = session.scalars(
            select(Delivery)
            .where(Delivery.pantry_id == user.pantry.id)
            .order_by(Delivery.created_at.desc(), Delivery.id.desc())
            .limit(5)
        )
        return [
            {"title": delivery.offer.title, "status": delivery.status, "created_at": delivery.created_at}
            for delivery in deliveries
        ]

    if user.role == Role.DRIVER and user.driver is not None:
        requests = session.scalars(
            select(DispatchRequest)
            .where(DispatchRequest.driver_id == user.driver.id)
            .order_by(DispatchRequest.sent_at.desc(), DispatchRequest.id.desc())
            .limit(5)
        )
        return [
            {"title": request.delivery.offer.title, "status": request.status, "created_at": request.sent_at}
            for request in requests
        ]

    return []
