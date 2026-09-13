"""The FastAPI web server — the backend API that the React frontend talks to.

Right now it only has a health-check endpoint, so we can prove the frontend and
backend are connected. Later steps add routers for login, restaurants, pantries,
drivers and the admin dashboard.

DETERMINISTIC CODE: no AI reasoning ever happens in the web server. It only reads
and writes the database. The agents run separately in the background worker.

Run it with:  uvicorn pantrypilot.web.main:app --reload
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from pantrypilot.config import settings


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
    """Build the FastAPI application and attach all its endpoints.

    Every backend URL starts with /api. The React dev server forwards (proxies)
    anything under /api to this backend, so both look like one website to the browser.
    """
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_api_route("/api/health", health, methods=["GET"], response_model=HealthResponse)
    return app


# Uvicorn looks for this variable: "pantrypilot.web.main:app".
app: FastAPI = create_app()
