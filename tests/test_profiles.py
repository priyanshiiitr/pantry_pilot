"""Tests for the restaurant/pantry/driver profile API (Step 4)."""

from fastapi.testclient import TestClient


def signup(client: TestClient, role: str, email: str = None) -> dict:
    """Sign up a fresh account for `role` and return the created user (already logged in)."""
    response = client.post(
        "/api/auth/signup",
        json={
            "email": email or f"{role}@example.com",
            "password": "letmein123",
            "display_name": f"Test {role}",
            "role": role,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_new_restaurant_gets_a_default_profile(client: TestClient) -> None:
    """Right after signup, GET /profile returns the placeholder profile created at signup."""
    signup(client, "restaurant")

    response = client.get("/api/restaurant/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test restaurant"
    assert "not set yet" in body["address"]


def test_restaurant_can_update_profile(client: TestClient) -> None:
    """Saved changes come back on the next GET."""
    signup(client, "restaurant")

    update = client.put(
        "/api/restaurant/profile",
        json={"name": "Golden Crust Bakery", "address": "123 Main St", "lat": 47.61, "lon": -122.33, "phone": "555-1234"},
    )
    assert update.status_code == 200, update.text

    fetched = client.get("/api/restaurant/profile").json()
    assert fetched["name"] == "Golden Crust Bakery"
    assert fetched["phone"] == "555-1234"


def test_restaurant_profile_rejects_bad_latitude(client: TestClient) -> None:
    """A latitude outside -90..90 is refused before it reaches the database."""
    signup(client, "restaurant")

    response = client.put(
        "/api/restaurant/profile", json={"name": "X", "address": "Y", "lat": 999, "lon": 0, "phone": ""}
    )

    assert response.status_code == 422


def test_driver_cannot_access_restaurant_profile(client: TestClient) -> None:
    """A driver's account can't read or write a restaurant's profile endpoint."""
    signup(client, "driver")

    response = client.get("/api/restaurant/profile")

    assert response.status_code == 403


def test_logged_out_user_cannot_access_any_profile(client: TestClient) -> None:
    """A guest (nobody logged in) gets 401, not 403 — there's no role to even check yet."""
    response = client.get("/api/restaurant/profile")

    assert response.status_code == 401


def test_pantry_profile_round_trip_with_hours_and_restrictions(client: TestClient) -> None:
    """Opening hours and dietary restrictions save and load correctly."""
    signup(client, "pantry")

    update = client.put(
        "/api/pantry/profile",
        json={
            "name": "Riverside Food Bank",
            "address": "1 River Rd",
            "lat": 47.5,
            "lon": -122.3,
            "phone": "",
            "capacity_kg_per_day": 200,
            "has_fridge": True,
            "has_freezer": True,
            "dietary_restrictions": ["no_pork"],
            "opening_hours": {"mon": ["08:00", "16:00"], "tue": ["08:00", "16:00"]},
            "accepting_donations": True,
            "notes": "Largest storage in the city.",
        },
    )
    assert update.status_code == 200, update.text

    fetched = client.get("/api/pantry/profile").json()
    assert fetched["dietary_restrictions"] == ["no_pork"]
    assert fetched["opening_hours"]["mon"] == ["08:00", "16:00"]
    assert fetched["has_freezer"] is True


def test_pantry_profile_rejects_unknown_dietary_tag(client: TestClient) -> None:
    """A dietary tag that isn't in the known list is refused."""
    signup(client, "pantry")

    response = client.put(
        "/api/pantry/profile",
        json={
            "name": "X",
            "address": "Y",
            "lat": 0,
            "lon": 0,
            "capacity_kg_per_day": 10,
            "dietary_restrictions": ["no_shellfish_but_thats_not_a_real_tag"],
        },
    )

    assert response.status_code == 422


def test_pantry_profile_rejects_backwards_hours(client: TestClient) -> None:
    """Closing before opening doesn't make sense and should be rejected."""
    signup(client, "pantry")

    response = client.put(
        "/api/pantry/profile",
        json={
            "name": "X",
            "address": "Y",
            "lat": 0,
            "lon": 0,
            "capacity_kg_per_day": 10,
            "opening_hours": {"mon": ["17:00", "09:00"]},
        },
    )

    assert response.status_code == 422


def test_pantry_profile_rejects_zero_capacity(client: TestClient) -> None:
    """Capacity must be a positive number."""
    signup(client, "pantry")

    response = client.put(
        "/api/pantry/profile", json={"name": "X", "address": "Y", "lat": 0, "lon": 0, "capacity_kg_per_day": 0}
    )

    assert response.status_code == 422


def test_driver_profile_round_trip_with_availability(client: TestClient) -> None:
    """Availability, vehicle info and on_duty save and load correctly."""
    signup(client, "driver")

    update = client.put(
        "/api/driver/profile",
        json={
            "name": "Sam Rivera",
            "phone": "555-9999",
            "lat": 47.6,
            "lon": -122.3,
            "service_radius_km": 10,
            "vehicle": "car",
            "max_kg": 80,
            "has_cooler": True,
            "availability": {"mon": ["09:00", "17:00"]},
            "on_duty": True,
        },
    )
    assert update.status_code == 200, update.text

    fetched = client.get("/api/driver/profile").json()
    assert fetched["vehicle"] == "car"
    assert fetched["availability"]["mon"] == ["09:00", "17:00"]
    assert fetched["on_duty"] is True


def test_driver_profile_rejects_zero_capacity(client: TestClient) -> None:
    """A driver who can carry 0 kg can't do deliveries — reject it."""
    signup(client, "driver")

    response = client.put(
        "/api/driver/profile",
        json={"name": "X", "lat": 0, "lon": 0, "service_radius_km": 10, "max_kg": 0},
    )

    assert response.status_code == 422
