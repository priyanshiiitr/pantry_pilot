"""Tests for agents/tools/offer_tools.py — get_offer, get_current_time.

These call the @tool-decorated functions directly (they remain plain
callables), bypassing any LLM — this tests the tool's own logic, never a
real model call.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pantrypilot.services.offers import save_structured_details
from pantrypilot.agents.tools.offer_tools import get_current_time, get_offer
from pantrypilot.database import utc_now
from pantrypilot.models import Offer, Restaurant, Role, User


def make_offer(db_session: Session) -> Offer:
    """Create a minimal offer with its restaurant."""
    user = User(email="r@test.local", role=Role.RESTAURANT, display_name="R", password_hash="x")
    restaurant = Restaurant(user=user, name="Golden Crust Bakery", address="123 Main St", lat=47.6, lon=-122.3)
    offer = Offer(
        restaurant=restaurant,
        title="Unsold bread",
        description="40 loaves",
        quantity_text="40 loaves",
        allergen_notes="wheat",
        pickup_deadline=utc_now() + timedelta(hours=2),
    )
    db_session.add_all([user, restaurant, offer])
    db_session.commit()
    return offer


def test_get_offer_returns_all_the_fields_the_agent_needs(db_session: Session) -> None:
    """get_offer includes the restaurant's location, needed for distance/travel-time tools."""
    offer = make_offer(db_session)

    result = get_offer(offer_id=offer.id)

    assert result["title"] == "Unsold bread"
    assert result["restaurant_name"] == "Golden Crust Bakery"
    assert result["restaurant_lat"] == 47.6
    assert result["restaurant_lon"] == -122.3
    assert result["allergen_notes"] == "wheat"


@pytest.mark.usefixtures("db_session")  # activates the temp-database swap; no data is needed for this check
def test_get_offer_reports_a_clear_error_for_a_missing_id() -> None:
    """A bad offer_id returns an error dict, not a crash — the model can react to this."""
    result = get_offer(offer_id=999999)

    assert "error" in result


def test_get_current_time_is_close_to_now() -> None:
    """The tool's answer matches wall-clock time (the agent has no other way to know "now")."""
    result = get_current_time()

    reported = datetime.fromisoformat(result["utc_now"])
    assert abs((utc_now() - reported).total_seconds()) < 5


def test_get_offer_exposes_intakes_analysis(db_session: Session) -> None:
    """Matching and Dispatch read Intake's numbers back through get_offer.

    structured_details was declared on the model and documented as "filled in by
    the Intake agent", but nothing ever wrote or read it. Intake's analysis was
    computed, logged, and thrown away, so every later specialist re-derived the
    weight and allergens from the raw text and reached different answers.
    """
    offer = make_offer(db_session)
    save_structured_details(offer.id, {"estimated_kg": 38.0, "perishability": "high"})

    result = get_offer(offer_id=offer.id)

    assert result["structured_details"]["estimated_kg"] == 38.0
    assert result["structured_details"]["perishability"] == "high"


def test_get_offer_has_no_analysis_before_intake_runs(db_session: Session) -> None:
    """Before Intake has looked at it the field is null, not missing or an error."""
    offer = make_offer(db_session)

    assert get_offer(offer_id=offer.id)["structured_details"] is None


def test_saving_analysis_for_a_missing_offer_is_a_no_op(db_session: Session) -> None:
    """A deleted or cancelled offer shouldn't crash the agent run that was analysing it."""
    save_structured_details(999999, {"estimated_kg": 1.0})
