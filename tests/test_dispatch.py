"""Tests for services/dispatch.py (Step 8-10): asking a driver, and handling
accept, decline, or nobody responding in time.

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
    DispatchStatus,
    Offer,
    OfferStatus,
    Pantry,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.deliveries import assign_delivery
from pantrypilot.services.dispatch import (
    accept_dispatch_request,
    decline_dispatch_request,
    expire_dispatch_request,
    get_dispatch_request_for_driver,
    get_pending_dispatch_requests_for_driver,
    send_dispatch_request,
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


def make_pantry(db_session: Session) -> Pantry:
    """Create a minimal pantry."""
    user = User(email="p@test.local", role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=user, name="P", address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_driver(db_session: Session, email: str = "d@test.local") -> Driver:
    """Create a minimal driver. Pass a distinct `email` when creating more than one."""
    user = User(email=email, role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=user, name="D", lat=47.6, lon=-122.3)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def make_delivery(db_session: Session):
    """Create a minimal offer + pantry + assigned delivery, ready to dispatch."""
    offer = make_offer(db_session)
    pantry = make_pantry(db_session)
    delivery = assign_delivery(db_session, offer, pantry, "reason")
    return offer, delivery


def test_send_dispatch_request_moves_offer_and_delivery_to_driver_requested(db_session: Session) -> None:
    """Asking a driver moves both the delivery and the offer into driver_requested."""
    offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)

    request = send_dispatch_request(db_session, delivery, driver, "Nearest available driver.")

    assert request.driver_id == driver.id
    assert request.status == DispatchStatus.REQUESTED
    assert delivery.status == DeliveryStatus.DRIVER_REQUESTED
    assert offer.status == OfferStatus.DRIVER_REQUESTED
    assert delivery.dispatch_reasoning == "Nearest available driver."


def test_driver_sees_only_its_own_pending_requests(db_session: Session) -> None:
    """get_pending_dispatch_requests_for_driver only returns this driver's unanswered requests."""
    _offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)
    other_driver = make_driver(db_session, email="other@test.local")
    mine = send_dispatch_request(db_session, delivery, driver, "reason")

    pending = get_pending_dispatch_requests_for_driver(db_session, driver)
    other_pending = get_pending_dispatch_requests_for_driver(db_session, other_driver)

    assert [r.id for r in pending] == [mine.id]
    assert other_pending == []


def test_get_dispatch_request_for_driver_rejects_someone_elses_request(db_session: Session) -> None:
    """A driver can't fetch a request that wasn't sent to them."""
    _offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)
    other_driver = make_driver(db_session, email="other@test.local")
    request = send_dispatch_request(db_session, delivery, driver, "reason")

    with pytest.raises(LookupError):
        get_dispatch_request_for_driver(db_session, other_driver, request.id)


def test_accept_dispatch_request_assigns_the_driver(db_session: Session) -> None:
    """Accepting assigns the driver to the delivery and moves everything to driver_assigned."""
    offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)
    request = send_dispatch_request(db_session, delivery, driver, "reason")

    accept_dispatch_request(db_session, request)

    assert request.status == DispatchStatus.ACCEPTED
    assert request.responded_at is not None
    assert delivery.driver_id == driver.id
    assert delivery.status == DeliveryStatus.DRIVER_ASSIGNED
    assert offer.status == OfferStatus.DRIVER_ASSIGNED


def test_decline_dispatch_request_reverts_delivery_and_requeues_offer(db_session: Session) -> None:
    """Declining keeps the pantry choice (delivery goes back to PLANNED, not cancelled)
    and puts the offer back in the queue so the agent can find another driver."""
    offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)
    request = send_dispatch_request(db_session, delivery, driver, "reason")

    decline_dispatch_request(db_session, request, "Car trouble.")

    assert request.status == DispatchStatus.DECLINED
    assert request.decline_reason == "Car trouble."
    assert delivery.status == DeliveryStatus.PLANNED  # pantry still chosen
    assert delivery.pantry_id is not None
    assert offer.status == OfferStatus.POSTED
    assert "declined" in offer.agent_summary.lower()


def test_expire_dispatch_request_has_the_same_effect_as_a_decline(db_session: Session) -> None:
    """A driver who never responds is treated the same way as an explicit decline."""
    offer, delivery = make_delivery(db_session)
    driver = make_driver(db_session)
    request = send_dispatch_request(db_session, delivery, driver, "reason")

    expire_dispatch_request(db_session, request)

    assert request.status == DispatchStatus.EXPIRED
    assert delivery.status == DeliveryStatus.PLANNED
    assert offer.status == OfferStatus.POSTED
    assert "did not respond" in offer.agent_summary
