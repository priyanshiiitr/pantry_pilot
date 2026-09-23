"""Restaurant-only endpoints, under /api/restaurant.

DETERMINISTIC CODE: reads and writes the database. No AI reasoning here.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.activity_log import list_log_entries_for_offer
from pantrypilot.services.offers import create_offer, get_offer_for_restaurant, list_offers_for_restaurant
from pantrypilot.services.profiles import get_restaurant_for_user
from pantrypilot.services.progress import get_offer_progress
from pantrypilot.web.schemas import (
    AgentLogEntryOut,
    OfferCreate,
    OfferOut,
    OfferProgressOut,
    OfferStageOut,
    RestaurantProfileIn,
    RestaurantProfileOut,
)

router = APIRouter(prefix="/api/restaurant", tags=["restaurant"])


@router.get("/profile", response_model=RestaurantProfileOut)
def get_profile(
    user: User = Depends(require_role(Role.RESTAURANT)), db: Session = Depends(get_db)
) -> RestaurantProfileOut:
    """Return the logged-in restaurant's own profile."""
    restaurant = get_restaurant_for_user(db, user)
    return RestaurantProfileOut.model_validate(restaurant)


@router.put("/profile", response_model=RestaurantProfileOut)
def update_profile(
    payload: RestaurantProfileIn,
    user: User = Depends(require_role(Role.RESTAURANT)),
    db: Session = Depends(get_db),
) -> RestaurantProfileOut:
    """Save changes to the logged-in restaurant's own profile."""
    restaurant = get_restaurant_for_user(db, user)
    restaurant.name = payload.name
    restaurant.address = payload.address
    restaurant.lat = payload.lat
    restaurant.lon = payload.lon
    restaurant.phone = payload.phone
    db.commit()
    db.refresh(restaurant)
    return RestaurantProfileOut.model_validate(restaurant)


@router.post("/offers", response_model=OfferOut)
def create_offer_route(
    payload: OfferCreate, user: User = Depends(require_role(Role.RESTAURANT)), db: Session = Depends(get_db)
) -> OfferOut:
    """Post a new surplus food offer."""
    restaurant = get_restaurant_for_user(db, user)
    offer = create_offer(db, restaurant, payload)
    return OfferOut.model_validate(offer)


@router.get("/offers", response_model=list[OfferOut])
def list_offers_route(
    user: User = Depends(require_role(Role.RESTAURANT)), db: Session = Depends(get_db)
) -> list[OfferOut]:
    """List this restaurant's own offers, newest first."""
    restaurant = get_restaurant_for_user(db, user)
    return [OfferOut.model_validate(offer) for offer in list_offers_for_restaurant(db, restaurant)]


@router.get("/offers/{offer_id}", response_model=OfferOut)
def get_offer_route(
    offer_id: int, user: User = Depends(require_role(Role.RESTAURANT)), db: Session = Depends(get_db)
) -> OfferOut:
    """Return one of this restaurant's own offers."""
    restaurant = get_restaurant_for_user(db, user)
    try:
        offer = get_offer_for_restaurant(db, restaurant, offer_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Offer not found.") from error
    return OfferOut.model_validate(offer)


@router.get("/offers/{offer_id}/activity", response_model=OfferProgressOut)
def get_offer_activity_route(
    offer_id: int, user: User = Depends(require_role(Role.RESTAURANT)), db: Session = Depends(get_db)
) -> OfferProgressOut:
    """Where this offer has got to, and everything the agents did getting there.

    Returned together because the page shows them together: two separate polls
    could disagree, showing a stage as done while the log that proves it hasn't
    arrived yet.

    Scoped through get_offer_for_restaurant so a restaurant can only ever read
    its own offers.
    """
    restaurant = get_restaurant_for_user(db, user)
    try:
        get_offer_for_restaurant(db, restaurant, offer_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Offer not found.") from error

    return OfferProgressOut(
        stages=[OfferStageOut(**stage) for stage in get_offer_progress(db, offer_id)],
        entries=[AgentLogEntryOut.model_validate(entry) for entry in list_log_entries_for_offer(db, offer_id)],
    )
