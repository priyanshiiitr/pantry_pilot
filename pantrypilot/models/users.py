"""The `users` table: every login account, whatever its role."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pantrypilot.database import Base, UtcDateTime, utc_now

if TYPE_CHECKING:  # only for editors/type checkers; avoids circular imports at runtime
    from pantrypilot.models.places import Driver, Pantry, Restaurant


class Role(StrEnum):
    """The four kinds of account. Stored in the database as plain text, e.g. "pantry"."""

    RESTAURANT = "restaurant"
    PANTRY = "pantry"
    DRIVER = "driver"
    ADMIN = "admin"


class User(Base):
    """A person who can log in. Their role decides which pages they may use.

    Restaurant, pantry and driver users also have exactly ONE profile row in the
    matching table (see places.py). Admins have no profile.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # bcrypt hash, never the real password
    role: Mapped[str] = mapped_column(String(20))  # one of Role
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    # "Relationships" let you write user.pantry instead of querying by hand.
    restaurant: Mapped["Restaurant | None"] = relationship(back_populates="user")
    pantry: Mapped["Pantry | None"] = relationship(back_populates="user")
    driver: Mapped["Driver | None"] = relationship(back_populates="user")

    def __repr__(self) -> str:
        """Short readable text when printing a User (handy while debugging)."""
        return f"<User {self.id} {self.email} ({self.role})>"
