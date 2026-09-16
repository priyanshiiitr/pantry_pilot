"""Driver-only endpoints, under /api/driver.

DETERMINISTIC CODE: reads and writes the database. No AI reasoning here — the
driver is a human deciding whether to accept a pickup the agent proposed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.deliveries import (
    get_active_trips_for_driver,
    get_trip_for_driver,
    mark_delivered,
    mark_picked_up,
)
from pantrypilot.services.dispatch import (
    accept_dispatch_request,
    decline_dispatch_request,
    get_dispatch_request_for_driver,
    get_pending_dispatch_requests_for_driver,
)
from pantrypilot.services.profiles import get_driver_for_user
from pantrypilot.web.schemas import (
    DeclineRequest,
    DriverDispatchRequestOut,
    DriverProfileIn,
    DriverProfileOut,
    DriverTripOut,
)

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


@router.get("/dispatch-requests", response_model=list[DriverDispatchRequestOut])
def list_pending_dispatch_requests_route(
    user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> list[DriverDispatchRequestOut]:
    """List pickup requests sent to this driver that they haven't answered yet."""
    driver = get_driver_for_user(db, user)
    requests = get_pending_dispatch_requests_for_driver(db, driver)
    return [DriverDispatchRequestOut.from_request(r) for r in requests]


@router.post("/dispatch-requests/{request_id}/accept", response_model=DriverDispatchRequestOut)
def accept_dispatch_request_route(
    request_id: int, user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> DriverDispatchRequestOut:
    """Accept a pickup request."""
    driver = get_driver_for_user(db, user)
    try:
        request = get_dispatch_request_for_driver(db, driver, request_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Dispatch request not found.") from error
    accept_dispatch_request(db, request)
    return DriverDispatchRequestOut.from_request(request)


@router.post("/dispatch-requests/{request_id}/decline", response_model=DriverDispatchRequestOut)
def decline_dispatch_request_route(
    request_id: int,
    payload: DeclineRequest,
    user: User = Depends(require_role(Role.DRIVER)),
    db: Session = Depends(get_db),
) -> DriverDispatchRequestOut:
    """Decline a pickup request — the offer goes back to the agent to find another driver."""
    driver = get_driver_for_user(db, user)
    try:
        request = get_dispatch_request_for_driver(db, driver, request_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Dispatch request not found.") from error
    decline_dispatch_request(db, request, payload.reason)
    return DriverDispatchRequestOut.from_request(request)


@router.get("/trips", response_model=list[DriverTripOut])
def list_active_trips_route(
    user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> list[DriverTripOut]:
    """List this driver's trips that are assigned but not yet delivered."""
    driver = get_driver_for_user(db, user)
    return [DriverTripOut.from_delivery(d) for d in get_active_trips_for_driver(db, driver)]


@router.post("/trips/{delivery_id}/picked-up", response_model=DriverTripOut)
def mark_picked_up_route(
    delivery_id: int, user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> DriverTripOut:
    """Mark that the driver has collected the food from the restaurant."""
    driver = get_driver_for_user(db, user)
    try:
        delivery = get_trip_for_driver(db, driver, delivery_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Trip not found.") from error
    mark_picked_up(db, delivery)
    return DriverTripOut.from_delivery(delivery)


@router.post("/trips/{delivery_id}/delivered", response_model=DriverTripOut)
def mark_delivered_route(
    delivery_id: int, user: User = Depends(require_role(Role.DRIVER)), db: Session = Depends(get_db)
) -> DriverTripOut:
    """Mark that the driver has dropped the food off at the pantry."""
    driver = get_driver_for_user(db, user)
    try:
        delivery = get_trip_for_driver(db, driver, delivery_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Trip not found.") from error
    mark_delivered(db, delivery)
    return DriverTripOut.from_delivery(delivery)
