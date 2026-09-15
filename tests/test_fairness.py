"""Tests for pantrypilot/services/fairness.py (Step 6) — no AI, just arithmetic on the database."""

from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DeliveryStatus, Offer, Pantry, PantryResponse, Restaurant, Role, User
from pantrypilot.services.fairness import fairness_snapshot


def make_pantry(db_session: Session, name: str) -> Pantry:
    """Create a minimal pantry (with its user) for a test."""
    user = User(email=f"{name}@test.local", role=Role.PANTRY, display_name=name, password_hash="x")
    pantry = Pantry(user=user, name=name, address="somewhere", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_delivery(db_session: Session, pantry: Pantry, kg: float, status: str = DeliveryStatus.DELIVERED) -> Delivery:
    """Create a minimal offer + delivery of `kg` kilograms to `pantry`."""
    restaurant_user = User(
        email=f"r{pantry.id}-{kg}@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x"
    )
    restaurant = Restaurant(user=restaurant_user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now(),
    )
    delivery = Delivery(offer=offer, pantry=pantry, status=status, pantry_response=PantryResponse.ACCEPTED, kg=kg)
    db_session.add_all([restaurant_user, restaurant, offer, delivery])
    db_session.commit()
    return delivery


def test_fairness_snapshot_with_no_history(db_session: Session) -> None:
    """A pantry with no deliveries yet has 0 kg received and is not above average."""
    pantry = make_pantry(db_session, "Empty Pantry")

    snapshot = fairness_snapshot(db_session, pantry.id, extra_kg=10)

    assert snapshot["kg_received_last_7_days"] == 0.0
    assert snapshot["currently_above_average"] is False


def test_fairness_snapshot_flags_a_pantry_that_already_got_a_lot(db_session: Session) -> None:
    """A pantry that already received much more than others shows as above average."""
    busy_pantry = make_pantry(db_session, "Busy Pantry")
    quiet_pantry = make_pantry(db_session, "Quiet Pantry")
    make_delivery(db_session, busy_pantry, kg=100)
    make_delivery(db_session, quiet_pantry, kg=10)

    busy_snapshot = fairness_snapshot(db_session, busy_pantry.id, extra_kg=0)

    assert busy_snapshot["kg_received_last_7_days"] == 100.0
    assert busy_snapshot["average_kg_received_last_7_days_across_all_pantries"] == 55.0
    assert busy_snapshot["currently_above_average"] is True


def test_fairness_snapshot_projects_the_new_total(db_session: Session) -> None:
    """extra_kg is added to the current total to project what would happen next."""
    pantry = make_pantry(db_session, "Some Pantry")
    make_delivery(db_session, pantry, kg=20)

    snapshot = fairness_snapshot(db_session, pantry.id, extra_kg=15)

    assert snapshot["kg_if_this_delivery_is_added"] == 35.0


def test_fairness_snapshot_ignores_cancelled_deliveries(db_session: Session) -> None:
    """A cancelled delivery shouldn't count toward what a pantry "received"."""
    pantry = make_pantry(db_session, "Pantry With Cancellation")
    make_delivery(db_session, pantry, kg=50, status=DeliveryStatus.CANCELLED)

    snapshot = fairness_snapshot(db_session, pantry.id, extra_kg=0)

    assert snapshot["kg_received_last_7_days"] == 0.0
