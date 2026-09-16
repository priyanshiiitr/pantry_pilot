"""Tests for services/deliveries.py (Step 8-10): assigning a pantry, the
pantry accepting/declining, and driver pickup/delivered updates.

No AI involved — these are the functions called once a decision has already
been made (by an agent, or a person clicking Accept/Decline).
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    DeliveryStatus,
    Driver,
    Offer,
    OfferStatus,
    Pantry,
    PantryResponse,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.deliveries import (
    accept_delivery,
    assign_delivery,
    decline_delivery,
    get_active_trips_for_driver,
    get_latest_delivery,
    get_pending_deliveries_for_pantry,
    get_trip_for_driver,
    mark_delivered,
    mark_picked_up,
)


def make_offer(db_session: Session, email: str = "r@test.local") -> Offer:
    """Create a minimal posted offer with its restaurant."""
    user = User(email=email, role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2),
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


def make_pantry(db_session: Session, email: str = "p@test.local") -> Pantry:
    """Create a minimal pantry. Pass a distinct `email` when creating more than one."""
    user = User(email=email, role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=user, name="P", address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_driver(db_session: Session, email: str = "d@test.local") -> Driver:
    """Create a minimal driver."""
    user = User(email=email, role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=user, name="D", lat=47.6, lon=-122.3)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def test_assign_delivery_creates_a_planned_delivery(db_session: Session) -> None:
    """Assigning a pantry creates a Delivery in PLANNED status, without touching offer.status."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)

    delivery = assign_delivery(db_session, offer, pantry, "Closest pantry with fridge capacity.")

    assert delivery.status == DeliveryStatus.PLANNED
    assert delivery.pantry_id == pantry.id
    assert delivery.pantry_response == PantryResponse.PENDING
    assert offer.status == OfferStatus.POSTED  # unchanged until a driver is asked


def test_get_latest_delivery_returns_the_newest_one(db_session: Session) -> None:
    """When an offer has been re-planned, get_latest_delivery returns the most recent attempt."""
    offer = make_offer(db_session)
    pantry_a = make_pantry(db_session, email="pa@test.local")
    pantry_b = make_pantry(db_session, email="pb@test.local")
    assign_delivery(db_session, offer, pantry_a, "first attempt")
    second = assign_delivery(db_session, offer, pantry_b, "re-planned")

    latest = get_latest_delivery(db_session, offer.id)

    assert latest.id == second.id


def test_pantry_sees_only_its_own_pending_deliveries(db_session: Session) -> None:
    """get_pending_deliveries_for_pantry only returns this pantry's undecided deliveries."""
    offer1 = make_offer(db_session, email="r1@test.local")
    offer2 = make_offer(db_session, email="r2@test.local")
    pantry = make_pantry(db_session)
    other_pantry = make_pantry(db_session, email="other@test.local")
    mine = assign_delivery(db_session, offer1, pantry, "reason")
    assign_delivery(db_session, offer2, other_pantry, "reason")

    pending = get_pending_deliveries_for_pantry(db_session, pantry)

    assert [d.id for d in pending] == [mine.id]


def test_accept_delivery_sets_pantry_response(db_session: Session) -> None:
    """Accepting marks the delivery as accepted, without changing its status."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")

    accept_delivery(db_session, delivery)

    assert delivery.pantry_response == PantryResponse.ACCEPTED


def test_decline_delivery_cancels_delivery_and_requeues_offer(db_session: Session) -> None:
    """Declining cancels this delivery attempt and puts the offer back in the queue."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")

    decline_delivery(db_session, delivery, "We're at capacity this week.")

    assert delivery.pantry_response == PantryResponse.DECLINED
    assert delivery.pantry_decline_reason == "We're at capacity this week."
    assert delivery.status == DeliveryStatus.CANCELLED
    assert offer.status == OfferStatus.POSTED
    assert "declined" in offer.agent_summary.lower()


def test_driver_sees_only_active_trips(db_session: Session) -> None:
    """get_active_trips_for_driver excludes deliveries not yet assigned or already delivered."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    driver = make_driver(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")
    delivery.driver_id = driver.id
    delivery.status = DeliveryStatus.DRIVER_ASSIGNED
    db_session.commit()

    trips = get_active_trips_for_driver(db_session, driver)

    assert [t.id for t in trips] == [delivery.id]


def test_get_trip_for_driver_rejects_someone_elses_delivery(db_session: Session) -> None:
    """A driver can't fetch a trip that isn't assigned to them."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    driver = make_driver(db_session)
    other_driver = make_driver(db_session, email="other@test.local")
    delivery = assign_delivery(db_session, offer, pantry, "reason")
    delivery.driver_id = driver.id
    db_session.commit()

    with pytest.raises(LookupError):
        get_trip_for_driver(db_session, other_driver, delivery.id)


def test_mark_picked_up_sets_status_and_timestamp(db_session: Session) -> None:
    """Marking picked-up updates both the delivery and the offer."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")

    mark_picked_up(db_session, delivery)

    assert delivery.status == DeliveryStatus.PICKED_UP
    assert delivery.picked_up_at is not None
    assert offer.status == OfferStatus.PICKED_UP


def test_mark_delivered_sets_status_and_timestamp(db_session: Session) -> None:
    """Marking delivered updates both the delivery and the offer."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")

    mark_delivered(db_session, delivery)

    assert delivery.status == DeliveryStatus.DELIVERED
    assert delivery.delivered_at is not None
    assert offer.status == OfferStatus.DELIVERED
