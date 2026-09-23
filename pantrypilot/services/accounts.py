"""Creating accounts and checking logins.

DETERMINISTIC CODE: no AI involved. This is the one place that knows how to turn
a signup form into a User row plus the matching profile row (Restaurant/Pantry/Driver).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.auth.passwords import hash_password, verify_password
from pantrypilot.models import Driver, Pantry, Restaurant, Role, User

# New signups start at a generic point in the demo city and a placeholder address.
# Step 4 (profile editing) is where the user fills in their real details.
_DEFAULT_LAT = 47.6062
_DEFAULT_LON = -122.3321
_DEFAULT_ADDRESS = "Address not set yet — edit this in your profile"


def get_user_by_email(session: Session, email: str) -> User | None:
    """Look up a user by email, or return None if no account uses it."""
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def create_account(session: Session, *, email: str, password: str, role: Role, display_name: str) -> User:
    """Create a new login plus its matching profile row, and save it.

    Raises ValueError if the email is already registered, so the route can turn
    that into a clean 400 error instead of a database crash.
    """
    normalized_email = email.strip().lower()
    if get_user_by_email(session, normalized_email) is not None:
        raise ValueError("An account with this email already exists.")

    user = User(
        email=normalized_email,
        role=role,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
    )
    session.add(user)

    # Every restaurant/pantry/driver account gets a starter profile row immediately,
    # with placeholder location and details, so the rest of the app always has
    # something to show. The user fills in the real values in Step 4.
    if role == Role.RESTAURANT:
        session.add(
            Restaurant(user=user, name=display_name, address=_DEFAULT_ADDRESS, lat=_DEFAULT_LAT, lon=_DEFAULT_LON)
        )
    elif role == Role.PANTRY:
        session.add(
            Pantry(user=user, name=display_name, address=_DEFAULT_ADDRESS, lat=_DEFAULT_LAT, lon=_DEFAULT_LON)
        )
    elif role == Role.DRIVER:
        session.add(Driver(user=user, name=display_name, lat=_DEFAULT_LAT, lon=_DEFAULT_LON))
    else:
        # Admin accounts are only created by the seed script, never through signup.
        raise ValueError(f"Cannot self-sign-up as role={role!r}.")

    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Return the User if the email+password match an active account, else None."""
    user = get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def pick_account_to_preview(session: Session, role: Role) -> User | None:
    """Pick which account an admin sees when they switch to previewing `role`.

    Always the same account for a given role (lowest id, so the seeded demo
    accounts win over later signups), so switching away and back lands somewhere
    predictable during a demo.
    """
    return session.scalars(
        select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.id).limit(1)
    ).first()
