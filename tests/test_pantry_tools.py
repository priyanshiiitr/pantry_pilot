"""Tests for agents/tools/pantry_tools.py: find_nearby_pantries,
get_pantry_profile, check_pantry_capacity, calculate_fairness_score.

These call the @tool-decorated functions directly (they remain plain
callables), bypassing any LLM.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.agents.tools.pantry_tools import (
    calculate_fairness_score,
    check_pantry_capacity,
    find_nearby_pantries,
    get_pantry_profile,
)
from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DeliveryStatus, Offer, Pantry, PantryResponse, Restaurant, Role, User

# Roughly downtown Seattle, used as the "restaurant location" for distance checks.
SEATTLE_LAT, SEATTLE_LON = 47.6062, -122.3321


def make_pantry(db_session: Session, email: str, **overrides) -> Pantry:
    """Create a minimal pantry, defaulting to right at SEATTLE_LAT/LON."""
    user = User(email=email, role=Role.PANTRY, display_name="P", password_hash="x")
    fields = {"name": "P", "address": "x", "lat": SEATTLE_LAT, "lon": SEATTLE_LON, **overrides}
    pantry = Pantry(user=user, **fields)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def test_find_nearby_pantries_excludes_ones_too_far(db_session: Session) -> None:
    """A pantry well outside the radius doesn't show up."""
    make_pantry(db_session, "near@test.local", lat=SEATTLE_LAT + 0.01, lon=SEATTLE_LON)  # ~1 km away
    make_pantry(db_session, "far@test.local", lat=SEATTLE_LAT + 5.0, lon=SEATTLE_LON)  # ~550 km away

    results = find_nearby_pantries(lat=SEATTLE_LAT, lon=SEATTLE_LON, radius_km=15)

    assert len(results) == 1
    assert results[0]["name"] == "P"


def test_find_nearby_pantries_excludes_ones_not_accepting_donations(db_session: Session) -> None:
    """A pantry that paused donations doesn't show up as a candidate."""
    make_pantry(db_session, "closed@test.local", accepting_donations=False)

    results = find_nearby_pantries(lat=SEATTLE_LAT, lon=SEATTLE_LON, radius_km=15)

    assert results == []


def test_find_nearby_pantries_sorts_nearest_first(db_session: Session) -> None:
    """Results are ordered by distance, closest first."""
    make_pantry(db_session, "far@test.local", lat=SEATTLE_LAT + 0.05, lon=SEATTLE_LON)
    make_pantry(db_session, "near@test.local", lat=SEATTLE_LAT + 0.005, lon=SEATTLE_LON)

    results = find_nearby_pantries(lat=SEATTLE_LAT, lon=SEATTLE_LON, radius_km=15)

    assert [r["distance_km"] for r in results] == sorted(r["distance_km"] for r in results)


def test_get_pantry_profile_includes_location_and_hours(db_session: Session) -> None:
    """The profile has everything Matching/Dispatch need: location, storage, hours, restrictions."""
    pantry = make_pantry(
        db_session, "p@test.local", has_fridge=True, dietary_restrictions=["no_pork"],
        opening_hours={"mon": ["09:00", "17:00"]},
    )

    result = get_pantry_profile(pantry_id=pantry.id)

    assert result["lat"] == SEATTLE_LAT
    assert result["lon"] == SEATTLE_LON
    assert result["has_fridge"] is True
    assert result["dietary_restrictions"] == ["no_pork"]
    assert "is_open_right_now" in result  # computed, not just the raw schedule


@pytest.mark.usefixtures("db_session")  # activates the temp-database swap; no data is needed for this check
def test_get_pantry_profile_reports_a_clear_error_for_a_missing_id() -> None:
    """A bad pantry_id returns an error dict, not a crash."""
    result = get_pantry_profile(pantry_id=999999)

    assert "error" in result


def test_check_pantry_capacity_subtracts_recent_commitments(db_session: Session) -> None:
    """Capacity remaining accounts for deliveries already committed in the last 24h."""
    pantry = make_pantry(db_session, "p@test.local", capacity_kg_per_day=100.0)
    restaurant_user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=restaurant_user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant, title="T", description="D", quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=1),
    )
    delivery = Delivery(
        offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED, pantry_response=PantryResponse.PENDING, kg=30.0,
    )
    db_session.add_all([restaurant_user, restaurant, offer, delivery])
    db_session.commit()

    result = check_pantry_capacity(pantry_id=pantry.id)

    assert result["committed_last_24h_kg"] == 30.0
    assert result["remaining_kg_today"] == 70.0


def test_calculate_fairness_score_reflects_recent_history(db_session: Session) -> None:
    """The tool returns real numbers from the fairness service, not a stub."""
    pantry = make_pantry(db_session, "p@test.local")

    result = calculate_fairness_score(pantry_id=pantry.id, extra_kg=10)

    assert result["pantry_id"] == pantry.id
    assert result["kg_received_last_7_days"] == 0.0
    assert result["kg_if_this_delivery_is_added"] == 10.0
