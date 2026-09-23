"""Numbers and summaries for the admin dashboard: stat cards, the users list,
and one user's detail view.

DETERMINISTIC CODE: pure aggregation queries. No AI involved.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Decision,
    DecisionStatus,
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    DispatchStatus,
    Driver,
    Offer,
    OfferStatus,
    PantryResponse,
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


#
# --- Admin "Overview" page -------------------------------------------------
#
# Everything below backs the single GET /api/admin/overview call the Overview
# page polls, so one screen refresh is one query round-trip rather than six.
#

# Offers the agent team has taken on but not yet routed to a pantry.
_BEING_EVALUATED_STATUSES = [OfferStatus.POSTED, OfferStatus.AGENT_WORKING, OfferStatus.NEEDS_HUMAN]

# Deliveries where a driver is committed and the food is actually moving.
_IN_TRANSIT_STATUSES = [DeliveryStatus.DRIVER_ASSIGNED, DeliveryStatus.PICKED_UP]

# Deliveries that are over, either way — the denominator for the match-rate card.
_FINISHED_DELIVERY_STATUSES = [DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED]


def _percent_change(today: float, yesterday: float) -> float | None:
    """Percent change today vs. yesterday, or None when yesterday had nothing to compare against.

    None is deliberate: a card showing no trend arrow is honest on day one, where
    "+100%" would imply a comparison that never happened.
    """
    if yesterday == 0:
        return None
    return round((today - yesterday) / yesterday * 100, 1)


# `end=None` means "no upper bound", which is what every "so far today" window
# wants. Passing utc_now() as an exclusive end instead would silently drop a row
# written in the same clock tick as the query — on Windows, where the system
# clock advances in ~16ms steps, that is frequent enough to lose real offers.
def _count_offers_created_between(session: Session, start: datetime, end: datetime | None = None) -> int:
    query = select(func.count()).select_from(Offer).where(Offer.created_at >= start)
    if end is not None:
        query = query.where(Offer.created_at < end)
    return session.scalar(query) or 0


def _sum_meals_delivered_between(session: Session, start: datetime, end: datetime | None = None) -> int:
    query = select(func.coalesce(func.sum(Delivery.meals), 0)).where(
        Delivery.status == DeliveryStatus.DELIVERED, Delivery.delivered_at >= start
    )
    if end is not None:
        query = query.where(Delivery.delivered_at < end)
    return int(session.scalar(query) or 0)


def get_network_activity(session: Session) -> dict[str, int]:
    """The five counts along the "Live network activity" strip, left to right.

    Each one is a real stage of the pipeline described in docs/architecture.md,
    so the strip reads as where work actually is right now, not as decoration.
    """
    restaurants_posting = (
        session.scalar(
            select(func.count(func.distinct(Offer.restaurant_id))).where(Offer.status.in_(ACTIVE_OFFER_STATUSES))
        )
        or 0
    )
    being_evaluated = (
        session.scalar(select(func.count()).select_from(Offer).where(Offer.status.in_(_BEING_EVALUATED_STATUSES))) or 0
    )
    today_start = _start_of_today_utc()
    pantries_receiving = (
        session.scalar(
            select(func.count(func.distinct(Delivery.pantry_id))).where(Delivery.created_at >= today_start)
        )
        or 0
    )
    drivers_en_route = (
        session.scalar(select(func.count()).select_from(Delivery).where(Delivery.status.in_(_IN_TRANSIT_STATUSES)))
        or 0
    )
    drivers_on_duty = (
        session.scalar(select(func.count()).select_from(Driver).where(Driver.on_duty.is_(True))) or 0
    )

    return {
        "restaurants_posting": restaurants_posting,
        "offers_being_evaluated": being_evaluated,
        "pantries_receiving_today": pantries_receiving,
        "drivers_en_route": drivers_en_route,
        "drivers_on_duty": drivers_on_duty,
    }


def get_overview_stats(session: Session) -> dict[str, Any]:
    """The four headline cards, each with a day-over-day trend where one is meaningful."""
    today_start = _start_of_today_utc()
    yesterday_start = today_start - timedelta(days=1)

    active_offers = (
        session.scalar(select(func.count()).select_from(Offer).where(Offer.status.in_(ACTIVE_OFFER_STATUSES))) or 0
    )
    pending_decisions = (
        session.scalar(select(func.count()).select_from(Decision).where(Decision.status == DecisionStatus.PENDING))
        or 0
    )

    # "Meals being rescued" counts food in flight as well as food already
    # delivered today — the point of the card is today's impact, and a delivery
    # that lands at 4pm shouldn't make the number go down.
    meals_in_flight = session.scalar(
        select(func.coalesce(func.sum(Delivery.meals), 0)).where(Delivery.status.notin_(_FINISHED_DELIVERY_STATUSES))
    )
    meals_delivered_today = _sum_meals_delivered_between(session, today_start)
    meals_rescued = int(meals_in_flight or 0) + meals_delivered_today

    delivered_total = (
        session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.status == DeliveryStatus.DELIVERED)
        )
        or 0
    )
    finished_total = (
        session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.status.in_(_FINISHED_DELIVERY_STATUSES))
        )
        or 0
    )
    match_rate = round(delivered_total / finished_total * 100, 1) if finished_total else None

    offers_today = _count_offers_created_between(session, today_start)
    offers_yesterday = _count_offers_created_between(session, yesterday_start, today_start)
    meals_yesterday = _sum_meals_delivered_between(session, yesterday_start, today_start)
    decisions_today = (
        session.scalar(select(func.count()).select_from(Decision).where(Decision.created_at >= today_start)) or 0
    )
    decisions_yesterday = (
        session.scalar(
            select(func.count())
            .select_from(Decision)
            .where(Decision.created_at >= yesterday_start, Decision.created_at < today_start)
        )
        or 0
    )

    return {
        "active_offers": active_offers,
        "active_offers_change": _percent_change(offers_today, offers_yesterday),
        "meals_rescued": meals_rescued,
        "meals_rescued_change": _percent_change(meals_delivered_today, meals_yesterday),
        "match_rate": match_rate,
        "pending_decisions": pending_decisions,
        "pending_decisions_change": _percent_change(decisions_today, decisions_yesterday),
    }


def get_recent_network_activity(session: Session, limit: int = 8) -> list[dict[str, Any]]:
    """The newest things that actually happened across the whole network, newest first.

    Built by merging real timestamps already on the offers/deliveries/decisions
    rows rather than by keeping a separate event table: there is exactly one
    source of truth for "when did this happen", and the feed can never drift
    from it.

    This is deliberately business-level ("matched", "delivered"). The agent's own
    tool-by-tool reasoning lives in the agent_log table and the Activity page.
    """
    events: list[dict[str, Any]] = []

    # Each event names its restaurant/pantry, which are relationships. Left to
    # load lazily that is one extra round trip per row — harmless against a local
    # SQLite file, and 21 queries taking ten seconds against a hosted database.
    recent_offers = session.scalars(
        select(Offer)
        .options(selectinload(Offer.restaurant))
        .order_by(Offer.created_at.desc(), Offer.id.desc())
        .limit(limit)
    )
    for offer in recent_offers:
        events.append(
            {
                "kind": "offer_posted",
                "title": "New surplus offer",
                "detail": f"{offer.quantity_text} from {offer.restaurant.name}",
                "status": offer.status,
                "offer_id": offer.id,
                "at": offer.created_at,
            }
        )

    recent_deliveries = session.scalars(
        select(Delivery)
        .options(selectinload(Delivery.offer), selectinload(Delivery.pantry))
        .order_by(Delivery.created_at.desc(), Delivery.id.desc())
        .limit(limit)
    )
    for delivery in recent_deliveries:
        events.append(
            {
                "kind": "matched",
                "title": "Donation matched",
                "detail": f"{delivery.offer.title} → {delivery.pantry.name}",
                "status": delivery.status,
                "offer_id": delivery.offer_id,
                "at": delivery.created_at,
            }
        )
        if delivery.delivered_at is not None:
            events.append(
                {
                    "kind": "delivered",
                    "title": "Delivery completed",
                    "detail": f"{delivery.meals or 0} meals to {delivery.pantry.name}",
                    "status": DeliveryStatus.DELIVERED,
                    "offer_id": delivery.offer_id,
                    "at": delivery.delivered_at,
                }
            )

    recent_decisions = session.scalars(
        select(Decision)
        .options(selectinload(Decision.offer))
        .order_by(Decision.created_at.desc(), Decision.id.desc())
        .limit(limit)
    )
    for decision in recent_decisions:
        events.append(
            {
                "kind": "needs_human",
                "title": "Agent needs a human decision",
                # The agent wrote this title itself when it called ask_admin.
                "detail": decision.card.get("title", decision.offer.title),
                "status": decision.status,
                "offer_id": decision.offer_id,
                "at": decision.created_at,
            }
        )

    events.sort(key=lambda event: event["at"], reverse=True)
    return events[:limit]


def list_switchable_accounts(session: Session) -> list[dict[str, Any]]:
    """Every account an admin can preview, with how much work is waiting on each.

    The waiting count is the point: after the agents dispatch a delivery, exactly
    one driver and one pantry can act on it, and without this the admin has to
    guess which of eight drivers that is. Ordered by waiting work first, so
    whoever the agents are actually blocked on is at the top of the list.
    """
    pending_by_driver = dict(
        session.execute(
            select(DispatchRequest.driver_id, func.count())
            .where(DispatchRequest.status == DispatchStatus.REQUESTED)
            .group_by(DispatchRequest.driver_id)
        ).all()
    )
    pending_by_pantry = dict(
        session.execute(
            select(Delivery.pantry_id, func.count())
            .where(Delivery.pantry_response == PantryResponse.PENDING)
            .group_by(Delivery.pantry_id)
        ).all()
    )
    active_by_restaurant = dict(
        session.execute(
            select(Offer.restaurant_id, func.count())
            .where(Offer.status.in_(ACTIVE_OFFER_STATUSES))
            .group_by(Offer.restaurant_id)
        ).all()
    )

    accounts: list[dict[str, Any]] = []
    for user in session.scalars(select(User).where(User.is_active.is_(True)).order_by(User.id)):
        if user.role == Role.DRIVER and user.driver is not None:
            waiting, label = pending_by_driver.get(user.driver.id, 0), "pickup requests"
        elif user.role == Role.PANTRY and user.pantry is not None:
            waiting, label = pending_by_pantry.get(user.pantry.id, 0), "deliveries to confirm"
        elif user.role == Role.RESTAURANT and user.restaurant is not None:
            waiting, label = active_by_restaurant.get(user.restaurant.id, 0), "offers in progress"
        else:
            continue

        accounts.append(
            {
                "user_id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "waiting_count": waiting,
                "waiting_label": label,
            }
        )

    accounts.sort(key=lambda account: (-account["waiting_count"], account["display_name"]))
    return accounts


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
