"""Creating and listing surplus food offers, and the offer-level actions an
agent can take: claiming it to work on, cancelling, flagging for a human, or
putting it back in the queue after a decline/timeout.

Delivery-specific actions (assigning a pantry, pantry accept/decline, pickup/
delivered) live in services/deliveries.py. Driver-dispatch actions (asking a
driver, accept/decline/expire) live in services/dispatch.py. This file only
ever touches the Offer row itself.

DETERMINISTIC CODE: no AI involved. These functions just apply a decision that was
already made (by a human posting an offer, or by an agent choosing a pantry/driver)
to the database. Which pantry or driver to pick is decided in agents/, never here.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Offer, OfferStatus, Restaurant
from pantrypilot.web.schemas import OfferCreate


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
    offer = session.scalar(select(Offer).where(Offer.id == offer_id, Offer.restaurant_id == restaurant.id))
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


def requeue_offer_for_retry(session: Session, offer: Offer, note: str) -> None:
    """Put a partly-worked offer back in the queue for the agent team to reconsider.

    Used when a pantry declines, a driver declines, or a driver never responds in
    time. The worker's normal "pick up new offers" check (every 15s, see
    worker/jobs.py) finds it again — `note` is saved as the offer's summary and
    also becomes the context the Coordinator is told about when it resumes, so it
    doesn't have to guess why it's looking at this offer again. Its per-offer
    session (agents/sessions.py) also remembers the earlier attempt on its own.
    """
    offer.status = OfferStatus.POSTED
    offer.claimed_at = None
    offer.agent_summary = note
    session.commit()


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
