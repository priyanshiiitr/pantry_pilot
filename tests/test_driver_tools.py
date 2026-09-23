"""Tests for agents/tools/driver_tools.py: get_available_drivers, get_driver_history.

These call the @tool-decorated functions directly (they remain plain
callables), bypassing any LLM.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from pantrypilot.agents.tools.driver_tools import get_available_drivers, get_driver_history
from pantrypilot.models import (
    Delivery,
    DeliveryStatus,
    Driver,
    DispatchRequest,
    DispatchStatus,
    Offer,
    Pantry,
    PantryResponse,
    Restaurant,
    Role,
    User,
)

SEATTLE_LAT, SEATTLE_LON = 47.6062, -122.3321
MONDAY_NOON_UTC = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)  # a Monday (see test_geo.py)


def make_driver(db_session: Session, email: str, **overrides) -> Driver:
    """Create a minimal driver, defaulting to right at SEATTLE_LAT/LON, on duty, always available."""
    user = User(email=email, role=Role.DRIVER, display_name="D", password_hash="x")
    fields = {
        "name": "D", "lat": SEATTLE_LAT, "lon": SEATTLE_LON, "on_duty": True,
        "availability": {"mon": ["00:00", "23:59"]}, **overrides,
    }
    driver = Driver(user=user, **fields)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def test_get_available_drivers_excludes_off_duty(db_session: Session) -> None:
    """An off-duty driver never shows up, regardless of location or schedule."""
    make_driver(db_session, "off@test.local", on_duty=False)

    results = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())

    assert results == []


def test_get_available_drivers_excludes_too_far(db_session: Session) -> None:
    """A driver whose service radius doesn't reach the pickup location is excluded."""
    make_driver(db_session, "far@test.local", lat=SEATTLE_LAT + 5.0, lon=SEATTLE_LON, service_radius_km=10)

    results = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())

    assert results == []


def test_get_available_drivers_excludes_unavailable_at_needed_time(db_session: Session) -> None:
    """A driver not scheduled to be available at the needed time is excluded."""
    make_driver(db_session, "busy@test.local", availability={"tue": ["00:00", "23:59"]})  # not Monday

    results = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())

    assert results == []


def test_get_available_drivers_includes_a_real_match(db_session: Session) -> None:
    """A driver who is on duty, in range, and available at the right time shows up."""
    make_driver(db_session, "ok@test.local")

    results = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())

    assert len(results) == 1
    assert results[0]["name"] == "D"


@pytest.mark.usefixtures("db_session")
def test_get_driver_history_with_no_requests_is_all_zero() -> None:
    """A driver nobody has ever asked has an empty, not broken, history."""
    result = get_driver_history(driver_id=1)

    assert result == {"driver_id": 1, "total_requests": 0, "accepted": 0, "declined": 0, "decline_reasons": []}


def test_get_driver_history_counts_accepted_and_declined(db_session: Session) -> None:
    """Accepted and declined requests are counted separately, with decline reasons collected."""
    driver = make_driver(db_session, "d@test.local")
    pantry_user = User(email="p@test.local", role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=pantry_user, name="P", address="x", lat=47.6, lon=-122.3)
    restaurant_user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=restaurant_user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant, title="T", description="D", quantity_text="Q",
        pickup_deadline=MONDAY_NOON_UTC,
    )
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED, pantry_response=PantryResponse.PENDING)
    db_session.add_all([pantry_user, pantry, restaurant_user, restaurant, offer, delivery])
    db_session.commit()

    db_session.add_all(
        [
            DispatchRequest(delivery=delivery, driver=driver, status=DispatchStatus.ACCEPTED),
            DispatchRequest(
                delivery=delivery, driver=driver, status=DispatchStatus.DECLINED, decline_reason="Car trouble."
            ),
        ]
    )
    db_session.commit()

    result = get_driver_history(driver_id=driver.id)

    assert result["total_requests"] == 2
    assert result["accepted"] == 1
    assert result["declined"] == 1
    assert result["decline_reasons"] == ["Car trouble."]


def test_available_drivers_include_travel_time_not_just_distance(db_session: Session) -> None:
    """The agent plans in minutes, so the tool reports minutes.

    Watching a real run, the Dispatch agent needed driver-to-pickup time, found
    only distance_km, and derived "minutes = distance_km * 2" from a guessed
    30km/h — close to, but not the same as, the 25km/h plus loading buffer the
    rest of the system uses. Returning the real number keeps every leg of its
    plan on one set of figures.
    """
    make_driver(db_session, "d@test.local", lat=SEATTLE_LAT + 0.05, lon=SEATTLE_LON)

    results = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())

    assert results[0]["minutes_to_pickup"] > 0
    assert isinstance(results[0]["minutes_to_pickup"], int)


def test_travel_time_matches_the_shared_estimator(db_session: Session) -> None:
    """The number must agree with estimate_travel_time, or the agent's legs won't add up."""
    from pantrypilot.services.geo import estimate_travel_minutes

    make_driver(db_session, "d@test.local", lat=SEATTLE_LAT + 0.05, lon=SEATTLE_LON)

    driver = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())[0]

    assert driver["minutes_to_pickup"] == round(estimate_travel_minutes(driver["distance_km"]))


def test_available_drivers_include_coordinates_for_the_onward_leg(db_session: Session) -> None:
    """With lat/lon the agent can call estimate_travel_time for driver -> pantry itself.

    Without them it could only ever approximate that second leg.
    """
    make_driver(db_session, "d@test.local")

    driver = get_available_drivers(lat=SEATTLE_LAT, lon=SEATTLE_LON, needed_by=MONDAY_NOON_UTC.isoformat())[0]

    assert driver["lat"] == SEATTLE_LAT
    assert driver["lon"] == SEATTLE_LON
