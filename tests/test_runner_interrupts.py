"""Tests for the interrupt-handling logic in agents/runner.py (Step 11).

These never call a real AI model — _handle_agent_result only reads whatever
agent() already returned, so we hand it a fake result object (a plain
SimpleNamespace shaped like a real Strands AgentResult) and check what gets
written to the database. run_case/resume_case's own model-calling code is
verified live separately (see PLAN.md).
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session
from strands.interrupt import Interrupt

from pantrypilot.agents.runner import _handle_agent_result, resume_case
from pantrypilot.agents.schemas import CaseUpdate
from pantrypilot.database import utc_now
from pantrypilot.models import AgentLog, AgentRun, Decision, DecisionStatus, Offer, OfferStatus, Restaurant, Role, User
from pantrypilot.services.activity_log import start_agent_run
from pantrypilot.services.decisions import answer_decision, create_decision


def make_offer(db_session: Session) -> Offer:
    """Create a minimal posted offer with its restaurant."""
    user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2),
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


SAMPLE_CARD = {
    "title": "No pantry can take this before it spoils",
    "situation": "Deadline is in 20 minutes.",
    "reasoning": "No candidate can arrive in time.",
    "options": [{"label": "Extend the deadline", "consequence": "Restaurant must agree."}],
    "recommended_option": "Extend the deadline.",
    "urgency": "high",
}


def make_interrupted_result() -> SimpleNamespace:
    """A fake AgentResult shaped like what agent() returns when ask_admin pauses it."""
    return SimpleNamespace(
        stop_reason="interrupt",
        interrupts=[Interrupt(id="int-abc123", name="ask_admin_offer_1", reason=SAMPLE_CARD)],
        structured_output=None,
    )


def make_finished_result() -> SimpleNamespace:
    """A fake AgentResult shaped like what agent() returns when the Coordinator finishes normally."""
    return SimpleNamespace(
        stop_reason="end_turn",
        interrupts=None,
        structured_output=CaseUpdate(
            status="driver_requested", summary="Matched with Hope Pantry.", reasoning="It was the best fit."
        ),
    )


def test_handle_agent_result_on_interrupt_creates_a_pending_decision(db_session: Session) -> None:
    """An interrupted result saves a Decision with exactly the agent's card."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    update = _handle_agent_result(make_interrupted_result(), run_id, offer.id)

    assert update is None
    decision = db_session.query(Decision).filter_by(offer_id=offer.id).one()
    assert decision.status == DecisionStatus.PENDING
    assert decision.interrupt_id == "int-abc123"
    assert decision.card["title"] == SAMPLE_CARD["title"]


def test_handle_agent_result_on_interrupt_flags_offer_needs_human(db_session: Session) -> None:
    """The offer's status turns needs_human, visible in every dashboard immediately."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    _handle_agent_result(make_interrupted_result(), run_id, offer.id)

    db_session.refresh(offer)
    assert offer.status == OfferStatus.NEEDS_HUMAN
    assert "spoils" in offer.agent_summary


def test_handle_agent_result_on_interrupt_finishes_the_run_as_interrupted(db_session: Session) -> None:
    """The agent_runs row records that this run paused, not crashed or completed."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    _handle_agent_result(make_interrupted_result(), run_id, offer.id)

    run = db_session.get(AgentRun, run_id)
    assert run.stop_reason == "interrupt"
    assert run.finished_at is not None


def test_handle_agent_result_on_interrupt_logs_the_event(db_session: Session) -> None:
    """An "interrupt" row appears in the activity timeline with the card's title."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    _handle_agent_result(make_interrupted_result(), run_id, offer.id)

    entry = db_session.query(AgentLog).filter_by(run_id=run_id, event_type="interrupt").one()
    assert entry.summary == SAMPLE_CARD["title"]


def test_handle_agent_result_on_finish_saves_summary_and_returns_update(db_session: Session) -> None:
    """A normal finish saves the summary on the offer and returns the CaseUpdate."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    update = _handle_agent_result(make_finished_result(), run_id, offer.id)

    assert update.status == "driver_requested"
    db_session.refresh(offer)
    assert offer.agent_summary == "Matched with Hope Pantry."


def test_handle_agent_result_on_finish_leaves_offer_status_alone(db_session: Session) -> None:
    """Unlike an interrupt, a normal finish doesn't touch offer.status itself —
    that's the action tools' job (assign_delivery, send_dispatch_request, etc.)."""
    offer = make_offer(db_session)
    run_id = start_agent_run(trigger="manual", offer_id=offer.id)

    _handle_agent_result(make_finished_result(), run_id, offer.id)

    db_session.refresh(offer)
    assert offer.status == OfferStatus.POSTED  # unchanged by _handle_agent_result itself


def test_resume_case_rejects_a_decision_that_is_not_answered(db_session: Session) -> None:
    """resume_case refuses to act on a decision nobody has answered yet."""
    offer = make_offer(db_session)
    decision = create_decision(db_session, offer.id, "int-1", "ask_admin_offer_1", SAMPLE_CARD)

    with pytest.raises(ValueError, match="not 'answered'"):
        resume_case(decision.id)


def test_resume_case_rejects_an_already_resumed_decision(db_session: Session) -> None:
    """resume_case refuses to double-resume a decision that already went through."""
    offer = make_offer(db_session)
    admin = User(email="admin@test.local", role=Role.ADMIN, display_name="Admin", password_hash="x")
    db_session.add(admin)
    db_session.commit()
    decision = create_decision(db_session, offer.id, "int-1", "ask_admin_offer_1", SAMPLE_CARD)
    answer_decision(db_session, decision, "Extend the deadline", None, admin.id)
    decision.status = DecisionStatus.RESUMED
    db_session.commit()

    with pytest.raises(ValueError, match="not 'answered'"):
        resume_case(decision.id)
