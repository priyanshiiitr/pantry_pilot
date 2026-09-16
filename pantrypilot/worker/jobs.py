"""The scheduled jobs themselves — what the worker checks, and how often.

DETERMINISTIC CODE: this decides WHEN to wake the agents up. What they do once
awake is entirely runner.run_case()'s business, not this file's.
"""

import logging

from sqlalchemy import select

from pantrypilot import database
from pantrypilot.agents.runner import resume_case, run_case
from pantrypilot.database import utc_now
from pantrypilot.models import DispatchRequest, DispatchStatus, Offer, OfferStatus, RunTrigger
from pantrypilot.services.decisions import list_answered_decisions
from pantrypilot.services.dispatch import expire_dispatch_request

logger = logging.getLogger(__name__)


def pick_up_new_offers() -> None:
    """Find every offer still waiting (status=posted) and run the agent team on it.

    "Posted" covers two cases: a genuinely new offer, and one that was requeued
    after a pantry/driver declined or a driver timed out (see
    services/offers.py:requeue_offer_for_retry). For a requeued offer,
    agent_summary already holds a note explaining why — we turn that into the
    Coordinator's task, so it knows exactly what changed since last time.

    Offers are processed one at a time, oldest first. If one offer's agent run
    fails (e.g. a network error calling the model), that failure is logged and
    every other offer still gets its turn — one bad offer should never block
    every other restaurant's food from being matched.

    Safe to call again before a previous call finishes: claim_offer_for_agent
    (inside run_case) immediately moves an offer's status away from "posted",
    so a re-run only ever sees offers nobody has started on yet.
    """
    with database.SessionLocal() as session:
        query = select(Offer.id, Offer.agent_summary).where(Offer.status == OfferStatus.POSTED).order_by(Offer.id)
        offers_to_run = list(session.execute(query).all())

    for offer_id, previous_note in offers_to_run:
        context_message = (
            f"{previous_note} Reconsider and find another solution, or explain clearly why you can't."
            if previous_note
            else None
        )
        try:
            logger.info("Waking the agent team for offer #%s", offer_id)
            run_case(offer_id, trigger=RunTrigger.NEW_OFFER, context_message=context_message)
        except Exception:
            logger.exception("Agent run failed for offer #%s", offer_id)


def expire_stale_dispatch_requests() -> None:
    """Find pickup requests nobody responded to in time, mark them expired, and
    put their offers back in the queue so the agent can find another driver.

    Each expiry is its own small database transaction (rather than one big one
    for the whole batch), so one bad row can't stop the rest from being handled.
    """
    with database.SessionLocal() as session:
        query = select(DispatchRequest.id).where(
            DispatchRequest.status == DispatchStatus.REQUESTED, DispatchRequest.expires_at < utc_now()
        )
        stale_request_ids = list(session.scalars(query))

    for request_id in stale_request_ids:
        try:
            with database.SessionLocal() as session:
                request = session.get(DispatchRequest, request_id)
                # Re-check the status: another process could have handled it since we listed it.
                if request is not None and request.status == DispatchStatus.REQUESTED:
                    expire_dispatch_request(session, request)
                    logger.info("Dispatch request #%s expired — driver did not respond in time", request_id)
        except Exception:
            logger.exception("Failed to expire dispatch request #%s", request_id)


def resume_answered_decisions() -> None:
    """Find decisions an admin has answered, and resume each paused Coordinator
    with their choice.

    This is deliberately separate from the (fast, synchronous) "answer a
    decision" API call: resuming calls the model, which can take a while, so it
    happens here on the worker's own schedule instead of making an admin's
    button click hang. Each resume is its own try/except, same as the other
    jobs — one bad decision never blocks the rest.
    """
    with database.SessionLocal() as session:
        answered_decision_ids = [decision.id for decision in list_answered_decisions(session)]

    for decision_id in answered_decision_ids:
        try:
            logger.info("Resuming offer's agent for decision #%s", decision_id)
            resume_case(decision_id)
        except Exception:
            logger.exception("Failed to resume decision #%s", decision_id)
