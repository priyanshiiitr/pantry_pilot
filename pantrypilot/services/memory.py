"""Reading and removing the long-term facts the agents have recorded.

DETERMINISTIC CODE: this only lists/deactivates rows. Deciding what's worth
remembering in the first place happens in agents/tools/memory_tools.py's
remember_fact tool — that's the agent's judgment call, not this file's.

We evaluated Strands' built-in MemoryManager/MemoryStore for this instead of
our own AgentMemory table, and chose to keep the simple table: it already
integrates directly with this admin page and the rest of our database, with
no extra moving parts. MemoryManager is worth revisiting if this moved to a
real AgentCore deployment (see docs/aws-deployment.md), where AgentCore Memory
would replace it with the same recall_facts/remember_fact tool interface.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.models import AgentMemory, Driver, Pantry, Restaurant

# Maps a fact's subject_type string to the table it refers to, so we can look up
# a readable name (e.g. "Riverside Food Bank") instead of showing a bare id.
_SUBJECT_MODELS = {"pantry": Pantry, "driver": Driver, "restaurant": Restaurant}


def list_active_facts(session: Session) -> list[AgentMemory]:
    """Return every fact the agents can currently recall, newest first."""
    query = (
        select(AgentMemory)
        .where(AgentMemory.is_active.is_(True))
        .order_by(AgentMemory.created_at.desc(), AgentMemory.id.desc())
    )
    return list(session.scalars(query))


def get_subject_name(session: Session, subject_type: str, subject_id: int) -> str:
    """Look up a fact's subject's display name, e.g. a pantry's name."""
    model = _SUBJECT_MODELS.get(subject_type)
    if model is None:
        return f"{subject_type} #{subject_id}"
    subject = session.get(model, subject_id)
    return subject.name if subject is not None else f"{subject_type} #{subject_id} (deleted)"


def deactivate_fact(session: Session, fact_id: int) -> None:
    """Stop the agents from recalling this fact.

    This is a soft delete (is_active=False, the row stays in the database) so
    there's a history of what was once remembered and why, matching the
    is_active flag recall_facts already filters on.
    """
    fact = session.get(AgentMemory, fact_id)
    if fact is None:
        raise LookupError(f"No fact with id {fact_id}.")
    fact.is_active = False
    session.commit()
