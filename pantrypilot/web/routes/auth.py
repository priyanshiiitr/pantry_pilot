"""Signup, login, logout, and "who am I" — the endpoints under /api/auth.

DETERMINISTIC CODE: this just checks credentials and manages the login cookie
session. No AI is involved in deciding whether to let someone log in.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import SESSION_USER_KEY, get_optional_user
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.accounts import authenticate, create_account
from pantrypilot.web.schemas import LoginRequest, MeResponse, SignupRequest, UserOut

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
def me(user: User | None = Depends(get_optional_user)) -> MeResponse:
    """Tell the frontend who (if anyone) is currently logged in.

    Deliberately returns 200 with user=None instead of a 401 error, because
    "nobody is logged in yet" is a normal state, not a failure, every time a
    page first loads.
    """
    return MeResponse(user=UserOut.from_user(user) if user else None)
