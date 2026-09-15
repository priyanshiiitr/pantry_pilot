"""How much of the recent food supply each pantry has already received.

DETERMINISTIC CODE: this only computes numbers. It never decides what's "fair" —
that judgment call belongs to the Matching agent, which reads these numbers and
reasons about them (see agents/matching_agent.py).
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DeliveryStatus, Pantry

FAIRNESS_LOOKBACK_DAYS = 7

# A delivery counts toward "received" as soon as it's planned, not only once it
# arrives — otherwise the agent could over-commit a pantry by planning several
# deliveries to it before any of them shows as "delivered". Shared with
# check_pantry_capacity in agents/tools/pantry_tools.py, which uses the same rule.
COUNTED_DELIVERY_STATUSES = [
    DeliveryStatus.PLANNED,
    DeliveryStatus.DRIVER_REQUESTED,
    DeliveryStatus.DRIVER_ASSIGNED,
    DeliveryStatus.PICKED_UP,
    DeliveryStatus.DELIVERED,
]


def _kg_received_since(session: Session, pantry_id: int, since: object) -> float:
    """Total kg counted toward `pantry_id` since the `since` timestamp."""
    total = session.scalar(
        select(func.sum(Delivery.kg)).where(
            Delivery.pantry_id == pantry_id,
            Delivery.status.in_(COUNTED_DELIVERY_STATUSES),
            Delivery.created_at >= since,
        )
    )
    return float(total or 0.0)


def fairness_snapshot(session: Session, pantry_id: int, extra_kg: float) -> dict:
    """Numbers describing how `pantry_id` compares with other pantries, and how adding
    `extra_kg` more would change that. The caller (an agent tool) decides what to do
    with these numbers — this function only reports them.
    """
    since = utc_now() - timedelta(days=FAIRNESS_LOOKBACK_DAYS)
    all_pantry_ids = list(session.scalars(select(Pantry.id)))
    kg_by_pantry = {pid: _kg_received_since(session, pid, since) for pid in all_pantry_ids}

    this_pantry_kg = kg_by_pantry.get(pantry_id, 0.0)
    average_kg = sum(kg_by_pantry.values()) / len(kg_by_pantry) if kg_by_pantry else 0.0
    projected_kg = this_pantry_kg + extra_kg

    return {
        "pantry_id": pantry_id,
        "lookback_days": FAIRNESS_LOOKBACK_DAYS,
        "kg_received_last_7_days": round(this_pantry_kg, 1),
        "average_kg_received_last_7_days_across_all_pantries": round(average_kg, 1),
        "kg_if_this_delivery_is_added": round(projected_kg, 1),
        "currently_above_average": this_pantry_kg > average_kg,
        "would_be_above_average_after_this_delivery": projected_kg > average_kg,
    }
