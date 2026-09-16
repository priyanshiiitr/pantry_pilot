"""Tests for the worker's scheduled jobs (Steps 9-11).

pick_up_new_offers, expire_stale_dispatch_requests and resume_answered_decisions'
own logic — which rows they pick, what context they build, that one failure
doesn't stop the rest — is tested here by replacing run_case/resume_case with a
stub. The agents themselves are already tested elsewhere; this only tests the
timer's wiring, never a real model call.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Delivery,
    DeliveryStatus,
    Driver,
    DispatchRequest,
    DispatchStatus,
    Offer,
    OfferStatus,
    Pantry,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.decisions import answer_decision, create_decision
from pantrypilot.worker import jobs


def make_offer(db_session: Session, email: str, status: str = OfferStatus.POSTED, agent_summary: str | None = None) -> Offer:
    """Create a minimal offer with the given status and optional prior summary."""
    user = User(email=email, role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=1),
        status=status,
        agent_summary=agent_summary,
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


def test_pick_up_new_offers_runs_the_agent_for_each_posted_offer(db_session: Session, monkeypatch) -> None:
    """Every offer with status=posted gets a run_case call; other statuses are ignored."""
    offer1 = make_offer(db_session, "r1@test.local")
    offer2 = make_offer(db_session, "r2@test.local")
    make_offer(db_session, "r3@test.local", status=OfferStatus.DELIVERED)

    calls: list[int] = []
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger, context_message: calls.append(offer_id))

    jobs.pick_up_new_offers()

    assert set(calls) == {offer1.id, offer2.id}


def test_pick_up_new_offers_sends_no_context_for_a_genuinely_new_offer(db_session: Session, monkeypatch) -> None:
    """A freshly-posted offer (no prior agent_summary) gets a plain None context_message."""
    offer = make_offer(db_session, "r1@test.local")

    seen: dict[int, str | None] = {}
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger, context_message: seen.__setitem__(offer_id, context_message))

    jobs.pick_up_new_offers()

    assert seen[offer.id] is None


def test_pick_up_new_offers_builds_context_from_a_requeue_note(db_session: Session, monkeypatch) -> None:
    """An offer requeued after a decline carries its note into the new run's context."""
    offer = make_offer(db_session, "r1@test.local", agent_summary="Driver Sam declined the pickup: car trouble.")

    seen: dict[int, str | None] = {}
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger, context_message: seen.__setitem__(offer_id, context_message))

    jobs.pick_up_new_offers()

    assert "Driver Sam declined" in seen[offer.id]
    assert "another solution" in seen[offer.id]


def test_pick_up_new_offers_continues_after_one_failure(db_session: Session, monkeypatch) -> None:
    """If one offer's agent run raises, the others still get processed."""
    offer1 = make_offer(db_session, "r1@test.local")
    offer2 = make_offer(db_session, "r2@test.local")

    calls: list[int] = []

    def fake_run_case(offer_id: int, trigger: str, context_message: str | None) -> None:
        calls.append(offer_id)
        if offer_id == offer1.id:
            raise RuntimeError("simulated failure")

    monkeypatch.setattr(jobs, "run_case", fake_run_case)

    jobs.pick_up_new_offers()  # must not raise, despite offer1 failing

    assert set(calls) == {offer1.id, offer2.id}


@pytest.mark.usefixtures("db_session")  # activates the temp-database swap; the test itself needs no session
def test_pick_up_new_offers_does_nothing_when_none_posted(monkeypatch) -> None:
    """An empty queue is a no-op, not an error."""
    calls: list[int] = []
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger, context_message: calls.append(offer_id))

    jobs.pick_up_new_offers()

    assert calls == []


def make_requested_dispatch(db_session: Session, expires_at) -> DispatchRequest:
    """Create a full offer -> pantry -> delivery -> dispatch_request chain, REQUESTED, expiring at `expires_at`."""
    r_user = User(email=f"r{expires_at}@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=r_user, name="R", address="x", lat=47.6, lon=-122.3)
    p_user = User(email=f"p{expires_at}@test.local", role=Role.PANTRY, display_name="P", password_hash="x")
    pantry = Pantry(user=p_user, name="P", address="x", lat=47.6, lon=-122.3)
    d_user = User(email=f"d{expires_at}@test.local", role=Role.DRIVER, display_name="D", password_hash="x")
    driver = Driver(user=d_user, name="D", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2),
        status=OfferStatus.DRIVER_REQUESTED,
    )
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.DRIVER_REQUESTED)
    request = DispatchRequest(delivery=delivery, driver=driver, status=DispatchStatus.REQUESTED, expires_at=expires_at)
    db_session.add_all([r_user, restaurant, p_user, pantry, d_user, driver, offer, delivery, request])
    db_session.commit()
    return request


def test_expire_stale_dispatch_requests_expires_only_overdue_ones(db_session: Session) -> None:
    """A request past its expires_at gets marked expired; one still within its window is untouched."""
    overdue = make_requested_dispatch(db_session, utc_now() - timedelta(minutes=1))
    fresh = make_requested_dispatch(db_session, utc_now() + timedelta(minutes=10))

    jobs.expire_stale_dispatch_requests()

    db_session.refresh(overdue)
    db_session.refresh(fresh)
    assert overdue.status == DispatchStatus.EXPIRED
    assert fresh.status == DispatchStatus.REQUESTED


def test_expire_stale_dispatch_requests_requeues_the_offer(db_session: Session) -> None:
    """Expiring a request puts its offer back in the queue for another driver."""
    request = make_requested_dispatch(db_session, utc_now() - timedelta(minutes=1))

    jobs.expire_stale_dispatch_requests()

    db_session.expire_all()  # the job used a separate session; force a fresh read
    offer = request.delivery.offer
    assert offer.status == OfferStatus.POSTED
    assert "did not respond" in offer.agent_summary


def test_expire_stale_dispatch_requests_does_nothing_when_none_overdue(db_session: Session) -> None:
    """No overdue requests is a no-op, not an error."""
    fresh = make_requested_dispatch(db_session, utc_now() + timedelta(minutes=10))

    jobs.expire_stale_dispatch_requests()  # must not raise

    db_session.refresh(fresh)
    assert fresh.status == DispatchStatus.REQUESTED


SAMPLE_CARD = {
    "title": "No pantry can take this before it spoils",
    "situation": "Deadline is in 20 minutes.",
    "reasoning": "No candidate can arrive in time.",
    "options": [{"label": "Extend the deadline", "consequence": "Restaurant must agree."}],
    "recommended_option": "Extend the deadline.",
    "urgency": "high",
}


def make_answered_decision(db_session: Session, email: str) -> int:
    """Create a minimal offer with one answered decision, and return the decision's id."""
    offer = make_offer(db_session, email)
    admin = User(email=f"admin-{email}", role=Role.ADMIN, display_name="Admin", password_hash="x")
    db_session.add(admin)
    db_session.commit()
    decision = create_decision(db_session, offer.id, f"int-{email}", f"ask_admin_offer_{offer.id}", SAMPLE_CARD)
    answer_decision(db_session, decision, "Extend the deadline", None, admin.id)
    return decision.id


def test_resume_answered_decisions_resumes_each_one(db_session: Session, monkeypatch) -> None:
    """Every answered decision gets a resume_case call."""
    decision1_id = make_answered_decision(db_session, "r1@test.local")
    decision2_id = make_answered_decision(db_session, "r2@test.local")

    calls: list[int] = []
    monkeypatch.setattr(jobs, "resume_case", lambda decision_id: calls.append(decision_id))

    jobs.resume_answered_decisions()

    assert set(calls) == {decision1_id, decision2_id}


def test_resume_answered_decisions_continues_after_one_failure(db_session: Session, monkeypatch) -> None:
    """If resuming one decision raises, the others still get processed."""
    decision1_id = make_answered_decision(db_session, "r1@test.local")
    decision2_id = make_answered_decision(db_session, "r2@test.local")

    calls: list[int] = []

    def fake_resume_case(decision_id: int) -> None:
        calls.append(decision_id)
        if decision_id == decision1_id:
            raise RuntimeError("simulated failure")

    monkeypatch.setattr(jobs, "resume_case", fake_resume_case)

    jobs.resume_answered_decisions()  # must not raise, despite decision1 failing

    assert set(calls) == {decision1_id, decision2_id}


@pytest.mark.usefixtures("db_session")
def test_resume_answered_decisions_does_nothing_when_none_answered(monkeypatch) -> None:
    """No answered decisions is a no-op, not an error."""
    calls: list[int] = []
    monkeypatch.setattr(jobs, "resume_case", lambda decision_id: calls.append(decision_id))

    jobs.resume_answered_decisions()

    assert calls == []
