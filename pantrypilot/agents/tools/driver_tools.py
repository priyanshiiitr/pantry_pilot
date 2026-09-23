"""Tools for finding and evaluating volunteer drivers."""

from datetime import datetime

from sqlalchemy import select
from strands import tool

from pantrypilot import database
from pantrypilot.config import settings
from pantrypilot.models import Driver, DispatchRequest, DispatchStatus
from pantrypilot.services.geo import estimate_travel_minutes, haversine_km, is_open_now


@tool
def get_available_drivers(lat: float, lon: float, needed_by: str) -> list[dict]:
    """Find on-duty drivers who could pick up from `lat`/`lon` and would be available
    by `needed_by`, nearest first. A driver too far away (outside their own service
    radius) or not scheduled to be available at that time is left out entirely.

    Each driver includes `minutes_to_pickup` (how long they need to reach the pickup
    point) and their `lat`/`lon`, so you can work out the onward leg to a pantry with
    estimate_travel_time rather than approximating from the distance.

    Args:
        lat: latitude of the pickup location (e.g. the restaurant's).
        lon: longitude of the pickup location.
        needed_by: ISO 8601 timestamp of when the pickup needs to happen.
    """
    needed_time = datetime.fromisoformat(needed_by)

    with database.SessionLocal() as session:
        drivers = list(session.scalars(select(Driver).where(Driver.on_duty.is_(True))))

    available = []
    for driver in drivers:
        distance_km = haversine_km(lat, lon, driver.lat, driver.lon)
        # Driver.availability has the exact same weekly-hours shape as a pantry's
        # opening_hours, so the same is_open_now() check works for both.
        is_available = is_open_now(driver.availability, needed_time, settings.city_timezone)
        if distance_km <= driver.service_radius_km and is_available:
            available.append(
                {
                    "driver_id": driver.id,
                    "name": driver.name,
                    "distance_km": round(distance_km, 1),
                    # Watching a real run, the agent wanted this, found only
                    # distance, and derived "minutes = distance_km * 2" from a
                    # guessed 30km/h. Giving it the same number estimate_travel_time
                    # would give keeps every leg of its plan on one set of numbers.
                    "minutes_to_pickup": round(estimate_travel_minutes(distance_km)),
                    "lat": driver.lat,
                    "lon": driver.lon,
                    "vehicle": driver.vehicle,
                    "max_kg": driver.max_kg,
                    "has_cooler": driver.has_cooler,
                }
            )

    available.sort(key=lambda entry: entry["distance_km"])
    return available


@tool
def get_driver_history(driver_id: int) -> dict:
    """See a driver's track record: how many requests they've accepted vs declined,
    and their stated reasons for declining — useful for spotting patterns like
    "this driver always declines evening runs".

    Args:
        driver_id: the id of the driver to check.
    """
    with database.SessionLocal() as session:
        requests = list(session.scalars(select(DispatchRequest).where(DispatchRequest.driver_id == driver_id)))

    declined = [request for request in requests if request.status == DispatchStatus.DECLINED]
    accepted_count = sum(1 for request in requests if request.status == DispatchStatus.ACCEPTED)

    return {
        "driver_id": driver_id,
        "total_requests": len(requests),
        "accepted": accepted_count,
        "declined": len(declined),
        "decline_reasons": [request.decline_reason for request in declined if request.decline_reason],
    }
