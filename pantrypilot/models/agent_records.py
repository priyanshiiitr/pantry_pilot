"""Tables that record what the AI agents did and what they are waiting for:
Decision (the admin inbox), AgentRun, AgentLog (activity timeline), AgentMemory.

These tables are written by deterministic code (runner, hooks, tools). They store
the agents' reasoning; they don't contain any decision logic themselves.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pantrypilot.database import Base, UtcDateTime, utc_now

if TYPE_CHECKING:
    from pantrypilot.models.offers import Offer


class DecisionKind(StrEnum):
    """Why a human is being asked."""

    AGENT_ESCALATION = "agent_escalation"  # the agent reasoned it couldn't decide responsibly
    APPROVAL_GATE = "approval_gate"  # Supervised mode: admin must approve an action


class DecisionStatus(StrEnum):
    """Life of a decision card."""

    PENDING = "pending"  # waiting for the admin
    ANSWERED = "answered"  # admin chose; worker hasn't resumed the agent yet
    RESUMED = "resumed"  # agent received the answer and carried on
    FAILED = "failed"  # resuming went wrong (details in agent_log)


class RunTrigger(StrEnum):
    """What woke the agents up for a run."""

    NEW_OFFER = "new_offer"
    DRIVER_DECLINED = "driver_declined"
    DRIVER_TIMEOUT = "driver_timeout"
    PANTRY_DECLINED = "pantry_declined"
    ADMIN_DECISION = "admin_decision"
    MANUAL = "manual"  # started by a script while developing


class Decision(Base):
    """A card in the admin Decisions inbox, created when an agent run pauses (interrupt).

    `interrupt_id` is the Strands interrupt id. We need it to resume the paused agent.
    `card` holds the agent-written content: title, situation, reasoning, options.
    """

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    interrupt_id: Mapped[str] = mapped_column(String(120))
    interrupt_name: Mapped[str] = mapped_column(String(120))
    card: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=DecisionStatus.PENDING, index=True)
    chosen_option: Mapped[str | None] = mapped_column(String(120), default=None)
    admin_note: Mapped[str | None] = mapped_column(Text, default=None)
    answered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    resumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    offer: Mapped["Offer"] = relationship(back_populates="decisions")


class AgentRun(Base):
    """One time the agent team woke up to work on an offer."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"), default=None, index=True)
    trigger: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    stop_reason: Mapped[str | None] = mapped_column(String(40), default=None)  # e.g. "end_turn", "interrupt"
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class AgentLog(Base):
    """One line in the readable activity timeline: a tool call, a result, a stated reason…"""

    __tablename__ = "agent_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), default=None, index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"), default=None, index=True)
    agent_name: Mapped[str] = mapped_column(String(40))  # "coordinator", "matching", ...
    event_type: Mapped[str] = mapped_column(String(30))  # "tool_call", "reasoning", "interrupt", ...
    tool_name: Mapped[str | None] = mapped_column(String(80), default=None)
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, index=True)


class AgentMemory(Base):
    """A long-term fact the agents should remember across offers,
    e.g. subject_type="pantry", subject_id=2, fact="Cannot take pork products"."""

    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(20))  # "pantry" | "driver" | "restaurant"
    subject_id: Mapped[int] = mapped_column(index=True)
    fact: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="agent")  # "agent" | "admin"
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
