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

# Set only while an admin is previewing another role's dashboard ("Switch view"
# in the sidebar). Holds the id of the account being previewed.
SESSION_VIEW_AS_KEY = "view_as_user_id"


def get_real_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Return the account that actually logged in, ignoring any "view as" preview.

    Anything that decides *permissions* must use this, never the previewed user —
    otherwise a preview could be used to gain access the real account doesn't have.
    """
    user_id = request.session.get(SESSION_USER_KEY)
    if user_id is None:
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_optional_user(
    request: Request, real_user: User | None = Depends(get_real_user), db: Session = Depends(get_db)
) -> User | None:
    """Return the User whose dashboard should be shown, or None if nobody is logged in.

    Normally that's whoever logged in. While an admin is previewing another role
    (see web/routes/auth.py:view_as), it's the account being previewed instead.

    The admin check is re-run on every request rather than trusted from when the
    preview started, so demoting an account immediately ends its previews too.
    """
    if real_user is None:
        return None

    view_as_id = request.session.get(SESSION_VIEW_AS_KEY)
    if view_as_id is None or real_user.role != Role.ADMIN:
        return real_user

    previewed = db.get(User, view_as_id)
    if previewed is None or not previewed.is_active:
        return real_user
    return previewed


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
