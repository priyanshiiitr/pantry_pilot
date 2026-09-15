"""Tools for reading an offer and knowing what time it is.

Each tool opens its own short-lived database session (database.SessionLocal())
rather than sharing one from a web request, because agents run outside of any
HTTP request — in a script here, and in the background worker from Step 9 onward.

We call `database.SessionLocal()` rather than `from pantrypilot.database import
SessionLocal` so that tests can swap in a temporary database by monkeypatching
`pantrypilot.database.SessionLocal` — a plain `from` import would freeze in the
real one at import time and never see the swap.
"""

from strands import tool

from pantrypilot import database
from pantrypilot.database import utc_now
from pantrypilot.models import Offer


@tool
def get_offer(offer_id: int) -> dict:
    """Get the full details of a surplus food offer, exactly as the restaurant wrote it.

    Args:
        offer_id: the id of the offer to look up.
    """
    with database.SessionLocal() as session:
        offer = session.get(Offer, offer_id)
        if offer is None:
            return {"error": f"No offer with id {offer_id}."}
        return {
            "id": offer.id,
            "title": offer.title,
            "description": offer.description,
            "quantity_text": offer.quantity_text,
            "allergen_notes": offer.allergen_notes,
            "pickup_deadline": offer.pickup_deadline.isoformat(),
            "status": offer.status,
            "restaurant_name": offer.restaurant.name,
            "restaurant_lat": offer.restaurant.lat,
            "restaurant_lon": offer.restaurant.lon,
        }


@tool
def get_current_time() -> dict:
    """Get the current date and time in UTC.

    You have no built-in sense of "now" — call this whenever you need to compare
    something against a deadline, or check whether a pantry is open right now.
    """
    return {"utc_now": utc_now().isoformat()}
