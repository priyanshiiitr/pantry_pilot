"""Creating and listing surplus food offers.

DETERMINISTIC CODE: no AI involved. This just saves what the restaurant typed.
The Intake agent (Step 6) is what turns this into clean, structured data.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.models import Offer, Restaurant
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
    return list(
        session.scalars(select(Offer).where(Offer.restaurant_id == restaurant.id).order_by(Offer.created_at.desc()))
    )


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
    return list(session.scalars(select(Offer).order_by(Offer.created_at.desc())))
