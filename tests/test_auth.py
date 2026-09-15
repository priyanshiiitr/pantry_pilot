"""Tests for the signup/login/logout API (Step 3)."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pantrypilot.auth.current_user import require_role
from pantrypilot.models import Role, User
from pantrypilot.web.schemas import SignupRequest


def test_signup_creates_account_and_logs_in(client: TestClient) -> None:
    """Signing up returns the new user and immediately starts a session."""
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "chef@example.com",
            "password": "letmein123",
            "display_name": "Chef Alice",
            "role": "restaurant",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "chef@example.com"
    assert body["role"] == "restaurant"
    assert "password" not in body and "password_hash" not in body

    me_response = client.get("/api/auth/me")
    assert me_response.json()["user"]["email"] == "chef@example.com"


def test_signup_creates_a_profile_row_for_each_role(client: TestClient) -> None:
    """Each role gets a starter profile row immediately, so later pages have something to show."""
    for role in ["restaurant", "pantry", "driver"]:
        response = client.post(
            "/api/auth/signup",
            json={"email": f"{role}@example.com", "password": "letmein123", "display_name": role, "role": role},
        )
        assert response.status_code == 200, response.text


def test_signup_rejects_duplicate_email(client: TestClient) -> None:
    """The same email can't be used to sign up twice."""
    payload = {"email": "dup@example.com", "password": "letmein123", "display_name": "First", "role": "pantry"}
    client.post("/api/auth/signup", json=payload)

    response = client.post("/api/auth/signup", json={**payload, "display_name": "Second"})

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_signup_rejects_admin_role() -> None:
    """The API rejects role="admin" before it even reaches our code (422 = bad request shape)."""
    with pytest.raises(ValidationError):
        SignupRequest(email="x@example.com", password="letmein123", display_name="X", role="admin")


def test_signup_rejects_short_password(client: TestClient) -> None:
    """A password under 8 characters is rejected with a 422, not saved."""
    response = client.post(
        "/api/auth/signup",
        json={"email": "short@example.com", "password": "abc", "display_name": "Short", "role": "driver"},
    )

    assert response.status_code == 422


def test_login_with_correct_password_succeeds(client: TestClient) -> None:
    """Logging in with the right password sets the session so /me recognizes you."""
    client.post(
        "/api/auth/signup",
        json={"email": "driver1@example.com", "password": "correct-horse", "display_name": "D1", "role": "driver"},
    )
    client.post("/api/auth/logout")

    response = client.post("/api/auth/login", json={"email": "driver1@example.com", "password": "correct-horse"})

    assert response.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["email"] == "driver1@example.com"


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    """A wrong password gets a 401, and no session is started."""
    client.post(
        "/api/auth/signup",
        json={"email": "driver2@example.com", "password": "correct-horse", "display_name": "D2", "role": "driver"},
    )
    client.post("/api/auth/logout")

    response = client.post("/api/auth/login", json={"email": "driver2@example.com", "password": "wrong-password"})

    assert response.status_code == 401
    assert client.get("/api/auth/me").json()["user"] is None


def test_me_without_login_returns_null_user(client: TestClient) -> None:
    """A fresh visitor with no cookie sees user: null, not an error."""
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user"] is None


def test_logout_clears_the_session(client: TestClient) -> None:
    """After logout, /me forgets who you are."""
    client.post(
        "/api/auth/signup",
        json={"email": "pantry1@example.com", "password": "letmein123", "display_name": "P1", "role": "pantry"},
    )

    client.post("/api/auth/logout")

    assert client.get("/api/auth/me").json()["user"] is None


def test_require_role_allows_matching_role() -> None:
    """The require_role dependency lets a user with the right role through."""
    dependency = require_role(Role.ADMIN)
    admin_user = User(id=1, email="a@example.com", role=Role.ADMIN, display_name="Admin", password_hash="x")

    assert dependency(user=admin_user) is admin_user


def test_require_role_blocks_wrong_role() -> None:
    """The require_role dependency raises 403 for a user with a different role."""
    dependency = require_role(Role.ADMIN)
    driver_user = User(id=2, email="d@example.com", role=Role.DRIVER, display_name="Driver", password_hash="x")

    with pytest.raises(HTTPException) as excinfo:
        dependency(user=driver_user)
    assert excinfo.value.status_code == 403
