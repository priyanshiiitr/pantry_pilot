"""Tests for the worker's scheduled job (Step 9).

pick_up_new_offers's own logic — which offers it picks, and that one failure
doesn't stop the rest — is tested here by replacing run_case with a stub.
The agents themselves are already tested elsewhere; this only tests the timer's
wiring, never a real model call.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Offer, OfferStatus, Restaurant, Role, User
from pantrypilot.worker import jobs


def make_offer(db_session: Session, email: str, status: str = OfferStatus.POSTED) -> Offer:
    """Create a minimal offer with the given status."""
    user = User(email=email, role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="T",
        description="D",
        quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=1),
        status=status,
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


def test_pick_up_new_offers_runs_the_agent_for_each_posted_offer(
    db_session: Session, monkeypatch
) -> None:
    """Every offer with status=posted gets a run_case call; other statuses are ignored."""
    offer1 = make_offer(db_session, "r1@test.local")
    offer2 = make_offer(db_session, "r2@test.local")
    make_offer(db_session, "r3@test.local", status=OfferStatus.DELIVERED)

    calls: list[int] = []
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger: calls.append(offer_id))

    jobs.pick_up_new_offers()

    assert set(calls) == {offer1.id, offer2.id}


def test_pick_up_new_offers_continues_after_one_failure(db_session: Session, monkeypatch) -> None:
    """If one offer's agent run raises, the others still get processed."""
    offer1 = make_offer(db_session, "r1@test.local")
    offer2 = make_offer(db_session, "r2@test.local")

    calls: list[int] = []

    def fake_run_case(offer_id: int, trigger: str) -> None:
        calls.append(offer_id)
        if offer_id == offer1.id:
            raise RuntimeError("simulated failure")

    monkeypatch.setattr(jobs, "run_case", fake_run_case)

    jobs.pick_up_new_offers()  # must not raise, despite offer1 failing

    assert set(calls) == {offer1.id, offer2.id}


def test_pick_up_new_offers_does_nothing_when_none_posted(db_session: Session, monkeypatch) -> None:
    """An empty queue is a no-op, not an error."""
    calls: list[int] = []
    monkeypatch.setattr(jobs, "run_case", lambda offer_id, trigger: calls.append(offer_id))

    jobs.pick_up_new_offers()

    assert calls == []
