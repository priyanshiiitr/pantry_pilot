"""Tests for agents/tools/memory_tools.py: recall_facts, remember_fact.

These call the @tool-decorated functions directly (they remain plain
callables), bypassing any LLM.
"""

from sqlalchemy.orm import Session

from pantrypilot.agents.tools.memory_tools import recall_facts, remember_fact
from pantrypilot.models import AgentMemory


def test_remember_fact_saves_a_row(db_session: Session) -> None:
    """remember_fact creates a row the agent can recall later."""
    result = remember_fact(
        subject_type="pantry", subject_id=1, fact="Cannot take pork.", reason="Owner mentioned it on a call."
    )

    assert result["saved"] is True
    saved = db_session.query(AgentMemory).one()
    assert saved.fact == "Cannot take pork."
    assert saved.subject_type == "pantry"
    assert saved.subject_id == 1
    assert saved.source == "agent"


def test_recall_facts_returns_what_was_remembered(db_session: Session) -> None:
    """A fact saved via remember_fact is readable back via recall_facts."""
    remember_fact(subject_type="driver", subject_id=5, fact="Declines evening runs.", reason="Pattern noticed.")

    facts = recall_facts(subject_type="driver", subject_id=5)

    assert len(facts) == 1
    assert facts[0]["fact"] == "Declines evening runs."
    assert facts[0]["source"] == "agent"


def test_recall_facts_only_returns_facts_for_the_right_subject(db_session: Session) -> None:
    """A fact about a different pantry/driver doesn't leak into an unrelated lookup."""
    remember_fact(subject_type="pantry", subject_id=1, fact="Fact about pantry 1.", reason="x")
    remember_fact(subject_type="pantry", subject_id=2, fact="Fact about pantry 2.", reason="x")

    facts = recall_facts(subject_type="pantry", subject_id=1)

    assert len(facts) == 1
    assert facts[0]["fact"] == "Fact about pantry 1."


def test_recall_facts_with_nothing_remembered_is_an_empty_list(db_session: Session) -> None:
    """No facts yet is an empty list, not an error."""
    facts = recall_facts(subject_type="pantry", subject_id=999)

    assert facts == []


def test_recall_facts_excludes_deactivated_facts(db_session: Session) -> None:
    """A fact an admin removed (services/memory.py:deactivate_fact) isn't recalled."""
    remember_fact(subject_type="pantry", subject_id=1, fact="Old fact.", reason="x")
    fact_row = db_session.query(AgentMemory).one()
    fact_row.is_active = False
    db_session.commit()

    facts = recall_facts(subject_type="pantry", subject_id=1)

    assert facts == []
