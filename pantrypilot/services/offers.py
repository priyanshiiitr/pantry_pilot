"""Creating and listing surplus food offers, and the actions an agent can take on
one: claiming it to work on, assigning a pantry, dispatching a driver, cancelling,
or flagging it for a human.

DETERMINISTIC CODE: no AI involved. These functions just apply a decision that was
already made (by a human posting an offer, or by an agent choosing a pantry/driver)
to the database. Which pantry or driver to pick is decided in agents/, never here.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Delivery,
    DeliveryStatus,
    Driver,
    DispatchRequest,
    DispatchStatus,
    Offer,
    OfferStatus,
    Pantry,
    Restaurant,
)
from pantrypilot.web.schemas import OfferCreate

# How long a driver has to accept/decline before the worker (Step 9) treats a
# dispatch request as expired and moves on to another driver.
DISPATCH_REQUEST_WINDOW = timedelta(minutes=15)


def create_offer(session: Session, restaurant: Restaurant, payload: OfferCreate) -> Offer:
    """Save a new offer from `restaurant` and return it."""
    offer = Offer(
        restaurant=restaurant,
        title=payload.title,
        description=payload.description,
        quantity_text=payload.quantity_text,
        allergen_notes=payload.allergen_notes,
        pickup_deadline=payload.pickup_deadline,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return offer


def list_offers_for_restaurant(session: Session, restaurant: Restaurant) -> list[Offer]:
    """Return this restaurant's own offers, newest first."""
    query = (
        select(Offer)
        .where(Offer.restaurant_id == restaurant.id)
        .order_by(Offer.created_at.desc(), Offer.id.desc())
    )
    return list(session.scalars(query))


def get_offer_for_restaurant(session: Session, restaurant: Restaurant, offer_id: int) -> Offer:
    """Return one of this restaurant's own offers, or raise LookupError if it isn't theirs."""
    offer = session.scalar(
        select(Offer).where(Offer.id == offer_id, Offer.restaurant_id == restaurant.id)
    )
    if offer is None:
        raise LookupError(f"No offer {offer_id} for restaurant {restaurant.id}.")
    return offer


def list_all_offers(session: Session) -> list[Offer]:
    """Return every offer in the system, newest first. Used by the admin dashboard."""
    return list(session.scalars(select(Offer).order_by(Offer.created_at.desc(), Offer.id.desc())))


def claim_offer_for_agent(session: Session, offer: Offer) -> None:
    """Mark an offer as being worked on right now, before the agents start.

    Called once at the top of runner.run_case(), before any AI reasoning happens.
    """
    offer.status = OfferStatus.AGENT_WORKING
    offer.claimed_at = utc_now()
    session.commit()


def set_agent_summary(session: Session, offer: Offer, summary: str) -> None:
    """Save the latest plain-English update shown on the offer's detail page."""
    offer.agent_summary = summary
    session.commit()


def get_latest_delivery(session: Session, offer_id: int) -> Delivery | None:
    """Return the most recently created delivery plan for this offer, if any."""
    return session.scalar(
        select(Delivery).where(Delivery.offer_id == offer_id).order_by(Delivery.created_at.desc(), Delivery.id.desc())
    )


def assign_delivery(session: Session, offer: Offer, pantry: Pantry, reason: str) -> Delivery:
    """Record the agent's choice of pantry for this offer, as a new Delivery.

    This does NOT move the offer to "driver_requested" yet — that happens once a
    driver is actually asked, via send_dispatch_request. Until then the delivery
    sits as PLANNED: a pantry is chosen, but nobody has been asked to drive yet.
    """
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED, match_reasoning=reason)
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    return delivery


def send_dispatch_request(session: Session, delivery: Delivery, driver: Driver, reason: str) -> DispatchRequest:
    """Ask `driver` to do the pickup for `delivery`, and move the offer/delivery
    into the driver_requested state."""
    request = DispatchRequest(delivery=delivery, driver=driver, expires_at=utc_now() + DISPATCH_REQUEST_WINDOW)
    # Add `request` to the session BEFORE touching delivery.offer below: reading that
    # relationship can trigger SQLAlchemy's autoflush, which would otherwise try to
    # flush `request` while it's linked in-memory but not yet tracked by the session.
    session.add(request)
    delivery.status = DeliveryStatus.DRIVER_REQUESTED
    delivery.dispatch_reasoning = reason
    delivery.offer.status = OfferStatus.DRIVER_REQUESTED
    session.commit()
    session.refresh(request)
    return request


def flag_needs_human(session: Session, offer: Offer, reason: str) -> None:
    """Mark an offer as needing a human's attention.

    This is a placeholder for the real interrupt-based escalation that arrives in
    Step 11 (a Decision row the admin can act on). For now it just makes the
    situation visible: the offer's status badge turns amber in every dashboard.
    """
    offer.status = OfferStatus.NEEDS_HUMAN
    offer.agent_summary = f"Needs human review: {reason}"
    session.commit()


def cancel_offer(session: Session, offer: Offer, reason: str) -> None:
    """Cancel an offer entirely — used when nothing could be done for it."""
    offer.status = OfferStatus.CANCELLED
    offer.agent_summary = f"Cancelled: {reason}"
    session.commit()
