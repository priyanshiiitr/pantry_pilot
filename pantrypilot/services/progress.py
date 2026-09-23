"""The five stages one offer moves through, for the progress tracker in the UI.

DETERMINISTIC CODE: no AI. Every stage is *derived* from rows that already exist
— Intake's saved analysis, the Delivery row, the DispatchRequest, the pickup and
delivery timestamps. Nothing here tracks progress separately.

That matters: a second source of truth would let the tracker drift from reality,
showing "dispatched" for an offer whose driver request was never sent. It also
keeps the Coordinator free to work in whatever order it decides (see
docs/architecture.md) — this reads what actually happened rather than dictating
what should happen next.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.models import (
    Decision,
    DecisionStatus,
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    DispatchStatus,
    Offer,
    OfferStatus,
    PantryResponse,
)

# Stage states the UI renders differently.
DONE = "done"  # finished
ACTIVE = "active"  # being worked on right now
BLOCKED = "blocked"  # paused, waiting on a human
WAITING = "waiting"  # not started yet


def _first_delivery(session: Session, offer_id: int) -> Delivery | None:
    """The live delivery plan for this offer, if the agents have committed to one.

    Ignores cancelled plans: after a pantry declines and the agents re-plan, the
    abandoned row shouldn't keep the tracker showing a pantry that said no.
    """
    query = (
        select(Delivery)
        .where(Delivery.offer_id == offer_id, Delivery.status != DeliveryStatus.CANCELLED)
        .order_by(Delivery.id.desc())
    )
    return session.scalars(query).first()


def get_offer_progress(session: Session, offer_id: int) -> list[dict[str, Any]]:
    """Return the five stages for one offer, in order, each with a state and a detail line.

    Raises LookupError if the offer doesn't exist.
    """
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise LookupError(f"No offer with id {offer_id}.")

    delivery = _first_delivery(session, offer_id)
    accepted_request = None
    if delivery is not None:
        accepted_request = session.scalars(
            select(DispatchRequest)
            .where(
                DispatchRequest.delivery_id == delivery.id,
                DispatchRequest.status.in_([DispatchStatus.REQUESTED, DispatchStatus.ACCEPTED]),
            )
            .order_by(DispatchRequest.id.desc())
        ).first()

    blocked_here = session.scalars(
        select(Decision).where(Decision.offer_id == offer_id, Decision.status == DecisionStatus.PENDING)
    ).first()

    stages: list[dict[str, Any]] = []

    # 1. Understood — Intake has saved its breakdown (agents/intake_agent.py).
    details = offer.structured_details
    stages.append(
        {
            "key": "understood",
            "name": "Understood",
            "state": DONE if details else (ACTIVE if offer.status == OfferStatus.AGENT_WORKING else WAITING),
            "detail": (
                f"{details['estimated_kg']} kg, {details['estimated_meals']} meals"
                if details
                else "Reading what the restaurant wrote"
            ),
        }
    )

    # 2. Matched — a pantry has been chosen.
    stages.append(
        {
            "key": "matched",
            "name": "Pantry matched",
            "state": DONE if delivery else (ACTIVE if details else WAITING),
            "detail": delivery.pantry.name if delivery else "Comparing nearby pantries",
        }
    )

    # 3. Driver — asked, and whether they've said yes yet.
    if accepted_request is not None and accepted_request.status == DispatchStatus.ACCEPTED:
        driver_state, driver_detail = DONE, f"{accepted_request.driver.name} accepted"
    elif accepted_request is not None:
        driver_state, driver_detail = ACTIVE, f"Waiting for {accepted_request.driver.name} to respond"
    else:
        driver_state, driver_detail = (ACTIVE if delivery else WAITING), "Finding a driver who can make it in time"
    stages.append({"key": "driver", "name": "Driver assigned", "state": driver_state, "detail": driver_detail})

    # 4 and 5. The physical trip — the only stages no agent can complete.
    picked_up = delivery is not None and delivery.picked_up_at is not None
    delivered = delivery is not None and delivery.delivered_at is not None
    stages.append(
        {
            "key": "picked_up",
            "name": "Picked up",
            "state": DONE if picked_up else (ACTIVE if driver_state == DONE else WAITING),
            "detail": "Collected from the restaurant" if picked_up else "Driver heading to the restaurant",
        }
    )
    stages.append(
        {
            "key": "delivered",
            "name": "Delivered",
            "state": DONE if delivered else (ACTIVE if picked_up else WAITING),
            "detail": (
                f"Delivered to {delivery.pantry.name}"
                if delivered and delivery
                else "On the way to the pantry"
            ),
        }
    )

    _backfill_earlier_stages(stages)

    # A pantry that declined leaves the match stage genuinely un-done. Applied
    # after the backfill so this deliberate re-opening isn't filled straight in.
    if delivery is not None and delivery.pantry_response == PantryResponse.DECLINED:
        stages[1]["state"] = ACTIVE
        stages[1]["detail"] = f"{delivery.pantry.name} declined — looking for another pantry"

    # An escalation blocks wherever the agents got to, rather than adding a
    # stage of its own — the work didn't move on, it stopped.
    if blocked_here is not None:
        _mark_blocked(stages, blocked_here.card.get("title", "Waiting for a human decision"))

    return stages


def _backfill_earlier_stages(stages: list[dict[str, Any]]) -> None:
    """Mark everything before the furthest finished stage as finished too.

    You cannot deliver food you never matched, so a tracker showing "Delivered ✓"
    above "Understood ○" is just wrong on its face. It happens whenever a stage's
    own evidence is missing — an offer handled before Intake started saving its
    analysis, say — and the later rows are the stronger proof.
    """
    finished = [index for index, stage in enumerate(stages) if stage["state"] == DONE]
    if not finished:
        return
    for stage in stages[: max(finished)]:
        stage["state"] = DONE


def _mark_blocked(stages: list[dict[str, Any]], title: str) -> None:
    """Show the escalation on the stage the agents actually stopped at.

    Usually that's the stage in progress. When nothing is in progress — the agents
    escalated before finishing anything — it's the first unfinished stage, so the
    card is never silently invisible.
    """
    target = next((stage for stage in stages if stage["state"] == ACTIVE), None)
    if target is None:
        target = next((stage for stage in stages if stage["state"] != DONE), None)
    if target is not None:
        target["state"] = BLOCKED
        target["detail"] = title
