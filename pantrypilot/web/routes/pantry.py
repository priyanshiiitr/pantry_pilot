"""Pantry-only endpoints, under /api/pantry.

DETERMINISTIC CODE: reads and writes the database. No AI reasoning here — the
pantry is a human deciding whether to accept a delivery the agent proposed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.deliveries import (
    accept_delivery,
    decline_delivery,
    get_delivery_for_pantry,
    get_pending_deliveries_for_pantry,
)
from pantrypilot.services.profiles import get_pantry_for_user
from pantrypilot.web.schemas import DeclineRequest, PantryDeliveryOut, PantryProfileIn, PantryProfileOut

router = APIRouter(prefix="/api/pantry", tags=["pantry"])


@router.get("/profile", response_model=PantryProfileOut)
def get_profile(user: User = Depends(require_role(Role.PANTRY)), db: Session = Depends(get_db)) -> PantryProfileOut:
    """Return the logged-in pantry's own profile."""
    pantry = get_pantry_for_user(db, user)
    return PantryProfileOut.model_validate(pantry)


@router.put("/profile", response_model=PantryProfileOut)
def update_profile(
    payload: PantryProfileIn, user: User = Depends(require_role(Role.PANTRY)), db: Session = Depends(get_db)
) -> PantryProfileOut:
    """Save changes to the logged-in pantry's own profile."""
    pantry = get_pantry_for_user(db, user)
    pantry.name = payload.name
    pantry.address = payload.address
    pantry.lat = payload.lat
    pantry.lon = payload.lon
    pantry.phone = payload.phone
    pantry.capacity_kg_per_day = payload.capacity_kg_per_day
    pantry.has_fridge = payload.has_fridge
    pantry.has_freezer = payload.has_freezer
    pantry.dietary_restrictions = payload.dietary_restrictions
    pantry.opening_hours = payload.opening_hours
    pantry.accepting_donations = payload.accepting_donations
    pantry.notes = payload.notes
    db.commit()
    db.refresh(pantry)
    return PantryProfileOut.model_validate(pantry)


@router.get("/deliveries", response_model=list[PantryDeliveryOut])
def list_pending_deliveries_route(
    user: User = Depends(require_role(Role.PANTRY)), db: Session = Depends(get_db)
) -> list[PantryDeliveryOut]:
    """List deliveries assigned to this pantry that it hasn't accepted or declined yet."""
    pantry = get_pantry_for_user(db, user)
    return [PantryDeliveryOut.from_delivery(d) for d in get_pending_deliveries_for_pantry(db, pantry)]


@router.post("/deliveries/{delivery_id}/accept", response_model=PantryDeliveryOut)
def accept_delivery_route(
    delivery_id: int, user: User = Depends(require_role(Role.PANTRY)), db: Session = Depends(get_db)
) -> PantryDeliveryOut:
    """Accept an incoming delivery."""
    pantry = get_pantry_for_user(db, user)
    try:
        delivery = get_delivery_for_pantry(db, pantry, delivery_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Delivery not found.") from error
    accept_delivery(db, delivery)
    return PantryDeliveryOut.from_delivery(delivery)


@router.post("/deliveries/{delivery_id}/decline", response_model=PantryDeliveryOut)
def decline_delivery_route(
    delivery_id: int,
    payload: DeclineRequest,
    user: User = Depends(require_role(Role.PANTRY)),
    db: Session = Depends(get_db),
) -> PantryDeliveryOut:
    """Decline an incoming delivery — the offer goes back to the agent to find another pantry."""
    pantry = get_pantry_for_user(db, user)
    try:
        delivery = get_delivery_for_pantry(db, pantry, delivery_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Delivery not found.") from error
    decline_delivery(db, delivery, payload.reason)
    return PantryDeliveryOut.from_delivery(delivery)
