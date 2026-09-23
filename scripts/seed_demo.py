"""Fill the database with the demo world from scripts/demo_world.py.

Creates login accounts for every restaurant, pantry and driver plus one admin,
and a week of past deliveries (so fairness and driver-history numbers mean something).

Usage (from the project folder):
    python -m scripts.seed_demo            # only works on an empty database
    python -m scripts.seed_demo --reset    # wipe everything first, then seed
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantrypilot.agents.sessions import clear_agent_sessions
from pantrypilot.auth.passwords import hash_password
from pantrypilot.config import settings
from pantrypilot.database import SessionLocal, create_tables, drop_tables, utc_now
from pantrypilot.models import (
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    DispatchStatus,
    Driver,
    Offer,
    OfferStatus,
    Pantry,
    PantryResponse,
    Restaurant,
    Role,
    User,
)
from scripts import demo_world


@dataclass
class SeedSummary:
    """What the seed created, so we can print it (and check it in tests)."""

    restaurants: int = 0
    pantries: int = 0
    drivers: int = 0
    admins: int = 0
    past_deliveries: int = 0
    dispatch_requests: int = 0
    logins: list[tuple[str, str, str]] = field(default_factory=list)  # (role, name, email)


def database_has_users(session: Session) -> bool:
    """Return True if any user exists, which means the database was already seeded or used."""
    return (session.scalar(select(func.count()).select_from(User)) or 0) > 0


def local_time_days_ago(days_ago: int, hour: int) -> datetime:
    """Return `hour`:00 in the demo city's local time, `days_ago` days before today, as UTC."""
    city_zone = ZoneInfo(settings.city_timezone)
    today_in_city = utc_now().astimezone(city_zone).date()
    local_moment = datetime.combine(today_in_city - timedelta(days=days_ago), time(hour=hour), tzinfo=city_zone)
    return local_moment.astimezone(timezone.utc)


def create_user(session: Session, email: str, role: Role, display_name: str, password_hash: str) -> User:
    """Add one login account to the session (saved when the session commits)."""
    user = User(email=email, role=role, display_name=display_name, password_hash=password_hash)
    session.add(user)
    return user


def seed_admin(session: Session, password_hash: str, summary: SeedSummary) -> None:
    """Create the single admin/coordinator account."""
    create_user(session, demo_world.ADMIN["email"], Role.ADMIN, demo_world.ADMIN["display_name"], password_hash)
    summary.admins += 1
    summary.logins.append((Role.ADMIN, demo_world.ADMIN["display_name"], demo_world.ADMIN["email"]))


def seed_restaurants(session: Session, password_hash: str, summary: SeedSummary) -> dict[str, Restaurant]:
    """Create restaurant accounts + profiles. Returns them by name for linking offers later."""
    by_name: dict[str, Restaurant] = {}
    for data in demo_world.RESTAURANTS:
        user = create_user(session, data["email"], Role.RESTAURANT, data["name"], password_hash)
        profile_fields = {key: value for key, value in data.items() if key != "email"}
        restaurant = Restaurant(user=user, **profile_fields)
        session.add(restaurant)
        by_name[restaurant.name] = restaurant
        summary.logins.append((Role.RESTAURANT, restaurant.name, data["email"]))
    summary.restaurants = len(by_name)
    return by_name


def seed_pantries(session: Session, password_hash: str, summary: SeedSummary) -> dict[str, Pantry]:
    """Create pantry accounts + profiles. Returns them by name."""
    by_name: dict[str, Pantry] = {}
    for data in demo_world.PANTRIES:
        user = create_user(session, data["email"], Role.PANTRY, data["name"], password_hash)
        profile_fields = {key: value for key, value in data.items() if key != "email"}
        pantry = Pantry(user=user, **profile_fields)
        session.add(pantry)
        by_name[pantry.name] = pantry
        summary.logins.append((Role.PANTRY, pantry.name, data["email"]))
    summary.pantries = len(by_name)
    return by_name


def seed_drivers(session: Session, password_hash: str, summary: SeedSummary) -> dict[str, Driver]:
    """Create driver accounts + profiles. Returns them by name."""
    by_name: dict[str, Driver] = {}
    for data in demo_world.DRIVERS:
        user = create_user(session, data["email"], Role.DRIVER, data["name"], password_hash)
        profile_fields = {key: value for key, value in data.items() if key != "email"}
        driver = Driver(user=user, **profile_fields)
        session.add(driver)
        by_name[driver.name] = driver
        summary.logins.append((Role.DRIVER, driver.name, data["email"]))
    summary.drivers = len(by_name)
    return by_name


def seed_one_past_delivery(
    session: Session,
    item: dict[str, Any],
    restaurants: dict[str, Restaurant],
    pantries: dict[str, Pantry],
    drivers: dict[str, Driver],
) -> int:
    """Create one finished offer → delivery → dispatch history. Returns how many dispatch requests it made."""
    pickup_time = local_time_days_ago(item["days_ago"], item["hour"])
    pantry = pantries[item["pantry"]]
    driver = drivers[item["driver"]]

    offer = Offer(
        restaurant=restaurants[item["restaurant"]],
        title=item["title"],
        description=f"{item['title']}: {item['quantity']}",
        quantity_text=item["quantity"],
        allergen_notes=item["allergens"],
        pickup_deadline=pickup_time + timedelta(hours=2),
        status=OfferStatus.DELIVERED,
        agent_summary=f"Delivered to {pantry.name} by {driver.name}.",
        created_at=pickup_time - timedelta(hours=1),
    )
    delivery = Delivery(
        offer=offer,
        pantry=pantry,
        driver=driver,
        status=DeliveryStatus.DELIVERED,
        pantry_response=PantryResponse.ACCEPTED,
        kg=item["kg"],
        meals=item["meals"],
        match_reasoning="(Historical demo data, created by the seed script.)",
        dispatch_reasoning="(Historical demo data, created by the seed script.)",
        created_at=pickup_time - timedelta(minutes=50),
        picked_up_at=pickup_time,
        delivered_at=pickup_time + timedelta(minutes=30),
    )
    session.add_all([offer, delivery])
    requests_made = 0

    declined = item.get("declined_by")
    if declined:
        session.add(
            DispatchRequest(
                delivery=delivery,
                driver=drivers[declined["driver"]],
                status=DispatchStatus.DECLINED,
                decline_reason=declined["reason"],
                sent_at=pickup_time - timedelta(minutes=45),
                responded_at=pickup_time - timedelta(minutes=40),
            )
        )
        requests_made += 1

    session.add(
        DispatchRequest(
            delivery=delivery,
            driver=driver,
            status=DispatchStatus.ACCEPTED,
            sent_at=pickup_time - timedelta(minutes=35),
            responded_at=pickup_time - timedelta(minutes=30),
        )
    )
    return requests_made + 1


def seed_demo_world(session: Session) -> SeedSummary:
    """Create the whole demo world in `session` and commit it.

    Raises RuntimeError if the database already has users, so we never duplicate data.
    """
    if database_has_users(session):
        raise RuntimeError("The database already has data. Use --reset to wipe it first.")

    # Hashing is deliberately slow (that's what makes it secure), so we hash the shared
    # demo password once and reuse it. Real signups get their own salted hash.
    password_hash = hash_password(demo_world.DEMO_PASSWORD)
    summary = SeedSummary()

    seed_admin(session, password_hash, summary)
    restaurants = seed_restaurants(session, password_hash, summary)
    pantries = seed_pantries(session, password_hash, summary)
    drivers = seed_drivers(session, password_hash, summary)

    for item in demo_world.PAST_DELIVERIES:
        summary.dispatch_requests += seed_one_past_delivery(session, item, restaurants, pantries, drivers)
        summary.past_deliveries += 1

    session.commit()
    return summary


def print_summary(summary: SeedSummary) -> None:
    """Print what was created and the demo logins."""
    print(f"\nDemo world created for {settings.city_name}:")
    print(f"  {summary.restaurants} restaurants, {summary.pantries} pantries, {summary.drivers} drivers, "
          f"{summary.admins} admin")
    print(f"  {summary.past_deliveries} past deliveries, {summary.dispatch_requests} dispatch requests (history)")
    print(f"\nDemo logins (password for all: {demo_world.DEMO_PASSWORD})")
    for role, name, email in summary.logins:
        print(f"  {role:<11} {name:<34} {email}")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Create the PantryPilot demo world.")
    parser.add_argument("--reset", action="store_true", help="delete all existing data first")
    args = parser.parse_args()

    if args.reset:
        drop_tables()
        clear_agent_sessions()
    create_tables()

    with SessionLocal() as session:
        try:
            summary = seed_demo_world(session)
        except RuntimeError as error:
            print(error)
            return
    print_summary(summary)


if __name__ == "__main__":
    main()
