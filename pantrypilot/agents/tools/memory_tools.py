"""Reading and writing long-term facts the agents (or an admin) have recorded before.

A real "What the agent remembers" admin page, with delete, arrives in Step 13 —
for now, remember_fact just saves a row, and recall_facts reads it back.
"""

from sqlalchemy import select
from strands import tool

from pantrypilot import database
from pantrypilot.models import AgentMemory


@tool
def recall_facts(subject_type: str, subject_id: int) -> list[dict]:
    """Recall remembered facts about a pantry, driver or restaurant.

    For example: "Riverside Food Bank cannot take pork products" or "Driver Sam
    always declines evening runs." Always call this for anyone you're about to
    choose — a remembered fact might change your decision.

    Args:
        subject_type: one of "pantry", "driver", "restaurant".
        subject_id: the id of that pantry/driver/restaurant.
    """
    with database.SessionLocal() as session:
        facts = session.scalars(
            select(AgentMemory).where(
                AgentMemory.subject_type == subject_type,
                AgentMemory.subject_id == subject_id,
                AgentMemory.is_active.is_(True),
            )
        )
        return [
            {"fact": fact.fact, "source": fact.source, "created_at": fact.created_at.isoformat()} for fact in facts
        ]


@tool
def remember_fact(subject_type: str, subject_id: int, fact: str, reason: str) -> dict:
    """Save a fact worth remembering for future offers, e.g. "Riverside Food Bank
    is temporarily closed for renovation" or "Driver Sam declines evening runs."

    Args:
        subject_type: one of "pantry", "driver", "restaurant".
        subject_id: the id of that pantry/driver/restaurant.
        fact: the fact itself, written plainly.
        reason: why you're recording this now (shown alongside the fact later).
    """
    with database.SessionLocal() as session:
        entry = AgentMemory(subject_type=subject_type, subject_id=subject_id, fact=fact, source="agent")
        session.add(entry)
        session.commit()
        return {"id": entry.id, "saved": True, "reason": reason}
