"""All database tables.

Importing this package registers every table with SQLAlchemy, so
`Base.metadata.create_all()` knows what to create. Other code can simply do:

    from pantrypilot.models import Offer, Pantry
"""

from pantrypilot.models.agent_records import (
    AgentLog,
    AgentMemory,
    AgentRun,
    Decision,
    DecisionKind,
    DecisionStatus,
    RunTrigger,
)
from pantrypilot.models.offers import (
    Delivery,
    DeliveryStatus,
    DispatchRequest,
    DispatchStatus,
    Offer,
    OfferStatus,
    PantryResponse,
)
from pantrypilot.models.places import DIETARY_RESTRICTIONS, Driver, Pantry, Restaurant
from pantrypilot.models.system import AppSetting, Notification
from pantrypilot.models.users import Role, User

__all__ = [
    "DIETARY_RESTRICTIONS",
    "AgentLog",
    "AgentMemory",
    "AgentRun",
    "AppSetting",
    "Decision",
    "DecisionKind",
    "DecisionStatus",
    "Delivery",
    "DeliveryStatus",
    "DispatchRequest",
    "DispatchStatus",
    "Driver",
    "Notification",
    "Offer",
    "OfferStatus",
    "Pantry",
    "PantryResponse",
    "Restaurant",
    "Role",
    "RunTrigger",
    "User",
]
