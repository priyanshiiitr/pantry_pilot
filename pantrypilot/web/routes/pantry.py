"""Pantry-only endpoints, under /api/pantry.

DETERMINISTIC CODE: reads and writes the database. No AI reasoning here.
Incoming deliveries (accept/decline) arrive in Step 10.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.profiles import get_pantry_for_user
from pantrypilot.web.schemas import PantryProfileIn, PantryProfileOut

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
