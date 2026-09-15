"""Admin-only endpoints, under /api/admin.

DETERMINISTIC CODE: reads the database for the dashboard. The full dashboard
(stat cards, Decisions inbox, activity log, map) arrives in Steps 11-12; this
step only adds a basic list of every offer in the system.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pantrypilot.auth.current_user import require_role
from pantrypilot.database import get_db
from pantrypilot.models import Role, User
from pantrypilot.services.offers import list_all_offers
from pantrypilot.web.schemas import OfferAdminOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/offers", response_model=list[OfferAdminOut])
def list_all_offers_route(
    _user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> list[OfferAdminOut]:
    """List every offer in the system, newest first, with the restaurant's name attached.

    `_user` isn't read here — it exists only so Depends(require_role(...)) runs and
    blocks non-admins before this function body executes.
    """
    return [OfferAdminOut.from_offer(offer) for offer in list_all_offers(db)]
