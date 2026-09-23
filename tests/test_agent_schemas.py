"""Tests for agents/schemas.py — the Pydantic "forms" each agent must fill in.

These need no database and no model: they check that the structured-output
contract is forgiving where a model is reasonably loose, and strict where it
actually matters.
"""

import pytest
from pydantic import ValidationError

from pantrypilot.agents.schemas import CaseUpdate, DispatchPlan, OfferDetails


def test_a_null_list_is_read_as_an_empty_one() -> None:
    """Models say `null` to mean "none of these"; that shouldn't cost a retry.

    Observed live: a Dispatch agent with no backup drivers answered
    backup_driver_ids=null, failed validation, and had to redo the whole turn —
    which on a rate-limited tier costs a minute to restate what it got right.
    """
    plan = DispatchPlan(
        driver_id=None, eta_minutes=None, backup_driver_ids=None, reasoning="nobody free", concerns=None
    )

    assert plan.backup_driver_ids == []
    assert plan.concerns == []


def test_null_lists_are_accepted_on_every_agent_form() -> None:
    """The same leniency applies to Intake's and the Coordinator's forms."""
    details = OfferDetails(
        items=["rice"], estimated_kg=3.0, estimated_meals=10, allergens=None, dietary_tags=None,
        needs_refrigeration=True, perishability="high", concerns=None, confidence=0.9,
    )

    assert details.allergens == []
    assert details.dietary_tags == []
    assert details.concerns == []


def test_real_lists_are_left_alone() -> None:
    """The null coercion must not touch lists that actually have content."""
    plan = DispatchPlan(
        driver_id=3, eta_minutes=12.5, backup_driver_ids=[4, 5], reasoning="closest", concerns=["tight window"]
    )

    assert plan.backup_driver_ids == [4, 5]
    assert plan.concerns == ["tight window"]


def test_null_is_still_meaningful_for_genuinely_optional_fields() -> None:
    """driver_id=None means "nobody can do it" and must stay None, not become []."""
    plan = DispatchPlan(driver_id=None, eta_minutes=None, reasoning="no driver in range")

    assert plan.driver_id is None
    assert plan.eta_minutes is None


def test_wrong_types_are_still_rejected() -> None:
    """Coercing null lists must not turn the schema into a rubber stamp."""
    with pytest.raises(ValidationError):
        DispatchPlan(driver_id="not-an-int", eta_minutes=None, reasoning="r")


def test_a_missing_required_field_is_still_rejected() -> None:
    """reasoning is what the admin actually reads — it can't be silently skipped."""
    with pytest.raises(ValidationError):
        DispatchPlan(driver_id=1, eta_minutes=5.0)


def test_case_update_status_is_restricted_to_known_states() -> None:
    """The Coordinator's status drives UI and worker behaviour, so it stays a closed set."""
    with pytest.raises(ValidationError):
        CaseUpdate(status="something_invented", summary="s", reasoning="r")
