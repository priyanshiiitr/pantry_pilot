"""The FastAPI web server — the backend API that the React frontend talks to.

DETERMINISTIC CODE: no AI reasoning ever happens in the web server. It only reads
and writes the database. The agents run separately in the background worker.

Run it with:  uvicorn pantrypilot.web.main:app --reload
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from pantrypilot.config import settings
from pantrypilot.database import create_tables
from pantrypilot.web.routes import admin, auth, driver, pantry, restaurant, tick


class HealthResponse(BaseModel):
    """The JSON shape returned by GET /api/health."""

    ok: bool
    app: str
    server_time: datetime


def health() -> HealthResponse:
    """Report that the backend is running.

    The React app calls this on startup to show "Backend connected".
    It's also handy for checking the server by hand in a browser.
    """
    return HealthResponse(ok=True, app=settings.app_name, server_time=datetime.now(timezone.utc))


def create_app() -> FastAPI:
    """Build the FastAPI application: create tables, add the login-cookie
    middleware, and attach every router of API endpoints."""
    # Safe to call every time the app starts: it only creates tables that don't
    # exist yet, so a fresh clone works with no separate "migrate" step.
    create_tables()

    app = FastAPI(title=settings.app_name, version="0.1.0")

    # SessionMiddleware turns request.session (a plain dict) into a signed cookie
    # in the browser. "Signed" means the browser can't edit it without the change
    # being detected, because it's signed with session_secret from .env.
    #
    # same_site has to relax to "none" once the frontend and API are on different
    # origins (Vercel and Render, say), or the browser simply won't send the
    # cookie and every request arrives logged out. Browsers only accept
    # SameSite=None together with Secure, so the two move as a pair — and "lax"
    # stays the default for local development over plain HTTP.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="pantrypilot_session",
        same_site="none" if settings.secure_cookies else "lax",
        https_only=settings.secure_cookies,
    )

    # Only added when origins are configured: locally the Vite proxy makes
    # frontend and API one origin, so CORS isn't involved at all.
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,  # required for the login cookie to cross origins
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_api_route("/api/health", health, methods=["GET"], response_model=HealthResponse)
    app.include_router(auth.router)
    app.include_router(restaurant.router)
    app.include_router(pantry.router)
    app.include_router(driver.router)
    app.include_router(admin.router)
    app.include_router(tick.router)

    return app


# Uvicorn looks for this variable: "pantrypilot.web.main:app".
app: FastAPI = create_app()
