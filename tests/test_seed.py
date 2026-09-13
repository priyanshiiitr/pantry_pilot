"""Tests for the database models and the demo seed script (Step 2)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantrypilot.auth.passwords import verify_password
from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DispatchRequest, DispatchStatus, Driver, Pantry, Restaurant, Role, User
from scripts import demo_world
from scripts.seed_demo import seed_demo_world


def count(session: Session, model: type) -> int:
    """Return how many rows a table has."""
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_the_whole_world(db_session: Session) -> None:
    """Every restaurant, pantry, driver, the admin and the delivery history get created."""
    seed_demo_world(db_session)

    assert count(db_session, Restaurant) == len(demo_world.RESTAURANTS)
    assert count(db_session, Pantry) == len(demo_world.PANTRIES)
    assert count(db_session, Driver) == len(demo_world.DRIVERS)
    expected_users = len(demo_world.RESTAURANTS) + len(demo_world.PANTRIES) + len(demo_world.DRIVERS) + 1
    assert count(db_session, User) == expected_users
    assert count(db_session, Delivery) == len(demo_world.PAST_DELIVERIES)


def test_profiles_are_linked_to_users_with_the_right_role(db_session: Session) -> None:
    """A pantry profile must belong to a pantry account, and so on."""
    seed_demo_world(db_session)

    for pantry in db_session.scalars(select(Pantry)):
        assert pantry.user.role == Role.PANTRY
    for driver in db_session.scalars(select(Driver)):
        assert driver.user.role == Role.DRIVER
    for restaurant in db_session.scalars(select(Restaurant)):
        assert restaurant.user.role == Role.RESTAURANT


def test_demo_password_works_for_seeded_accounts(db_session: Session) -> None:
    """You can log in to seeded accounts with the demo password."""
    seed_demo_world(db_session)

    admin = db_session.scalars(select(User).where(User.role == Role.ADMIN)).one()
    assert verify_password(demo_world.DEMO_PASSWORD, admin.password_hash)


def test_json_columns_round_trip(db_session: Session) -> None:
    """Lists and dicts stored in JSON columns come back unchanged."""
    seed_demo_world(db_session)

    riverside = db_session.scalars(select(Pantry).where(Pantry.name == "Riverside Food Bank")).one()
    assert riverside.dietary_restrictions == ["no_pork"]
    assert riverside.opening_hours["mon"] == ["08:00", "16:00"]
    assert "sat" not in riverside.opening_hours  # closed at weekends


def test_sam_has_a_history_of_declining_evening_runs(db_session: Session) -> None:
    """The seed includes the pattern the agent should notice later."""
    seed_demo_world(db_session)

    declined = db_session.scalars(
        select(DispatchRequest)
        .join(Driver)
        .where(Driver.name == "Sam Rivera", DispatchRequest.status == DispatchStatus.DECLINED)
    ).all()
    assert len(declined) == 3


def test_history_is_within_the_last_week_and_timezone_aware(db_session: Session) -> None:
    """Past deliveries are recent (so fairness numbers work) and times keep their UTC timezone."""
    seed_demo_world(db_session)
    db_session.expire_all()  # force a fresh read from the database file

    for delivery in db_session.scalars(select(Delivery)):
        assert delivery.delivered_at is not None
        assert delivery.delivered_at.tzinfo is not None
        assert utc_now() - delivery.delivered_at < timedelta(days=8)


def test_seed_refuses_to_run_twice(db_session: Session) -> None:
    """Seeding a database that already has data must not create duplicates."""
    seed_demo_world(db_session)

    with pytest.raises(RuntimeError):
        seed_demo_world(db_session)
