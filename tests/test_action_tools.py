"""Tests for the Coordinator's action-tool closures (agents/tools/action_tools.py).

These call the @tool-decorated functions directly (they remain plain callables),
bypassing any LLM — this tests the wiring between the tool and the services
layer, not the AI's decision-making.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from pantrypilot.agents.tools.action_tools import build_action_tools, notify_user
from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, Driver, Notification, Offer, OfferStatus, Pantry, Restaurant, Role, User


def make_offer_with_pantry_and_driver(db_session: Session) -> tuple[Offer, Pantry, Driver]:
    """Set up one offer, one pantry and one driver with their user accounts."""
    r_user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=r_user, name="R", address="x", lat=47.6, lon=-122.3)
    p_user = User(email="p@test.local", role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=p_user, name="P", address="x", lat=47.6, lon=-122.3)
    d_user = User(email="d@test.local", role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=d_user, name="D", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2),
    )
    db_session.add_all([r_user, restaurant, p_user, pantry, d_user, driver, offer])
    db_session.commit()
    return offer, pantry, driver


def get_tools(offer_id: int) -> dict:
    """Build the action tools for one offer and return them keyed by name for readability."""
    tools = build_action_tools(offer_id)
    return {tool.tool_name: tool for tool in tools}


def test_assign_delivery_tool_creates_delivery_and_notifies_pantry(db_session: Session) -> None:
    """Calling assign_delivery saves a delivery and notifies the pantry's user."""
    offer, pantry, _driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)

    result = tools["assign_delivery"](pantry_id=pantry.id, reason="Nearest pantry with capacity.")

    assert result["status"] == "planned"
    delivery = db_session.get(Delivery, result["delivery_id"])
    assert delivery.pantry_id == pantry.id
    notification = db_session.query(Notification).filter_by(user_id=pantry.user_id).one()
    assert "Nearest pantry" in notification.message


def test_assign_delivery_tool_reports_missing_pantry(db_session: Session) -> None:
    """A bad pantry_id returns a clear error dict instead of crashing."""
    offer, _pantry, _driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)

    result = tools["assign_delivery"](pantry_id=999999, reason="x")

    assert "error" in result


def test_send_dispatch_request_tool_requires_a_delivery_first(db_session: Session) -> None:
    """Calling send_dispatch_request before assign_delivery gives a clear error, not a crash."""
    offer, _pantry, driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)

    result = tools["send_dispatch_request"](driver_id=driver.id, reason="x")

    assert "error" in result
    assert "assign_delivery" in result["error"]


def test_send_dispatch_request_tool_after_assign_succeeds(db_session: Session) -> None:
    """The normal flow: assign, then dispatch, works end to end and notifies the driver."""
    offer, pantry, driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)
    tools["assign_delivery"](pantry_id=pantry.id, reason="reason A")

    result = tools["send_dispatch_request"](driver_id=driver.id, reason="Closest available driver.")

    assert result["status"] == "requested"
    notification = db_session.query(Notification).filter_by(user_id=driver.user_id).one()
    assert "Closest available driver" in notification.message


def test_flag_needs_human_tool_updates_offer(db_session: Session) -> None:
    """flag_needs_human moves the offer to needs_human."""
    offer, _pantry, _driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)

    result = tools["flag_needs_human"](reason="No pantry can accept in time.")

    assert result["status"] == "needs_human"
    db_session.refresh(offer)
    assert offer.status == OfferStatus.NEEDS_HUMAN


def test_cancel_offer_tool_updates_offer(db_session: Session) -> None:
    """cancel_offer moves the offer to cancelled."""
    offer, _pantry, _driver = make_offer_with_pantry_and_driver(db_session)
    tools = get_tools(offer.id)

    result = tools["cancel_offer"](reason="Already spoiled.")

    assert result["status"] == "cancelled"
    db_session.refresh(offer)
    assert offer.status == OfferStatus.CANCELLED


def test_notify_user_tool_creates_notification(db_session: Session) -> None:
    """The standalone notify_user tool saves a notification for the given user."""
    user = User(email="u@test.local", role=Role.PANTRY, display_name="U", password_hash="x")
    db_session.add(user)
    db_session.commit()

    result = notify_user(user_id=user.id, message="Heads up.")

    assert result["status"] == "sent"
    assert db_session.query(Notification).filter_by(user_id=user.id).count() == 1
