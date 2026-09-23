"""Signup, login, logout, and "who am I" — the endpoints under /api/auth.

DETERMINISTIC CODE: this just checks credentials and manages the login cookie
session. No AI is involved in deciding whether to let someone log in.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import (
    SESSION_USER_KEY,
    SESSION_VIEW_AS_KEY,
    get_optional_user,
    get_real_user,
)
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.accounts import authenticate, create_account, pick_account_to_preview
from pantrypilot.web.schemas import LoginRequest, MeResponse, SignupRequest, UserOut, ViewAsRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)) -> UserOut:
    """Create a new account (and its starter profile) and log the user straight in."""
    try:
        user = create_account(
            db,
            email=payload.email,
            password=payload.password,
            role=Role(payload.role),
            display_name=payload.display_name,
        )
    except ValueError as error:
        # e.g. "An account with this email already exists." — a normal, expected failure.
        raise HTTPException(status_code=400, detail=str(error)) from error

    request.session[SESSION_USER_KEY] = user.id
    return UserOut.from_user(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> UserOut:
    """Check email + password and, if correct, log the user in."""
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    request.session[SESSION_USER_KEY] = user.id
    return UserOut.from_user(user)


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    """Forget who is logged in by clearing everything in the session cookie."""
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(
    user: User | None = Depends(get_optional_user), real_user: User | None = Depends(get_real_user)
) -> MeResponse:
    """Tell the frontend who (if anyone) is currently logged in.

    Deliberately returns 200 with user=None instead of a 401 error, because
    "nobody is logged in yet" is a normal state, not a failure, every time a
    page first loads.

    `real_user` differs from `user` only while an admin is previewing another
    role, which is how the sidebar knows to show the "viewing as" banner.
    """
    return MeResponse(
        user=UserOut.from_user(user) if user else None,
        real_user=UserOut.from_user(real_user) if real_user else None,
    )


@router.post("/view-as", response_model=MeResponse)
def view_as(payload: ViewAsRequest, request: Request, db: Session = Depends(get_db)) -> MeResponse:
    """Let an admin preview another role's dashboard without logging out.

    Deliberately depends on get_real_user, not get_current_user: an admin who is
    already previewing a restaurant must still be able to switch again or return
    to their own view, and only the account that truly logged in may do either.
    """
    real_user = get_real_user(request, db)
    if real_user is None or real_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only an admin can switch views.")

    if payload.user_id is not None:
        previewed = db.get(User, payload.user_id)
        if previewed is None or not previewed.is_active:
            raise HTTPException(status_code=404, detail="That account doesn't exist.")
        if previewed.role == Role.ADMIN:
            # Previewing another admin would grant this admin's session a
            # different admin's identity for audit purposes, with nothing gained.
            raise HTTPException(status_code=400, detail="Use 'Back to admin' to return to your own view.")
    elif payload.role is None or payload.role == Role.ADMIN:
        request.session.pop(SESSION_VIEW_AS_KEY, None)
        return MeResponse(user=UserOut.from_user(real_user), real_user=UserOut.from_user(real_user))
    else:
        previewed = pick_account_to_preview(db, Role(payload.role))
        if previewed is None:
            raise HTTPException(status_code=404, detail=f"There are no {payload.role} accounts to preview yet.")

    request.session[SESSION_VIEW_AS_KEY] = previewed.id
    return MeResponse(user=UserOut.from_user(previewed), real_user=UserOut.from_user(real_user))
