"""Driver-only endpoints, under /api/driver.

DETERMINISTIC CODE: reads and writes the database. No AI reasoning here.
Dispatch requests (accept/decline, pickup/delivered) arrive in Step 10.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.profiles import get_driver_for_user
from pantrypilot.web.schemas import DriverProfileIn, DriverProfileOut

router = APIRouter(prefix="/api/driver", tags=["driver"])


@router.get("/profile", response_model=DriverProfileOut)
def get_profile(user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)) -> DriverProfileOut:
    """Return the logged-in driver's own profile."""
    driver = get_driver_for_user(db, user)
    return DriverProfileOut.model_validate(driver)


@router.put("/profile", response_model=DriverProfileOut)
def update_profile(
    payload: DriverProfileIn, user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> DriverProfileOut:
    """Save changes to the logged-in driver's own profile."""
    driver = get_driver_for_user(db, user)
    driver.name = payload.name
    driver.phone = payload.phone
    driver.lat = payload.lat
    driver.lon = payload.lon
    driver.service_radius_km = payload.service_radius_km
    driver.vehicle = payload.vehicle
    driver.max_kg = payload.max_kg
    driver.has_cooler = payload.has_cooler
    driver.availability = payload.availability
    driver.on_duty = payload.on_duty
    db.commit()
    db.refresh(driver)
    return DriverProfileOut.model_validate(driver)
