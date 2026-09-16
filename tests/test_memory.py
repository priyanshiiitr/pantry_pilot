"""Tests for services/memory.py (Step 13): listing and removing remembered facts.

No AI involved — deciding what's worth remembering is the remember_fact tool's
job (agents/tools/memory_tools.py, tested live in earlier steps); this only
tests reading the list back and deactivating one.
"""

import pytest
from sqlalchemy.orm import Session

from pantrypilot.models import AgentMemory, Pantry, Role, User
from pantrypilot.services.memory import deactivate_fact, get_subject_name, list_active_facts


def make_pantry(db_session: Session, email: str = "p@test.local") -> Pantry:
    """Create a minimal pantry."""
    user = User(email=email, role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=user, name="Riverside Food Bank", address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def test_list_active_facts_excludes_deactivated(db_session: Session) -> None:
    """Only is_active=True facts show up."""
    pantry = make_pantry(db_session)
    active = AgentMemory(subject_type="pantry", subject_id=pantry.id, fact="Cannot take pork.", source="agent")
    inactive = AgentMemory(
        subject_type="pantry", subject_id=pantry.id, fact="Old fact.", source="agent", is_active=False
    )
    db_session.add_all([active, inactive])
    db_session.commit()

    facts = list_active_facts(db_session)

    assert [f.id for f in facts] == [active.id]


def test_list_active_facts_orders_newest_first(db_session: Session) -> None:
    """Newest fact comes first."""
    pantry = make_pantry(db_session)
    first = AgentMemory(subject_type="pantry", subject_id=pantry.id, fact="First.", source="agent")
    db_session.add(first)
    db_session.commit()
    second = AgentMemory(subject_type="pantry", subject_id=pantry.id, fact="Second.", source="agent")
    db_session.add(second)
    db_session.commit()

    facts = list_active_facts(db_session)

    assert facts[0].id == second.id


def test_get_subject_name_resolves_a_real_pantry(db_session: Session) -> None:
    """A known subject resolves to its actual name."""
    pantry = make_pantry(db_session)

    name = get_subject_name(db_session, "pantry", pantry.id)

    assert name == "Riverside Food Bank"


def test_get_subject_name_handles_a_deleted_subject(db_session: Session) -> None:
    """A subject id that no longer exists gets a clear placeholder, not a crash."""
    name = get_subject_name(db_session, "pantry", 999999)

    assert "deleted" in name


def test_get_subject_name_handles_an_unknown_subject_type(db_session: Session) -> None:
    """An unrecognized subject_type still returns something readable."""
    name = get_subject_name(db_session, "spaceship", 1)

    assert name == "spaceship #1"


def test_deactivate_fact_hides_it_from_the_active_list(db_session: Session) -> None:
    """Deactivating a fact removes it from list_active_facts without deleting the row."""
    pantry = make_pantry(db_session)
    fact = AgentMemory(subject_type="pantry", subject_id=pantry.id, fact="Temporarily closed.", source="agent")
    db_session.add(fact)
    db_session.commit()

    deactivate_fact(db_session, fact.id)

    assert list_active_facts(db_session) == []
    assert db_session.get(AgentMemory, fact.id) is not None  # row still exists
    assert db_session.get(AgentMemory, fact.id).is_active is False


def test_deactivate_fact_raises_for_missing_id(db_session: Session) -> None:
    """A bad fact id raises LookupError, not a crash."""
    with pytest.raises(LookupError):
        deactivate_fact(db_session, 999999)
