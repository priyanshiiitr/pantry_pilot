"""Shared pytest fixtures.

A *fixture* is a helper pytest creates for a test when the test asks for it by name
(e.g. a test with a `db_session` parameter gets a fresh database).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pantrypilot.database import build_engine, create_tables, get_db
from pantrypilot.web.main import app


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """Give a test its own empty database, stored in a temporary file.

    The real data/pantrypilot.db is never touched by tests.
    """
    test_engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    create_tables(test_engine)
    make_session = sessionmaker(bind=test_engine, expire_on_commit=False)

    with make_session() as session:
        yield session

    # Close the file connection, otherwise Windows can't delete the temp folder.
    test_engine.dispose()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Give a test a FastAPI TestClient wired to its own temporary database.

    Without this, every API test would read and write the real data/pantrypilot.db —
    the one with your seeded demo accounts. `app.dependency_overrides` is FastAPI's
    built-in way to swap out one dependency (here, get_db) just for tests.
    """
    test_engine = build_engine(f"sqlite:///{(tmp_path / 'test_api.db').as_posix()}")
    create_tables(test_engine)
    make_session = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = make_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        # Attach the session factory so tests can reach into the SAME test database
        # directly (e.g. to create an admin user, which the signup API refuses to do
        # on purpose — see services/accounts.py).
        test_client.session_factory = make_session
        yield test_client

    app.dependency_overrides.clear()
    test_engine.dispose()
