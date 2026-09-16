"""The Coordinator's action tools: things that actually change the world (assign a
pantry, ask a driver, cancel, flag for a human, notify someone).

Each tool requires a `reason` argument — the agent must always say why it acted,
and that reason ends up on the offer/delivery for humans to read.

Why these are built by a factory function (build_action_tools), not plain
module-level @tool functions like the read-only tools: each one needs to know
WHICH offer it's acting on. Rather than trust the model to pass the right
offer_id correctly on every single call (a real source of bugs), we bind it once
via a Python closure when the Coordinator is built for that offer — the model
only ever supplies genuine decisions (which pantry, which driver, why), never
bookkeeping IDs it could get wrong.
"""

from typing import Any

from strands import tool
from strands.types.tools import AgentTool

from pantrypilot import database
from pantrypilot.models import Driver, Offer, Pantry
from pantrypilot.services import deliveries as deliveries_service
from pantrypilot.services import dispatch as dispatch_service
from pantrypilot.services import offers as offers_service
from pantrypilot.services.notifications import notify_user as notify_user_service


def build_action_tools(offer_id: int) -> list[AgentTool]:
    """Build the four action tools, each bound to `offer_id` via closure."""

    @tool
    def assign_delivery(pantry_id: int, reason: str) -> dict[str, Any]:
        """Commit this offer to `pantry_id`. Call this once run_matching has told you
        which pantry to use. This does not ask a driver yet — call
        send_dispatch_request next.

        Args:
            pantry_id: the pantry to assign this offer to.
            reason: why you chose this pantry (shown to the restaurant and pantry).
        """
        with database.SessionLocal() as session:
            offer = session.get(Offer, offer_id)
            pantry = session.get(Pantry, pantry_id)
            if offer is None or pantry is None:
                return {"error": f"offer {offer_id} or pantry {pantry_id} not found"}

            delivery = deliveries_service.assign_delivery(session, offer, pantry, reason)
            notify_user_service(session, pantry.user_id, f'New delivery incoming: "{offer.title}" — {reason}')
            return {"delivery_id": delivery.id, "status": delivery.status}

    @tool
    def send_dispatch_request(driver_id: int, reason: str) -> dict[str, Any]:
        """Ask `driver_id` to do the pickup for this offer's assigned delivery. Call
        this after assign_delivery.

        Args:
            driver_id: the driver to ask.
            reason: why this driver (shown to the driver and restaurant).
        """
        with database.SessionLocal() as session:
            delivery = deliveries_service.get_latest_delivery(session, offer_id)
            driver = session.get(Driver, driver_id)
            if delivery is None:
                return {"error": f"no delivery planned yet for offer {offer_id} — call assign_delivery first"}
            if driver is None:
                return {"error": f"driver {driver_id} not found"}

            request = dispatch_service.send_dispatch_request(session, delivery, driver, reason)
            notify_user_service(session, driver.user_id, f'New pickup request: "{delivery.offer.title}" — {reason}')
            return {"dispatch_request_id": request.id, "status": request.status}

    @tool
    def flag_needs_human(reason: str) -> dict[str, Any]:
        """Mark this offer as needing a human's attention, instead of guessing. Use
        this when you genuinely cannot make a safe, confident decision (e.g. no
        pantry can respond in time, or something looks unsafe).

        Args:
            reason: what a human needs to look at and why.
        """
        with database.SessionLocal() as session:
            offer = session.get(Offer, offer_id)
            if offer is None:
                return {"error": f"offer {offer_id} not found"}
            offers_service.flag_needs_human(session, offer, reason)
            return {"status": "needs_human"}

    @tool
    def cancel_offer(reason: str) -> dict[str, Any]:
        """Cancel this offer entirely. Use only when nothing can be done for it at
        all (e.g. it has already spoiled).

        Args:
            reason: why you're cancelling (shown to the restaurant).
        """
        with database.SessionLocal() as session:
            offer = session.get(Offer, offer_id)
            if offer is None:
                return {"error": f"offer {offer_id} not found"}
            offers_service.cancel_offer(session, offer, reason)
            return {"status": "cancelled"}

    return [assign_delivery, send_dispatch_request, flag_needs_human, cancel_offer]


@tool
def notify_user(user_id: int, message: str) -> dict[str, Any]:
    """Send a plain-English notification to a specific user, e.g. to give the
    restaurant owner a heads-up about something unusual.

    Args:
        user_id: which user to notify.
        message: what to tell them.
    """
    with database.SessionLocal() as session:
        notify_user_service(session, user_id, message)
        return {"status": "sent"}
