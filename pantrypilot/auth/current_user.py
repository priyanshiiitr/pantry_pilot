""""Who is logged in?" and "is this user allowed here?" — as FastAPI dependencies.

How login works without a username/password on every request: after a successful
login, we write the user's id into `request.session`. Starlette's SessionMiddleware
(set up in web/main.py) turns that into a signed cookie in the browser — signed means
tampering with it invalidates it, so a visitor can't just edit the cookie to become
a different user. Every later request sends the cookie back automatically, and these
functions read the id back out of it.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from pantrypilot.database import get_db
from pantrypilot.models import Role, User

# The key we store the logged-in user's id under inside request.session.
SESSION_USER_KEY = "user_id"


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Return the logged-in User, or None if nobody is logged in.

    Used for pages/endpoints that behave differently for guests vs. logged-in users
    (like the landing page) without treating "not logged in" as an error.
    """
    user_id = request.session.get(SESSION_USER_KEY)
    if user_id is None:
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Return the logged-in User, or fail the request with 401 Unauthorized.

    Use this on any endpoint that requires *some* logged-in account, regardless of role.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="You need to be logged in for this.")
    return user


def require_role(*roles: Role):
    """Build a dependency that only allows the given role(s), else 403 Forbidden.

    Example: `db_user: User = Depends(require_role(Role.ADMIN))` on an admin-only route.
    """
    allowed_roles = {role.value for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Your account type can't access this.")
        return user

    return dependency
