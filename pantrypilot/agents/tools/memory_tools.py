"""Reading long-term facts the agents (or an admin) have recorded before.

Only reading is wired up in Step 6 — `remember_fact` (writing a new fact) arrives
as an action tool once the Coordinator exists in Step 8, and gets a real UI in
Step 13. The agent_memory table already exists (see models/agent_records.py), so
there's nothing stopping recall from working today, even while it's always empty.
"""

from sqlalchemy import select
from strands import tool

from pantrypilot.database import SessionLocal
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
    with SessionLocal() as session:
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
