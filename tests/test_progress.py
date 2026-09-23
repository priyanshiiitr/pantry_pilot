"""Tests for services/progress.py — the five-stage tracker shown on an offer.

The design rule these pin down: every stage is *derived* from rows that already
exist, never tracked separately. A second source of truth could drift and show
"dispatched" for an offer whose driver was never asked.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import (
    Decision,
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    DispatchStatus,
    Driver,
    Offer,
    OfferStatus,
    Pantry,
    PantryResponse,
    Restaurant,
    Role,
    User,
)
from pantrypilot.services.progress import get_offer_progress

SAMPLE_DETAILS = {"estimated_kg": 38.0, "estimated_meals": 50, "perishability": "high"}


def make_offer(db_session: Session, **overrides) -> Offer:
    user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="R", address="x", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant, title="Surplus", description="D", quantity_text="Q",
        pickup_deadline=utc_now() + timedelta(hours=2), **overrides,
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


def make_pantry(db_session: Session, name: str = "Hope") -> Pantry:
    user = User(email=f"{name}@test.local", role=Role.PANTRY, display_name=name, password_hash="x")
    pantry = Pantry(user=user, name=name, address="x", lat=47.6, lon=-122.3)
    db_session.add_all([user, pantry])
    db_session.commit()
    return pantry


def make_driver(db_session: Session, name: str = "Jordan") -> Driver:
    user = User(email=f"{name}@test.local", role=Role.DRIVER, display_name=name, password_hash="x")
    driver = Driver(user=user, name=name, lat=47.6, lon=-122.3)
    db_session.add_all([user, driver])
    db_session.commit()
    return driver


def states(db_session: Session, offer_id: int) -> dict[str, str]:
    return {stage["key"]: stage["state"] for stage in get_offer_progress(db_session, offer_id)}


def test_a_new_offer_shows_the_whole_journey_as_waiting(db_session: Session) -> None:
    """All five stages appear immediately, rather than materialising one at a time."""
    offer = make_offer(db_session)

    stages = get_offer_progress(db_session, offer.id)

    assert [s["key"] for s in stages] == ["understood", "matched", "driver", "picked_up", "delivered"]
    assert all(s["state"] == "waiting" for s in stages)


def test_intakes_saved_analysis_completes_the_first_stage(db_session: Session) -> None:
    """"Understood" is derived from structured_details, not from a flag we set."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)

    stages = get_offer_progress(db_session, offer.id)

    assert stages[0]["state"] == "done"
    assert "38.0 kg" in stages[0]["detail"]
    assert stages[1]["state"] == "active"


def test_a_delivery_row_completes_the_match_stage(db_session: Session) -> None:
    """A committed pantry is what "matched" means — and the pantry is named."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry = make_pantry(db_session)
    db_session.add(Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED))
    db_session.commit()

    stages = get_offer_progress(db_session, offer.id)

    assert stages[1]["state"] == "done"
    assert stages[1]["detail"] == "Hope"
    assert stages[2]["state"] == "active"


def test_an_asked_driver_is_active_until_they_accept(db_session: Session) -> None:
    """Asking isn't the same as agreeing, and the tracker shouldn't pretend it is."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry, driver = make_pantry(db_session), make_driver(db_session)
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.DRIVER_REQUESTED)
    db_session.add(delivery)
    db_session.commit()
    db_session.add(DispatchRequest(delivery=delivery, driver=driver, status=DispatchStatus.REQUESTED))
    db_session.commit()

    stages = get_offer_progress(db_session, offer.id)

    assert stages[2]["state"] == "active"
    assert "Jordan" in stages[2]["detail"]


def test_an_accepted_driver_completes_that_stage(db_session: Session) -> None:
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry, driver = make_pantry(db_session), make_driver(db_session)
    delivery = Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.DRIVER_ASSIGNED)
    db_session.add(delivery)
    db_session.commit()
    db_session.add(DispatchRequest(delivery=delivery, driver=driver, status=DispatchStatus.ACCEPTED))
    db_session.commit()

    assert states(db_session, offer.id)["driver"] == "done"
    assert states(db_session, offer.id)["picked_up"] == "active"


def test_the_trip_stages_follow_the_real_timestamps(db_session: Session) -> None:
    """Picked up and delivered are the two stages no agent can complete."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry, driver = make_pantry(db_session), make_driver(db_session)
    delivery = Delivery(
        offer=offer, pantry=pantry, status=DeliveryStatus.DELIVERED,
        picked_up_at=utc_now(), delivered_at=utc_now(),
    )
    db_session.add(delivery)
    db_session.commit()
    db_session.add(DispatchRequest(delivery=delivery, driver=driver, status=DispatchStatus.ACCEPTED))
    db_session.commit()

    result = states(db_session, offer.id)

    assert result["picked_up"] == "done"
    assert result["delivered"] == "done"


def test_an_escalation_blocks_the_stage_the_agents_reached(db_session: Session) -> None:
    """A pending decision stops the work where it was — it isn't a stage of its own.

    Showing it as a sixth step would imply the offer moved forward. It didn't.
    """
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS, status=OfferStatus.NEEDS_HUMAN)
    db_session.add(
        Decision(
            offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n",
            card={"title": "No pantry can take this in time"},
        )
    )
    db_session.commit()

    stages = get_offer_progress(db_session, offer.id)

    assert stages[1]["state"] == "blocked"
    assert stages[1]["detail"] == "No pantry can take this in time"


def test_a_declined_pantry_reopens_the_match_stage(db_session: Session) -> None:
    """A pantry saying no means the offer genuinely isn't matched any more."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry = make_pantry(db_session)
    db_session.add(
        Delivery(
            offer=offer, pantry=pantry, status=DeliveryStatus.PLANNED,
            pantry_response=PantryResponse.DECLINED,
        )
    )
    db_session.commit()

    stages = get_offer_progress(db_session, offer.id)

    assert stages[1]["state"] == "active"
    assert "declined" in stages[1]["detail"]


def test_a_cancelled_plan_is_ignored(db_session: Session) -> None:
    """After a re-plan, the abandoned delivery shouldn't keep the tracker filled in."""
    offer = make_offer(db_session, structured_details=SAMPLE_DETAILS)
    pantry = make_pantry(db_session)
    db_session.add(Delivery(offer=offer, pantry=pantry, status=DeliveryStatus.CANCELLED))
    db_session.commit()

    assert states(db_session, offer.id)["matched"] == "active"


def test_a_missing_offer_raises(db_session: Session) -> None:
    with pytest.raises(LookupError):
        get_offer_progress(db_session, 999999)


def test_a_finished_stage_implies_the_earlier_ones(db_session: Session) -> None:
    """"Delivered ✓" above "Understood ○" is wrong on its face.

    It happens when a stage's own evidence is missing — an offer handled before
    Intake began saving its analysis, say. The later rows are stronger proof:
    food cannot be delivered without having been understood and matched.
    """
    offer = make_offer(db_session)  # deliberately no structured_details
    pantry = make_pantry(db_session)
    db_session.add(
        Delivery(
            offer=offer, pantry=pantry, status=DeliveryStatus.DELIVERED,
            picked_up_at=utc_now(), delivered_at=utc_now(),
        )
    )
    db_session.commit()

    result = states(db_session, offer.id)

    assert result["understood"] == "done"
    assert result["delivered"] == "done"


def test_an_escalation_before_any_progress_is_still_visible(db_session: Session) -> None:
    """An offer waiting on a human must say so, even if nothing finished first.

    Blocking only the "in progress" stage hid the card entirely when the agents
    escalated before completing anything.
    """
    offer = make_offer(db_session, status=OfferStatus.NEEDS_HUMAN)
    db_session.add(
        Decision(
            offer=offer, kind="ask_admin", interrupt_id="i1", interrupt_name="n",
            card={"title": "The description is too vague to act on"},
        )
    )
    db_session.commit()

    stages = get_offer_progress(db_session, offer.id)

    assert [s["state"] for s in stages].count("blocked") == 1
    assert stages[0]["state"] == "blocked"
    assert stages[0]["detail"] == "The description is too vague to act on"
