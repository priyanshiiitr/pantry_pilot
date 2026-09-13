"""Profile tables for the three kinds of place/person on the map:
restaurants (donors), pantries (recipients) and drivers (volunteers).

Weekly hours format, used by `Pantry.opening_hours` and `Driver.availability`:
    {"mon": ["09:00", "17:00"], "tue": ["09:00", "17:00"], ...}
A missing day means closed / not available. Times are local city time
(settings.city_timezone).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pantrypilot.database import Base, UtcDateTime, utc_now

if TYPE_CHECKING:
    from pantrypilot.models.offers import Delivery, DispatchRequest, Offer
    from pantrypilot.models.users import User

# The dietary restriction tags a pantry can choose from.
# The AI agents read these tags; they are facts, not rules the code enforces.
DIETARY_RESTRICTIONS: tuple[str, ...] = (
    "no_pork",
    "no_beef",
    "halal_only",
    "kosher_only",
    "vegetarian_only",
    "no_nuts",
    "no_alcohol",
)

# Note on JSON columns: if you change a list/dict in place (e.g. .append()), SQLAlchemy
# won't notice. Always assign a new value instead: pantry.dietary_restrictions = [...].


class Restaurant(Base):
    """A donor: restaurant, bakery or grocery store that posts surplus food."""

    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float]
    lon: Mapped[float]
    phone: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="restaurant")
    offers: Mapped[list["Offer"]] = relationship(back_populates="restaurant")


class Pantry(Base):
    """A recipient: food pantry or shelter that can receive food."""

    __tablename__ = "pantries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float]
    lon: Mapped[float]
    phone: Mapped[str] = mapped_column(String(40), default="")
    capacity_kg_per_day: Mapped[float] = mapped_column(default=100.0)
    has_fridge: Mapped[bool] = mapped_column(default=False)
    has_freezer: Mapped[bool] = mapped_column(default=False)
    dietary_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    opening_hours: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    accepting_donations: Mapped[bool] = mapped_column(default=True)  # pantry can pause itself
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="pantry")
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="pantry")


class Driver(Base):
    """A volunteer driver who picks food up and drops it at a pantry."""

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="")
    lat: Mapped[float]  # home base
    lon: Mapped[float]
    service_radius_km: Mapped[float] = mapped_column(default=10.0)
    vehicle: Mapped[str] = mapped_column(String(60), default="car")
    max_kg: Mapped[float] = mapped_column(default=50.0)
    has_cooler: Mapped[bool] = mapped_column(default=False)
    availability: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    on_duty: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="driver")
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="driver")
    dispatch_requests: Mapped[list["DispatchRequest"]] = relationship(back_populates="driver")
