"""Database connection, the base class for tables, and small shared helpers.

DETERMINISTIC CODE: plain storage. No AI reasoning happens here.

Key ideas (in plain words):
- An *engine* is SQLAlchemy's connection to the database file.
- A *session* is one "conversation" with the database: you add/change rows, then commit.
- Every table class (in pantrypilot/models/) inherits from `Base`.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from pantrypilot.config import settings


class Base(DeclarativeBase):
    """Parent class of every database table. SQLAlchemy uses it to find all tables."""


def utc_now() -> datetime:
    """Return the current time in UTC, with timezone info attached.

    We store every timestamp in UTC so there is never confusion about time zones.
    """
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator[datetime]):
    """A date-time column that always hands back timezone-aware UTC datetimes.

    Why this exists: SQLite forgets timezone info. Without this, a time read back
    from the database would be "naive" (no timezone), and comparing it with
    utc_now() would crash with a TypeError.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convert a Python datetime into what gets saved (plain UTC)."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Only timezone-aware datetimes can be stored. Use utc_now().")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convert a saved value back into a UTC-aware Python datetime."""
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


def _set_sqlite_options(dbapi_connection: Any, _connection_record: Any) -> None:
    """Turn on two SQLite settings every time a connection opens.

    - WAL mode lets the web server and the agent worker read and write at the same time.
    - foreign_keys=ON makes SQLite enforce links between tables (it's off by default!).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def normalise_database_url(database_url: str) -> str:
    """Point a Postgres URL at the driver we actually install.

    Hosting providers hand out `postgres://` or `postgresql://`, and SQLAlchemy
    reads both as a request for psycopg2. We install psycopg 3, so without this
    a deployment fails at startup with "ModuleNotFoundError: psycopg2" — which
    says nothing useful about the real problem.
    """
    for prefix in ("postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg://" + database_url[len(prefix) :]
    return database_url


def build_engine(database_url: str) -> Engine:
    """Create a database engine for the given URL.

    For SQLite it also makes sure the folder for the database file exists and
    applies the SQLite options above. Tests call this with a temporary file.
    """
    database_url = normalise_database_url(database_url)
    is_sqlite = database_url.startswith("sqlite")
    # check_same_thread=False: FastAPI may use the connection from different threads.
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    # pool_pre_ping: a hosted Postgres drops idle connections, and a free web
    # service sits idle a lot — without this the first request after a quiet
    # spell fails on a stale connection.
    new_engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=not is_sqlite)

    if is_sqlite:
        database_file = new_engine.url.database
        if database_file and database_file != ":memory:":
            Path(database_file).parent.mkdir(parents=True, exist_ok=True)
        event.listen(new_engine, "connect", _set_sqlite_options)

    return new_engine


# The app's real database, configured from .env (default: data/pantrypilot.db).
engine: Engine = build_engine(settings.database_url)

# Call SessionLocal() to open a session. expire_on_commit=False keeps objects
# readable after commit, which is simpler for beginners and for API responses.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables(target_engine: Engine | None = None) -> None:
    """Create any tables that don't exist yet. Safe to call many times."""
    # Importing the models package registers every table class with Base.
    # It's imported here (not at the top) to avoid a circular import, because models import Base from this file.
    import pantrypilot.models  # noqa: F401

    Base.metadata.create_all(target_engine or engine)


def drop_tables(target_engine: Engine | None = None) -> None:
    """Delete ALL tables and their data. Used by scripts/reset_db.py and tests."""
    import pantrypilot.models  # noqa: F401

    Base.metadata.drop_all(target_engine or engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that hands a route one database session and closes it after.

    Usage in a route: `db: Session = Depends(get_db)`.
    Tests replace this with a temporary database via `app.dependency_overrides[get_db]`,
    so running the test suite never touches the real data/pantrypilot.db file.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
