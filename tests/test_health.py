"""Tests for the health-check endpoint (Step 1)."""

from fastapi.testclient import TestClient

from pantrypilot.web.main import app


def test_health_endpoint_reports_ok() -> None:
    """GET /api/health should answer 200 with ok=True and the app name."""
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["app"] == "PantryPilot"
