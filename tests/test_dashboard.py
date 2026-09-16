"""Tests for services/dashboard.py (Step 12): the admin overview stats and
the users list/detail view.

No AI involved — pure aggregation queries.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Decision,
    DecisionKind,
    DecisionStatus,
    Delivery,
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
from pantrypilot.services.dashboard import (
    get_dashboard_stats,
    get_recent_activity_for_user,
    get_user_or_raise,
    get_user_status_label,
    list_all_users,
)


def make_restaurant(db_session: Session, email: str = "r@test.local") -> Restaurant:
    """Create a minimal restaurant with its user account."""
    user = User(email=email, role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, restaurant])
    db_session.commit()
    return restaurant


def make_pantry(db_session: Session, email: str = "p@test.local", accepting: bool = True) -> Pantry:
    """Create a minimal pantry with its user account."""
    user = User(email=email, role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=user, name="P", address="x", lat=47.6, lon=-122.3, accepting_donations=accepting)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_driver(db_session: Session, email: str = "d@test.local", on_duty: bool = True) -> Driver:
    """Create a minimal driver with its user account."""
    user = User(email=email, role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=user, name="D", lat=47.6, lon=-122.3, on_duty=on_duty)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def make_offer(db_session: Session, restaurant: Restaurant, status: str = OfferStatus.POSTED) -> Offer:
    """Create a minimal offer for `restaurant`."""
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2),
        status=status,
    )
    db_session.add(offer)
    db_session.commit()
    return offer


def test_dashboard_stats_counts_active_offers(db_session: Session) -> None:
    """Active statuses count; delivered/cancelled don't."""
    restaurant = make_restaurant(db_session)
    make_offer(db_session, restaurant, status=OfferStatus.AGENT_WORKING)
    make_offer(db_session, restaurant, status=OfferStatus.DRIVER_REQUESTED)
    make_offer(db_session, restaurant, status=OfferStatus.DELIVERED)
    make_offer(db_session, restaurant, status=OfferStatus.CANCELLED)

    stats = get_dashboard_stats(db_session)

    assert stats["active_offers"] == 2


def test_dashboard_stats_counts_pending_decisions(db_session: Session) -> None:
    """Only pending decisions count toward the stat card."""
    restaurant = make_restaurant(db_session)
    offer = make_offer(db_session, restaurant)
    db_session.add(
        Decision(
            offer=offer, kind=DecisionKind.AGENT_ESCALATION, interrupt_id="i1", interrupt_name="n1", card={},
            status=DecisionStatus.PENDING,
        )
    )
    db_session.add(
        Decision(
            offer=offer, kind=DecisionKind.AGENT_ESCALATION, interrupt_id="i2", interrupt_name="n2", card={},
            status=DecisionStatus.RESUMED,
        )
    )
    db_session.commit()

    stats = get_dashboard_stats(db_session)

    assert stats["pending_decisions"] == 1


def test_dashboard_stats_sums_kg_and_meals_delivered_today(db_session: Session) -> None:
    """Today's delivered kg/meals are summed; older or undelivered ones are excluded."""
    restaurant = make_restaurant(db_session)
    pantry = make_pantry(db_session)
    offer1 = make_offer(db_session, restaurant, status=OfferStatus.DELIVERED)
    offer2 = make_offer(db_session, restaurant, status=OfferStatus.DELIVERED)
    offer3 = make_offer(db_session, restaurant, status=OfferStatus.POSTED)  # not delivered - excluded

    db_session.add_all(
        [
            Delivery(
                offer=offer1, pantry=pantry, status=DeliveryStatus.DELIVERED, pantry_response=PantryResponse.ACCEPTED,
                kg=10.0, meals=20, delivered_at=utc_now(),
            ),
            Delivery(
                offer=offer2, pantry=pantry, status=DeliveryStatus.DELIVERED, pantry_response=PantryResponse.ACCEPTED,
                kg=5.0, meals=15, delivered_at=utc_now() - timedelta(days=3),  # not today - excluded from "today"
            ),
            Delivery(
                offer=offer3, pantry=pantry, status=DeliveryStatus.PLANNED, pantry_response=PantryResponse.PENDING,
                kg=100.0, meals=200,
            ),
        ]
    )
    db_session.commit()

    stats = get_dashboard_stats(db_session)

    assert stats["kg_saved_today"] == 10.0
    assert stats["meals_saved_today"] == 20
    assert stats["kg_saved_total"] == 15.0  # both delivered ones, regardless of day
    assert stats["meals_saved_total"] == 35
    assert stats["completed_today"] == 1


def test_dashboard_stats_with_no_data_are_all_zero(db_session: Session) -> None:
    """An empty database reports zeros, not an error."""
    stats = get_dashboard_stats(db_session)

    assert stats == {
        "active_offers": 0,
        "pending_decisions": 0,
        "completed_today": 0,
        "kg_saved_today": 0.0,
        "meals_saved_today": 0,
        "kg_saved_total": 0.0,
        "meals_saved_total": 0,
    }


def test_list_all_users_includes_every_role(db_session: Session) -> None:
    """Restaurants, pantries and drivers all show up."""
    make_restaurant(db_session)
    make_pantry(db_session)
    make_driver(db_session)

    users = list_all_users(db_session)

    assert {user.role for user in users} == {Role.RESTAURANT, Role.PANTRY, Role.DRIVER}


def test_get_user_status_label_for_driver_and_pantry(db_session: Session) -> None:
    """Status labels reflect on_duty / accepting_donations; restaurants have no label."""
    restaurant = make_restaurant(db_session)
    on_duty_driver = make_driver(db_session, "d1@test.local", on_duty=True)
    off_duty_driver = make_driver(db_session, "d2@test.local", on_duty=False)
    open_pantry = make_pantry(db_session, "p1@test.local", accepting=True)
    paused_pantry = make_pantry(db_session, "p2@test.local", accepting=False)

    assert get_user_status_label(restaurant.user) == ""
    assert get_user_status_label(on_duty_driver.user) == "On duty"
    assert get_user_status_label(off_duty_driver.user) == "Off duty"
    assert get_user_status_label(open_pantry.user) == "Accepting donations"
    assert get_user_status_label(paused_pantry.user) == "Paused"


def test_get_user_or_raise_for_missing_id(db_session: Session) -> None:
    """A bad user id raises LookupError, not a crash."""
    with pytest.raises(LookupError):
        get_user_or_raise(db_session, 999999)


def test_recent_activity_for_restaurant_shows_its_offers(db_session: Session) -> None:
    """A restaurant's recent activity is its own recent offers."""
    restaurant = make_restaurant(db_session)
    make_offer(db_session, restaurant, status=OfferStatus.DELIVERED)

    activity = get_recent_activity_for_user(db_session, restaurant.user)

    assert len(activity) == 1
    assert activity[0]["status"] == OfferStatus.DELIVERED


def test_recent_activity_for_admin_is_empty(db_session: Session) -> None:
    """Admins have no role-specific activity to show."""
    admin = User(email="admin@test.local", role=Role.ADMIN, display_name="Admin", password_hash="x")
    db_session.add(admin)
    db_session.commit()

    assert get_recent_activity_for_user(db_session, admin) == []
