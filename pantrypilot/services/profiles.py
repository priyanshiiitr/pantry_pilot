"""Reading and updating the one profile row that belongs to each logged-in user.

DETERMINISTIC CODE: no AI involved. Every restaurant/pantry/driver account gets its
profile row at signup (see services/accounts.py), so these lookups should always
succeed — LookupError only happens if the data was somehow corrupted.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.models import Driver, Pantry, Restaurant, User


def get_restaurant_for_user(session: Session, user: User) -> Restaurant:
    """Return the Restaurant profile that belongs to this user."""
    restaurant = session.scalar(select(Restaurant).where(Restaurant.user_id == user.id))
    if restaurant is None:
        raise LookupError(f"No restaurant profile for user {user.id}.")
    return restaurant


def get_pantry_for_user(session: Session, user: User) -> Pantry:
    """Return the Pantry profile that belongs to this user."""
    pantry = session.scalar(select(Pantry).where(Pantry.user_id == user.id))
    if pantry is None:
        raise LookupError(f"No pantry profile for user {user.id}.")
    return pantry


def get_driver_for_user(session: Session, user: User) -> Driver:
    """Return the Driver profile that belongs to this user."""
    driver = session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise LookupError(f"No driver profile for user {user.id}.")
    return driver
