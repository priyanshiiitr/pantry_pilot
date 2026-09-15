"""Tests for the deterministic offer-action functions added in Step 8
(services/offers.py: claim/assign/dispatch/flag/cancel) and notifications.

No AI involved — these are the functions an agent's action tools call once a
decision has already been made.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    DeliveryStatus,
    Driver,
    Notification,
    Offer,
    OfferStatus,
    Pantry,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.notifications import notify_user
from pantrypilot.services.offers import (
    assign_delivery,
    cancel_offer,
    claim_offer_for_agent,
    flag_needs_human,
    get_latest_delivery,
    send_dispatch_request,
    set_agent_summary,
)


def make_offer(db_session: Session) -> Offer:
    """Create a minimal posted offer with its restaurant."""
    user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant, title="T", description="D", quantity_text="Q", pickup_deadline=utc_now() + timedelta(hours=2)
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


def make_driver(db_session: Session) -> Driver:
    """Create a minimal driver."""
    user = User(email="d@test.local", role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=user, name="D", lat=47.6, lon=-122.3)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def test_claim_offer_for_agent_sets_status_and_timestamp(db_session: Session) -> None:
    """Claiming marks the offer as being worked on right now."""
    offer = make_offer(db_session)

    claim_offer_for_agent(db_session, offer)

    assert offer.status == OfferStatus.AGENT_WORKING
    assert offer.claimed_at is not None


def test_set_agent_summary_saves_the_text(db_session: Session) -> None:
    """The agent's plain-English update gets saved on the offer."""
    offer = make_offer(db_session)

    set_agent_summary(db_session, offer, "Matched with Hope Community Pantry.")

    assert offer.agent_summary == "Matched with Hope Community Pantry."


def test_assign_delivery_creates_a_planned_delivery(db_session: Session) -> None:
    """Assigning a pantry creates a Delivery in PLANNED status, without touching offer.status."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)

    delivery = assign_delivery(db_session, offer, pantry, "Closest pantry with fridge capacity.")

    assert delivery.status == DeliveryStatus.PLANNED
    assert delivery.pantry_id == pantry.id
    assert delivery.match_reasoning == "Closest pantry with fridge capacity."
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


def test_send_dispatch_request_moves_offer_and_delivery_to_driver_requested(db_session: Session) -> None:
    """Asking a driver moves both the delivery and the offer into driver_requested."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    driver = make_driver(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")

    request = send_dispatch_request(db_session, delivery, driver, "Nearest available driver.")

    assert request.driver_id == driver.id
    assert delivery.status == DeliveryStatus.DRIVER_REQUESTED
    assert offer.status == OfferStatus.DRIVER_REQUESTED
    assert delivery.dispatch_reasoning == "Nearest available driver."


def test_flag_needs_human_sets_status_and_summary(db_session: Session) -> None:
    """Flagging for review makes the situation visible via status + summary."""
    offer = make_offer(db_session)

    flag_needs_human(db_session, offer, "No pantry can accept before the deadline.")

    assert offer.status == OfferStatus.NEEDS_HUMAN
    assert "No pantry can accept" in offer.agent_summary


def test_cancel_offer_sets_status_and_summary(db_session: Session) -> None:
    """Cancelling sets status and records why."""
    offer = make_offer(db_session)

    cancel_offer(db_session, offer, "Food has already spoiled.")

    assert offer.status == OfferStatus.CANCELLED
    assert "spoiled" in offer.agent_summary


def test_notify_user_creates_a_notification(db_session: Session) -> None:
    """notify_user saves a row with the message and optional link."""
    user = User(email="u@test.local", role=Role.PANTRY, display_name="U", password_hash="x")
    db_session.add(user)
    db_session.commit()

    notification = notify_user(db_session, user.id, "New delivery incoming.", link="/pantry")

    assert notification.user_id == user.id
    assert notification.message == "New delivery incoming."
    assert notification.link == "/pantry"
    assert db_session.get(Notification, notification.id) is not None
