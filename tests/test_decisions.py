"""Tests for services/decisions.py (Step 11): saving a paused agent's question
and recording the admin's answer.

No AI involved — these are the functions that store what the agent asked (via
its ask_admin interrupt) and what the admin decided.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import DecisionStatus, Offer, Restaurant, Role, User
from pantrypilot.services.decisions import (
    answer_decision,
    create_decision,
    get_decision,
    list_answered_decisions,
    list_pending_decisions,
    mark_decision_failed,
    mark_decision_resumed,
)


def make_offer(db_session: Session) -> Offer:
    """Create a minimal offer with its restaurant."""
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


def make_admin(db_session: Session, email: str = "admin@test.local") -> User:
    """Create a minimal admin user, to satisfy answer_decision's foreign key."""
    admin = User(email=email, role=Role.ADMIN, display_name="Admin", password_hash="x")
    db_session.add(admin)
    db_session.commit()
    return admin


SAMPLE_CARD = {
    "title": "No pantry can take this before it spoils",
    "situation": "Deadline is in 20 minutes; nearest open pantry is 30 minutes away.",
    "reasoning": "No candidate can arrive before the deadline.",
    "options": [
        {"label": "Extend the deadline", "consequence": "Restaurant must agree to hold the food longer."},
        {"label": "Cancel the offer", "consequence": "Food goes to waste."},
    ],
    "recommended_option": "Extend the deadline — the food is still safe for another hour.",
    "urgency": "high",
}


def test_create_decision_saves_the_card(db_session: Session) -> None:
    """create_decision saves exactly the card the agent produced."""
    offer = make_offer(db_session)

    decision = create_decision(db_session, offer.id, "interrupt-abc", "ask_admin_offer_1", SAMPLE_CARD)

    assert decision.status == DecisionStatus.PENDING
    assert decision.interrupt_id == "interrupt-abc"
    assert decision.card["title"] == SAMPLE_CARD["title"]
    assert len(decision.card["options"]) == 2


def test_list_pending_decisions_only_returns_pending(db_session: Session) -> None:
    """Answered/resumed decisions don't show up in the pending list."""
    offer = make_offer(db_session)
    admin = make_admin(db_session)
    pending = create_decision(db_session, offer.id, "i1", "n1", SAMPLE_CARD)
    answered = create_decision(db_session, offer.id, "i2", "n2", SAMPLE_CARD)
    answer_decision(db_session, answered, "Cancel the offer", None, answered_by_user_id=admin.id)

    result = list_pending_decisions(db_session)

    assert [d.id for d in result] == [pending.id]


def test_get_decision_raises_for_missing_id(db_session: Session) -> None:
    """A bad decision id raises LookupError, not a crash."""
    with pytest.raises(LookupError):
        get_decision(db_session, 999999)


def test_answer_decision_records_choice_and_timestamps(db_session: Session) -> None:
    """Answering saves the chosen option, note, who answered, and when."""
    offer = make_offer(db_session)
    admin = make_admin(db_session)
    decision = create_decision(db_session, offer.id, "i1", "n1", SAMPLE_CARD)

    answer_decision(db_session, decision, "Extend the deadline", "Called the restaurant, they agreed.", admin.id)

    assert decision.status == DecisionStatus.ANSWERED
    assert decision.chosen_option == "Extend the deadline"
    assert decision.admin_note == "Called the restaurant, they agreed."
    assert decision.answered_by_user_id == admin.id
    assert decision.answered_at is not None


def test_list_answered_decisions_only_returns_answered(db_session: Session) -> None:
    """Pending and resumed decisions don't show up in the answered queue."""
    offer = make_offer(db_session)
    admin = make_admin(db_session)
    pending = create_decision(db_session, offer.id, "i1", "n1", SAMPLE_CARD)
    answered = create_decision(db_session, offer.id, "i2", "n2", SAMPLE_CARD)
    resumed = create_decision(db_session, offer.id, "i3", "n3", SAMPLE_CARD)
    answer_decision(db_session, answered, "Cancel the offer", None, answered_by_user_id=admin.id)
    answer_decision(db_session, resumed, "Cancel the offer", None, answered_by_user_id=admin.id)
    mark_decision_resumed(db_session, resumed)

    result = list_answered_decisions(db_session)

    assert [d.id for d in result] == [answered.id]
    assert pending.id not in [d.id for d in result]


def test_mark_decision_resumed_sets_status_and_timestamp(db_session: Session) -> None:
    """Marking resumed records when the agent successfully picked back up."""
    offer = make_offer(db_session)
    admin = make_admin(db_session)
    decision = create_decision(db_session, offer.id, "i1", "n1", SAMPLE_CARD)
    answer_decision(db_session, decision, "Cancel the offer", None, answered_by_user_id=admin.id)

    mark_decision_resumed(db_session, decision)

    assert decision.status == DecisionStatus.RESUMED
    assert decision.resumed_at is not None


def test_mark_decision_failed_sets_status(db_session: Session) -> None:
    """Marking failed keeps the decision visible instead of vanishing silently."""
    offer = make_offer(db_session)
    admin = make_admin(db_session)
    decision = create_decision(db_session, offer.id, "i1", "n1", SAMPLE_CARD)
    answer_decision(db_session, decision, "Cancel the offer", None, answered_by_user_id=admin.id)

    mark_decision_failed(db_session, decision)

    assert decision.status == DecisionStatus.FAILED
