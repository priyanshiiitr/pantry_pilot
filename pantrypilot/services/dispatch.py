"""Asking a driver to do a pickup: sending the request, and handling accept,
decline, or nobody responding in time.

DETERMINISTIC CODE: no AI involved, and no decisions about WHICH driver — that's
agents/dispatch_agent.py. This only applies actions once someone has decided.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, DeliveryStatus, Driver, DispatchRequest, DispatchStatus, OfferStatus
from pantrypilot.services.offers import requeue_offer_for_retry

# How long a driver has to accept/decline before the worker (worker/jobs.py)
# treats a dispatch request as expired and puts the offer back in the queue.
DISPATCH_REQUEST_WINDOW = timedelta(minutes=15)


def send_dispatch_request(session: Session, delivery: Delivery, driver: Driver, reason: str) -> DispatchRequest:
    """Ask `driver` to do the pickup for `delivery`, and move the offer/delivery
    into the driver_requested state."""
    request = DispatchRequest(delivery=delivery, driver=driver, expires_at=utc_now() + DISPATCH_REQUEST_WINDOW)
    # Add `request` to the session BEFORE touching delivery.offer below: reading that
    # relationship can trigger SQLAlchemy's autoflush, which would otherwise try to
    # flush `request` while it's linked in-memory but not yet tracked by the session.
    session.add(request)
    delivery.status = DeliveryStatus.DRIVER_REQUESTED
    delivery.dispatch_reasoning = reason
    delivery.offer.status = OfferStatus.DRIVER_REQUESTED
    session.commit()
    session.refresh(request)
    return request


def get_pending_dispatch_requests_for_driver(session: Session, driver: Driver) -> list[DispatchRequest]:
    """Return requests sent to this driver that they haven't answered yet."""
    query = (
        select(DispatchRequest)
        .where(DispatchRequest.driver_id == driver.id, DispatchRequest.status == DispatchStatus.REQUESTED)
        .order_by(DispatchRequest.sent_at.desc(), DispatchRequest.id.desc())
    )
    return list(session.scalars(query))


def get_dispatch_request_for_driver(session: Session, driver: Driver, request_id: int) -> DispatchRequest:
    """Return one of this driver's own requests, or raise LookupError if it isn't theirs."""
    query = select(DispatchRequest).where(DispatchRequest.id == request_id, DispatchRequest.driver_id == driver.id)
    request = session.scalar(query)
    if request is None:
        raise LookupError(f"No dispatch request {request_id} for driver {driver.id}.")
    return request


def accept_dispatch_request(session: Session, request: DispatchRequest) -> None:
    """The driver agrees to do the pickup."""
    request.status = DispatchStatus.ACCEPTED
    request.responded_at = utc_now()
    request.delivery.driver_id = request.driver_id
    request.delivery.status = DeliveryStatus.DRIVER_ASSIGNED
    request.delivery.offer.status = OfferStatus.DRIVER_ASSIGNED
    session.commit()


def decline_dispatch_request(session: Session, request: DispatchRequest, reason: str) -> None:
    """The driver says no. The pantry choice still stands — only a new driver is
    needed — so the delivery goes back to PLANNED (not cancelled) and the offer
    is requeued for the agent to find someone else."""
    request.status = DispatchStatus.DECLINED
    request.decline_reason = reason
    request.responded_at = utc_now()
    request.delivery.status = DeliveryStatus.PLANNED
    requeue_offer_for_retry(session, request.delivery.offer, f"{request.driver.name} declined the pickup: {reason}")


def expire_dispatch_request(session: Session, request: DispatchRequest) -> None:
    """Nobody responded in time. Same outcome as a decline: find another driver."""
    request.status = DispatchStatus.EXPIRED
    request.responded_at = utc_now()
    request.delivery.status = DeliveryStatus.PLANNED
    note = f"{request.driver.name} did not respond to the pickup request in time."
    requeue_offer_for_retry(session, request.delivery.offer, note)
