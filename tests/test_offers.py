"""Tests for posting and listing offers (Step 5)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from pantrypilot.auth.passwords import hash_password
from pantrypilot.database import utc_now
from pantrypilot.models import Role, User


def signup_and_login(client: TestClient, role: str, email: str) -> dict:
    """Create a fresh account for `role` (leaves the client logged in as that user)."""
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "letmein123", "display_name": f"Test {role}", "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()


def future_iso(hours: float = 2) -> str:
    """An ISO 8601 UTC timestamp `hours` from now, e.g. for pickup_deadline."""
    return (utc_now() + timedelta(hours=hours)).isoformat()


def create_admin_and_login(client: TestClient, email: str) -> dict:
    """Insert an admin user straight into the test database and log in as them.

    Admin accounts are deliberately not signup-able through the API (only the seed
    script creates them — see services/accounts.py), so tests reach into the same
    test database the API is using (via `client.session_factory`, set up in
    tests/conftest.py) to create one directly.
    """
    with client.session_factory() as session:
        admin = User(email=email, role=Role.ADMIN, display_name="Test Admin", password_hash=hash_password("demo1234"))
        session.add(admin)
        session.commit()

    response = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert response.status_code == 200, response.text
    return response.json()


def make_offer_payload(**overrides) -> dict:
    """A valid OfferCreate body, with any fields overridden for a specific test."""
    payload = {
        "title": "Unsold sandwiches",
        "description": "40 sandwiches, various fillings.",
        "quantity_text": "40 sandwiches",
        "allergen_notes": "contains dairy, gluten",
        "pickup_deadline": future_iso(),
    }
    payload.update(overrides)
    return payload


def test_restaurant_can_post_and_list_offers(client: TestClient) -> None:
    """Posting an offer makes it show up in the restaurant's own list, as status=posted."""
    signup_and_login(client, "restaurant", "bakery@example.com")

    created = client.post("/api/restaurant/offers", json=make_offer_payload())
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "posted"
    assert body["title"] == "Unsold sandwiches"

    listed = client.get("/api/restaurant/offers")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]


def test_restaurant_can_fetch_a_single_offer(client: TestClient) -> None:
    """GET /offers/{id} returns the same offer that was created."""
    signup_and_login(client, "restaurant", "deli@example.com")
    created = client.post("/api/restaurant/offers", json=make_offer_payload(title="Leftover soup")).json()

    response = client.get(f"/api/restaurant/offers/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Leftover soup"


def test_restaurant_cannot_fetch_another_restaurants_offer(client: TestClient) -> None:
    """One restaurant can't read a different restaurant's offer by guessing its id."""
    signup_and_login(client, "restaurant", "shop1@example.com")
    created = client.post("/api/restaurant/offers", json=make_offer_payload()).json()
    client.post("/api/auth/logout")

    signup_and_login(client, "restaurant", "shop2@example.com")
    response = client.get(f"/api/restaurant/offers/{created['id']}")

    assert response.status_code == 404


def test_offer_rejects_deadline_in_the_past(client: TestClient) -> None:
    """A pickup deadline that has already passed is rejected."""
    signup_and_login(client, "restaurant", "late@example.com")

    response = client.post("/api/restaurant/offers", json=make_offer_payload(pickup_deadline=future_iso(-1)))

    assert response.status_code == 422


def test_offer_rejects_blank_title(client: TestClient) -> None:
    """A blank title is rejected."""
    signup_and_login(client, "restaurant", "blank@example.com")

    response = client.post("/api/restaurant/offers", json=make_offer_payload(title="   "))

    assert response.status_code == 422


def test_driver_cannot_post_offers(client: TestClient) -> None:
    """Posting an offer is restaurant-only."""
    signup_and_login(client, "driver", "driver@example.com")

    response = client.post("/api/restaurant/offers", json=make_offer_payload())

    assert response.status_code == 403


def test_admin_sees_offers_from_every_restaurant(client: TestClient) -> None:
    """The admin's list includes offers from multiple restaurants, with restaurant names attached."""
    signup_and_login(client, "restaurant", "r1@example.com")
    client.post("/api/restaurant/offers", json=make_offer_payload(title="From R1"))
    client.post("/api/auth/logout")

    signup_and_login(client, "restaurant", "r2@example.com")
    client.post("/api/restaurant/offers", json=make_offer_payload(title="From R2"))
    client.post("/api/auth/logout")

    create_admin_and_login(client, "boss@example.com")
    response = client.get("/api/admin/offers")

    assert response.status_code == 200
    titles_and_restaurants = {(o["title"], o["restaurant_name"]) for o in response.json()}
    assert ("From R1", "Test restaurant") in titles_and_restaurants
    assert ("From R2", "Test restaurant") in titles_and_restaurants


def test_restaurant_cannot_see_admin_offers_list(client: TestClient) -> None:
    """The admin offers list is admin-only."""
    signup_and_login(client, "restaurant", "nosneaking@example.com")

    response = client.get("/api/admin/offers")

    assert response.status_code == 403


def test_restaurant_sees_the_agents_progress_on_its_own_offer(client: TestClient) -> None:
    """The offer page's live progress feed.

    Without it a restaurant sees only an "Agent working…" badge, which on a
    rate-limited free model tier is indistinguishable from a crash.
    """
    from pantrypilot.models import AgentLog

    signup_and_login(client, "restaurant", "deli@example.com")
    created = client.post("/api/restaurant/offers", json=make_offer_payload()).json()
    with client.session_factory() as session:
        session.add(
            AgentLog(
                offer_id=created["id"], agent_name="matching", event_type="tool_call",
                tool_name="find_nearby_pantries", summary="Checking 7 nearby pantries",
            )
        )
        session.commit()

    response = client.get(f"/api/restaurant/offers/{created['id']}/activity")

    assert response.status_code == 200
    assert [entry["summary"] for entry in response.json()] == ["Checking 7 nearby pantries"]


def test_agent_progress_is_scoped_to_the_offers_owner(client: TestClient) -> None:
    """Activity is guarded the same way the offer itself is — by ownership, not by id."""
    signup_and_login(client, "restaurant", "shop1@example.com")
    created = client.post("/api/restaurant/offers", json=make_offer_payload()).json()
    client.post("/api/auth/logout")

    signup_and_login(client, "restaurant", "shop2@example.com")

    assert client.get(f"/api/restaurant/offers/{created['id']}/activity").status_code == 404


def test_agent_progress_is_empty_before_the_agents_start(client: TestClient) -> None:
    """A brand-new offer has no activity yet — an empty list, not an error."""
    signup_and_login(client, "restaurant", "deli@example.com")
    created = client.post("/api/restaurant/offers", json=make_offer_payload()).json()

    response = client.get(f"/api/restaurant/offers/{created['id']}/activity")

    assert response.status_code == 200
    assert response.json() == []
