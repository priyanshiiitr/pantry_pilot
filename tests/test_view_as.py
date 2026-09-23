"""Tests for the admin "Switch view" preview (web/routes/auth.py:view_as).

The security-relevant rule these pin down: previewing must never *grant* access.
Permission checks read the account that really logged in (auth/current_user.py's
get_real_user), never the previewed one.

These build their users through `client.session_factory` rather than the
`db_session` fixture, because the two fixtures own separate temporary databases
(see conftest.py) and these tests need the API and the rows in the same one.
"""

from fastapi.testclient import TestClient

from pantrypilot.auth.passwords import hash_password
from pantrypilot.models import Role, User
from pantrypilot.services.accounts import create_account

PASSWORD = "demo1234"


def make_user(client: TestClient, email: str, role: Role) -> None:
    with client.session_factory() as session:
        create_account(session, email=email, password=PASSWORD, role=role, display_name=f"{role} account")


def make_admin(client: TestClient, email: str = "admin@test.local") -> None:
    """Admins can't self-sign-up (services/accounts.py), so build one directly."""
    with client.session_factory() as session:
        session.add(
            User(email=email, role=Role.ADMIN, display_name="Admin", password_hash=hash_password(PASSWORD))
        )
        session.commit()


def login(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


def test_admin_can_preview_a_restaurant(client: TestClient) -> None:
    """Switching view returns the previewed account, while still reporting the real one."""
    make_admin(client)
    make_user(client, "r@test.local", Role.RESTAURANT)
    login(client, "admin@test.local")

    response = client.post("/api/auth/view-as", json={"role": "restaurant"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "r@test.local"
    assert body["real_user"]["email"] == "admin@test.local"


def test_preview_persists_across_requests(client: TestClient) -> None:
    """The preview lives in the session cookie, so the next request still sees it."""
    make_admin(client)
    make_user(client, "p@test.local", Role.PANTRY)
    login(client, "admin@test.local")
    client.post("/api/auth/view-as", json={"role": "pantry"})

    body = client.get("/api/auth/me").json()

    assert body["user"]["email"] == "p@test.local"
    assert body["real_user"]["email"] == "admin@test.local"


def test_admin_can_switch_back(client: TestClient) -> None:
    """Returning to the admin's own view clears the preview.

    This is why view_as depends on get_real_user: while previewing a restaurant,
    a get_current_user check would see role=restaurant and lock the admin out of
    their own switcher.
    """
    make_admin(client)
    make_user(client, "r@test.local", Role.RESTAURANT)
    login(client, "admin@test.local")
    client.post("/api/auth/view-as", json={"role": "restaurant"})

    response = client.post("/api/auth/view-as", json={"role": "admin"})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@test.local"
    assert client.get("/api/admin/stats").status_code == 200


def test_previewing_does_not_grant_admin_access(client: TestClient) -> None:
    """While previewing another role, the admin API is correctly closed."""
    make_admin(client)
    make_user(client, "r@test.local", Role.RESTAURANT)
    login(client, "admin@test.local")
    client.post("/api/auth/view-as", json={"role": "restaurant"})

    assert client.get("/api/admin/stats").status_code == 403


def test_non_admin_cannot_switch_views(client: TestClient) -> None:
    """The escalation this must never allow: a driver previewing their way into admin."""
    make_user(client, "d@test.local", Role.DRIVER)
    make_admin(client)
    login(client, "d@test.local")

    response = client.post("/api/auth/view-as", json={"role": "admin"})

    assert response.status_code == 403
    assert client.get("/api/admin/stats").status_code == 403


def test_a_demoted_admin_immediately_loses_their_preview(client: TestClient) -> None:
    """An account demoted out of admin stops being able to use a preview it already had.

    get_optional_user re-checks the real user's role on every request rather than
    trusting that the preview was legitimate when it started.
    """
    make_admin(client)
    make_user(client, "r@test.local", Role.RESTAURANT)
    login(client, "admin@test.local")
    client.post("/api/auth/view-as", json={"role": "restaurant"})

    with client.session_factory() as session:
        admin = session.query(User).filter(User.email == "admin@test.local").one()
        admin.role = Role.DRIVER
        session.commit()

    # The preview key is still in the cookie, but is now ignored entirely.
    assert client.get("/api/auth/me").json()["user"]["email"] == "admin@test.local"


def test_previewing_a_role_with_no_accounts_is_a_clear_error(client: TestClient) -> None:
    """Asking to preview a role nobody has yet is a 404, not a crash."""
    make_admin(client)
    login(client, "admin@test.local")

    response = client.post("/api/auth/view-as", json={"role": "pantry"})

    assert response.status_code == 404


def test_admin_can_preview_one_specific_account(client: TestClient) -> None:
    """Which driver matters: the agents' request went to exactly one of them.

    Previewing by role alone lands on a representative account, which is rarely
    the one holding the work — so the admin could not reach the driver who had
    been asked.
    """
    make_admin(client)
    make_user(client, "first@test.local", Role.DRIVER)
    make_user(client, "second@test.local", Role.DRIVER)
    login(client, "admin@test.local")

    with client.session_factory() as session:
        wanted = session.query(User).filter(User.email == "second@test.local").one().id

    response = client.post("/api/auth/view-as", json={"user_id": wanted})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "second@test.local"


def test_switching_between_two_accounts_does_not_need_a_trip_via_admin(client: TestClient) -> None:
    """An admin already previewing one driver can hop straight to another."""
    make_admin(client)
    make_user(client, "first@test.local", Role.DRIVER)
    make_user(client, "second@test.local", Role.DRIVER)
    login(client, "admin@test.local")

    with client.session_factory() as session:
        ids = {u.email: u.id for u in session.query(User).all()}

    client.post("/api/auth/view-as", json={"user_id": ids["first@test.local"]})
    response = client.post("/api/auth/view-as", json={"user_id": ids["second@test.local"]})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "second@test.local"


def test_the_account_list_is_readable_while_already_previewing(client: TestClient) -> None:
    """Otherwise the sidebar's switcher would vanish the moment it was used."""
    make_admin(client)
    make_user(client, "d@test.local", Role.DRIVER)
    login(client, "admin@test.local")
    client.post("/api/auth/view-as", json={"role": "driver"})

    assert client.get("/api/admin/switchable-accounts").status_code == 200
    # ...while the rest of the admin API stays closed.
    assert client.get("/api/admin/overview").status_code == 403


def test_a_non_admin_cannot_read_the_account_list(client: TestClient) -> None:
    """It names every account in the system, so it stays admin-only."""
    make_user(client, "d@test.local", Role.DRIVER)
    login(client, "d@test.local")

    assert client.get("/api/admin/switchable-accounts").status_code == 403


def test_previewing_a_non_existent_account_is_a_clear_error(client: TestClient) -> None:
    make_admin(client)
    login(client, "admin@test.local")

    assert client.post("/api/auth/view-as", json={"user_id": 999999}).status_code == 404


def test_an_admin_cannot_preview_another_admin(client: TestClient) -> None:
    """Nothing is gained, and it muddies who actually answered a decision."""
    make_admin(client)
    make_admin(client, "other@test.local")
    login(client, "admin@test.local")

    with client.session_factory() as session:
        other = session.query(User).filter(User.email == "other@test.local").one().id

    assert client.post("/api/auth/view-as", json={"user_id": other}).status_code == 400
