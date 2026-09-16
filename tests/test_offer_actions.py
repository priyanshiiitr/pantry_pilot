"""Tests for the deterministic offer-level functions (services/offers.py) and
notifications.

No AI involved — these are the functions an agent's action tools call once a
decision has already been made. Delivery-specific tests live in
test_deliveries.py, driver-dispatch tests in test_dispatch.py.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Notification, Offer, OfferStatus, Restaurant, Role, User
from pantrypilot.services.notifications import notify_user
from pantrypilot.services.offers import (
    cancel_offer,
    claim_offer_for_agent,
    flag_needs_human,
    requeue_offer_for_retry,
    set_agent_summary,
)


def make_offer(db_session: Session) -> Offer:
    """Create a minimal posted offer with its restaurant."""
    user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
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


def test_requeue_offer_for_retry_puts_it_back_to_posted(db_session: Session) -> None:
    """Requeuing clears the claim and saves a note explaining why it's back."""
    offer = make_offer(db_session)
    claim_offer_for_agent(db_session, offer)

    requeue_offer_for_retry(db_session, offer, "Driver Sam declined the pickup: car trouble.")

    assert offer.status == OfferStatus.POSTED
    assert offer.claimed_at is None
    assert "Sam declined" in offer.agent_summary


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
