"""Tables for the food itself and its journey:
Offer (what a restaurant posted) → Delivery (the planned trip) → DispatchRequest (asking a driver).
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pantrypilot.database import Base, UtcDateTime, utc_now

if TYPE_CHECKING:
    from pantrypilot.models.agent_records import Decision
    from pantrypilot.models.places import Driver, Pantry, Restaurant


class OfferStatus(StrEnum):
    """Where an offer is in its life. Shown as a coloured badge in the UI."""

    POSTED = "posted"  # just created, waiting for the agent worker to pick it up
    AGENT_WORKING = "agent_working"  # an agent run is reasoning about it right now
    NEEDS_HUMAN = "needs_human"  # paused: waiting in the admin Decisions inbox
    DRIVER_REQUESTED = "driver_requested"  # pantry chosen, waiting for a driver to accept
    DRIVER_ASSIGNED = "driver_assigned"  # a driver accepted
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    EXPIRED = "expired"  # nobody could take it in time
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    """Status of one planned trip. An offer can have several if the agent re-plans."""

    PLANNED = "planned"
    DRIVER_REQUESTED = "driver_requested"
    DRIVER_ASSIGNED = "driver_assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PantryResponse(StrEnum):
    """Whether the receiving pantry has confirmed the delivery."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class DispatchStatus(StrEnum):
    """Status of one request sent to one driver."""

    REQUESTED = "requested"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"  # driver didn't answer in time
    CANCELLED = "cancelled"  # agent withdrew the request (e.g. it re-planned)


class Offer(Base):
    """Surplus food posted by a restaurant.

    `description`, `quantity_text` and `allergen_notes` are exactly what the restaurant
    typed. `structured_details` is filled in later by the Intake agent (clean data).
    """

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    quantity_text: Mapped[str] = mapped_column(String(120))
    allergen_notes: Mapped[str] = mapped_column(Text, default="")
    pickup_deadline: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(30), default=OfferStatus.POSTED, index=True)
    structured_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    agent_summary: Mapped[str | None] = mapped_column(Text, default=None)  # latest plain-English update
    claimed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)  # when the worker took it
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="offers")
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="offer")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="offer")


class Delivery(Base):
    """One planned trip: this offer → this pantry, (eventually) with this driver.

    The two reasoning fields hold the agents' written explanations shown in the UI.
    """

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    pantry_id: Mapped[int] = mapped_column(ForeignKey("pantries.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), default=None, index=True)
    status: Mapped[str] = mapped_column(String(30), default=DeliveryStatus.PLANNED)
    pantry_response: Mapped[str] = mapped_column(String(20), default=PantryResponse.PENDING)
    pantry_decline_reason: Mapped[str | None] = mapped_column(Text, default=None)
    kg: Mapped[float] = mapped_column(default=0.0)
    meals: Mapped[int] = mapped_column(default=0)
    match_reasoning: Mapped[str] = mapped_column(Text, default="")
    dispatch_reasoning: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    picked_up_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    offer: Mapped["Offer"] = relationship(back_populates="deliveries")
    pantry: Mapped["Pantry"] = relationship(back_populates="deliveries")
    driver: Mapped["Driver | None"] = relationship(back_populates="deliveries")
    dispatch_requests: Mapped[list["DispatchRequest"]] = relationship(back_populates="delivery")


class DispatchRequest(Base):
    """One ask to one driver: "can you do this trip?". Keeps full history,
    which lets the agent notice patterns like "Sam always declines evening runs"."""

    __tablename__ = "dispatch_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DispatchStatus.REQUESTED)
    decline_reason: Mapped[str | None] = mapped_column(Text, default=None)
    sent_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    responded_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    delivery: Mapped["Delivery"] = relationship(back_populates="dispatch_requests")
    driver: Mapped["Driver"] = relationship(back_populates="dispatch_requests")
