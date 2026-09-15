"""The scheduled jobs themselves — what the worker checks, and how often.

DETERMINISTIC CODE: this decides WHEN to wake the agents up. What they do once
awake is entirely runner.run_case()'s business, not this file's.
"""

import logging

from sqlalchemy import select

from pantrypilot import database
from pantrypilot.agents.runner import run_case
from pantrypilot.models import Offer, OfferStatus, RunTrigger

logger = logging.getLogger(__name__)


def pick_up_new_offers() -> None:
    """Find every offer still waiting (status=posted) and run the agent team on it.

    Offers are processed one at a time, oldest first. If one offer's agent run
    fails (e.g. a network error calling the model), that failure is logged and
    every other offer still gets its turn — one bad offer should never block
    every other restaurant's food from being matched.

    Safe to call again before a previous call finishes: claim_offer_for_agent
    (inside run_case) immediately moves an offer's status away from "posted",
    so a re-run only ever sees offers nobody has started on yet.
    """
    with database.SessionLocal() as session:
        posted_offer_ids = list(
            session.scalars(select(Offer.id).where(Offer.status == OfferStatus.POSTED).order_by(Offer.id))
        )

    for offer_id in posted_offer_ids:
        try:
            logger.info("Waking the agent team for offer #%s", offer_id)
            run_case(offer_id, trigger=RunTrigger.NEW_OFFER)
        except Exception:
            logger.exception("Agent run failed for offer #%s", offer_id)
