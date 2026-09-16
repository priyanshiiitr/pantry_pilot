"""Deliveries: the plan to send one offer to one pantry, and everything that
happens to it — the pantry accepting/declining, and a driver's pickup/delivered
updates once one is assigned.

DETERMINISTIC CODE: no AI involved, and no decisions about WHICH pantry or driver
— see agents/. This only applies actions once a person or an agent has decided.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DeliveryStatus, Driver, Offer, OfferStatus, Pantry, PantryResponse
from pantrypilot.services.offers import requeue_offer_for_retry


def get_latest_delivery(session: Session, offer_id: int) -> Delivery | None:
    """Return the most recently created delivery plan for this offer, if any."""
    query = select(Delivery).where(Delivery.offer_id == offer_id).order_by(Delivery.created_at.desc(), Delivery.id.desc())
    return session.scalar(query)


def assign_delivery(session: Session, offer: Offer, pantry: Pantry, reason: str) -> Delivery:
    """Record the agent's choice of pantry for this offer, as a new Delivery.

    This does NOT move the offer to "driver_requested" yet — that happens once a
    driver is actually asked, via dispatch.send_dispatch_request. Until then the
    delivery sits as PLANNED: a pantry is chosen, but nobody has been asked to
    drive yet.
    """
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED, match_reasoning=reason)
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    return delivery


def get_pending_deliveries_for_pantry(session: Session, pantry: Pantry) -> list[Delivery]:
    """Return deliveries assigned to this pantry that it hasn't accepted or declined yet."""
    query = (
        select(Delivery)
        .where(Delivery.pantry_id == pantry.id, Delivery.pantry_response == PantryResponse.PENDING)
        .order_by(Delivery.created_at.desc(), Delivery.id.desc())
    )
    return list(session.scalars(query))


def get_delivery_for_pantry(session: Session, pantry: Pantry, delivery_id: int) -> Delivery:
    """Return one of this pantry's own deliveries, or raise LookupError if it isn't theirs."""
    delivery = session.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.pantry_id == pantry.id))
    if delivery is None:
        raise LookupError(f"No delivery {delivery_id} for pantry {pantry.id}.")
    return delivery


def accept_delivery(session: Session, delivery: Delivery) -> None:
    """The pantry confirms it will take this delivery."""
    delivery.pantry_response = PantryResponse.ACCEPTED
    session.commit()


def decline_delivery(session: Session, delivery: Delivery, reason: str) -> None:
    """The pantry says no. This delivery attempt is over — the offer goes back in
    the queue so the agent can try a different pantry."""
    delivery.pantry_response = PantryResponse.DECLINED
    delivery.pantry_decline_reason = reason
    delivery.status = DeliveryStatus.CANCELLED
    requeue_offer_for_retry(session, delivery.offer, f"{delivery.pantry.name} declined this delivery: {reason}")


def get_active_trips_for_driver(session: Session, driver: Driver) -> list[Delivery]:
    """Return this driver's deliveries that are assigned but not yet delivered."""
    query = (
        select(Delivery)
        .where(Delivery.driver_id == driver.id, Delivery.status.in_([DeliveryStatus.DRIVER_ASSIGNED, DeliveryStatus.PICKED_UP]))
        .order_by(Delivery.created_at.desc(), Delivery.id.desc())
    )
    return list(session.scalars(query))


def get_trip_for_driver(session: Session, driver: Driver, delivery_id: int) -> Delivery:
    """Return one of this driver's own trips, or raise LookupError if it isn't theirs."""
    delivery = session.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.driver_id == driver.id))
    if delivery is None:
        raise LookupError(f"No trip {delivery_id} for driver {driver.id}.")
    return delivery


def mark_picked_up(session: Session, delivery: Delivery) -> None:
    """The driver has collected the food from the restaurant."""
    delivery.status = DeliveryStatus.PICKED_UP
    delivery.picked_up_at = utc_now()
    delivery.offer.status = OfferStatus.PICKED_UP
    session.commit()


def mark_delivered(session: Session, delivery: Delivery) -> None:
    """The driver has dropped the food off at the pantry — the job is done."""
    delivery.status = DeliveryStatus.DELIVERED
    delivery.delivered_at = utc_now()
    delivery.offer.status = OfferStatus.DELIVERED
    session.commit()
