"""Pydantic shapes of API requests and responses.

Why this matters: FastAPI checks incoming JSON against these classes automatically
(a bad request gets a clear 422 error instead of crashing our code), and it uses
them to generate the interactive docs at /docs.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from pantrypilot.database import utc_now
from pantrypilot.models import DIETARY_RESTRICTIONS, Offer, User

# Only these three roles can sign up through the form. Admin accounts are only
# ever created by the seed script — see pantrypilot/services/accounts.py.
SignupRole = Literal["restaurant", "pantry", "driver"]


class UserOut(BaseModel):
    """The public shape of a logged-in user, sent to the frontend. No password hash!"""

    id: int
    email: str
    role: str
    display_name: str

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        """Build a UserOut from a database User row."""
        return cls(id=user.id, email=user.email, role=user.role, display_name=user.display_name)


class MeResponse(BaseModel):
    """Response for GET /api/auth/me. `user` is None when nobody is logged in."""

    user: UserOut | None


class SignupRequest(BaseModel):
    """Body of POST /api/auth/signup."""

    email: str
    password: str
    display_name: str
    role: SignupRole

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, value: str) -> str:
        """A light check, not a full email spec — good enough for a hackathon demo."""
        if "@" not in value or " " in value or len(value) < 5:
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("password")
    @classmethod
    def password_long_enough(cls, value: str) -> str:
        """Require a minimal password length. bcrypt itself caps the maximum length."""
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return value

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        """Reject an empty or whitespace-only name."""
        if not value.strip():
            raise ValueError("Enter a name.")
        return value


class LoginRequest(BaseModel):
    """Body of POST /api/auth/login."""

    email: str
    password: str


# ---------------------------------------------------------------------------
# Profiles (Step 4)
# ---------------------------------------------------------------------------

_DAY_KEYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # 24-hour "HH:MM", e.g. "09:00"


def _validate_weekly_hours(value: dict[str, list[str]]) -> dict[str, list[str]]:
    """Check a weekly-hours dict like {"mon": ["09:00", "17:00"]}.

    Shared by Pantry.opening_hours and Driver.availability, since both use the
    same shape. Raises ValueError (which Pydantic turns into a 422) on anything
    that doesn't make sense, so bad data never reaches the database.
    """
    for day, times in value.items():
        if day not in _DAY_KEYS:
            raise ValueError(f"'{day}' is not a day of the week (use mon/tue/wed/thu/fri/sat/sun).")
        if len(times) != 2:
            raise ValueError(f"'{day}' must have exactly [open_time, close_time].")
        for time_value in times:
            if not _TIME_PATTERN.match(time_value):
                raise ValueError(f"'{time_value}' is not a 24-hour time like '09:00'.")
        if times[0] >= times[1]:
            raise ValueError(f"'{day}': closing time must be after opening time.")
    return value


def _validate_latitude(value: float) -> float:
    """Reject a latitude that couldn't possibly be real (valid range is -90 to 90)."""
    if not -90 <= value <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    return value


def _validate_longitude(value: float) -> float:
    """Reject a longitude that couldn't possibly be real (valid range is -180 to 180)."""
    if not -180 <= value <= 180:
        raise ValueError("Longitude must be between -180 and 180.")
    return value


def _not_blank(value: str) -> str:
    """Reject empty or whitespace-only text."""
    if not value.strip():
        raise ValueError("This field can't be empty.")
    return value


class RestaurantProfileOut(BaseModel):
    """A restaurant's profile, sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)  # lets us build this straight from a Restaurant row

    name: str
    address: str
    lat: float
    lon: float
    phone: str


class RestaurantProfileIn(BaseModel):
    """Body of PUT /api/restaurant/profile."""

    name: str
    address: str
    lat: float
    lon: float
    phone: str = ""

    _check_name = field_validator("name")(_not_blank)
    _check_address = field_validator("address")(_not_blank)
    _check_lat = field_validator("lat")(_validate_latitude)
    _check_lon = field_validator("lon")(_validate_longitude)


class PantryProfileOut(BaseModel):
    """A pantry's profile, sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    address: str
    lat: float
    lon: float
    phone: str
    capacity_kg_per_day: float
    has_fridge: bool
    has_freezer: bool
    dietary_restrictions: list[str]
    opening_hours: dict[str, list[str]]
    accepting_donations: bool
    notes: str


class PantryProfileIn(BaseModel):
    """Body of PUT /api/pantry/profile."""

    name: str
    address: str
    lat: float
    lon: float
    phone: str = ""
    capacity_kg_per_day: float
    has_fridge: bool = False
    has_freezer: bool = False
    dietary_restrictions: list[str] = []
    opening_hours: dict[str, list[str]] = {}
    accepting_donations: bool = True
    notes: str = ""

    _check_name = field_validator("name")(_not_blank)
    _check_address = field_validator("address")(_not_blank)
    _check_lat = field_validator("lat")(_validate_latitude)
    _check_lon = field_validator("lon")(_validate_longitude)
    _check_hours = field_validator("opening_hours")(_validate_weekly_hours)

    @field_validator("capacity_kg_per_day")
    @classmethod
    def capacity_must_be_positive(cls, value: float) -> float:
        """A pantry that can't take any food isn't useful to model — require at least a little."""
        if value <= 0:
            raise ValueError("Capacity must be greater than 0 kg/day.")
        return value

    @field_validator("dietary_restrictions")
    @classmethod
    def tags_must_be_known(cls, value: list[str]) -> list[str]:
        """Only allow the tags defined in pantrypilot/models/places.py, so the agent
        always sees a recognized set of restrictions."""
        unknown = [tag for tag in value if tag not in DIETARY_RESTRICTIONS]
        if unknown:
            raise ValueError(f"Unknown dietary restriction(s): {', '.join(unknown)}.")
        return value


class DriverProfileOut(BaseModel):
    """A driver's profile, sent to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    phone: str
    lat: float
    lon: float
    service_radius_km: float
    vehicle: str
    max_kg: float
    has_cooler: bool
    availability: dict[str, list[str]]
    on_duty: bool


class DriverProfileIn(BaseModel):
    """Body of PUT /api/driver/profile."""

    name: str
    phone: str = ""
    lat: float
    lon: float
    service_radius_km: float
    vehicle: str = "car"
    max_kg: float
    has_cooler: bool = False
    availability: dict[str, list[str]] = {}
    on_duty: bool = True

    _check_name = field_validator("name")(_not_blank)
    _check_lat = field_validator("lat")(_validate_latitude)
    _check_lon = field_validator("lon")(_validate_longitude)
    _check_availability = field_validator("availability")(_validate_weekly_hours)

    @field_validator("service_radius_km", "max_kg")
    @classmethod
    def must_be_positive(cls, value: float) -> float:
        """A driver who can carry 0 kg or drive 0 km can't actually do deliveries."""
        if value <= 0:
            raise ValueError("Must be greater than 0.")
        return value


# ---------------------------------------------------------------------------
# Offers (Step 5)
# ---------------------------------------------------------------------------


class OfferCreate(BaseModel):
    """Body of POST /api/restaurant/offers — a restaurant posting surplus food."""

    title: str
    description: str
    quantity_text: str
    allergen_notes: str = ""
    # AwareDatetime requires a timezone offset in the JSON (e.g. a "Z" suffix),
    # so there's never doubt about which time zone a deadline means.
    pickup_deadline: AwareDatetime

    _check_title = field_validator("title")(_not_blank)
    _check_description = field_validator("description")(_not_blank)
    _check_quantity = field_validator("quantity_text")(_not_blank)

    @field_validator("pickup_deadline")
    @classmethod
    def deadline_must_be_in_the_future(cls, value: datetime) -> datetime:
        """A pickup deadline in the past makes no sense for a new offer."""
        if value <= utc_now():
            raise ValueError("Pickup deadline must be in the future.")
        return value


class OfferOut(BaseModel):
    """An offer, sent to the frontend. Used for both the restaurant's own view and admin."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    quantity_text: str
    allergen_notes: str
    pickup_deadline: datetime
    status: str
    agent_summary: str | None
    created_at: datetime
    updated_at: datetime


class OfferAdminOut(OfferOut):
    """An offer as the admin sees it: everything in OfferOut, plus who posted it."""

    restaurant_name: str

    @classmethod
    def from_offer(cls, offer: Offer) -> "OfferAdminOut":
        """Build this from an Offer row, pulling the restaurant's name off the relationship."""
        return cls(**OfferOut.model_validate(offer).model_dump(), restaurant_name=offer.restaurant.name)
