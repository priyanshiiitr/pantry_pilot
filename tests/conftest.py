"""Shared pytest fixtures.

A *fixture* is a helper pytest creates for a test when the test asks for it by name
(e.g. a test with a `db_session` parameter gets a fresh database).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pantrypilot.database import build_engine, create_tables


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
