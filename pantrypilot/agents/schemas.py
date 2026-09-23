"""The "forms" an agent must fill in — Pydantic models used as `structured_output_model`.

Why this matters: instead of the AI replying with loose prose ("I think Hope Pantry
is best because..."), Strands forces the reply into one of these shapes and validates
it. A judge (or our own code) can then trust that `result.structured_output` always
has these exact fields, with the right types.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class _ListFieldsAcceptNull(BaseModel):
    """Base model that reads a null list as an empty one.

    Models reach for `null` to mean "none of these" — observed live, a Dispatch
    agent with no backup drivers answered `backup_driver_ids=null` and the run
    failed validation, costing a retry (and, on a rate-limited tier, a minute) to
    say something it had already said correctly. An empty list is what it meant.
    """

    @field_validator("*", mode="before")
    @classmethod
    def _null_list_becomes_empty(cls, value: object, info: object) -> object:
        if value is None and cls.model_fields[info.field_name].annotation in (list[str], list[int]):
            return []
        return value


class OfferDetails(_ListFieldsAcceptNull):
    """The Intake agent's clean breakdown of a restaurant's raw offer text."""

    items: list[str] = Field(description="Plain list of what's being offered, e.g. ['60 cream pastries'].")
    estimated_kg: float = Field(description="Best estimate of total weight in kilograms.")
    estimated_meals: int = Field(description="Best estimate of how many meals/servings this represents.")
    allergens: list[str] = Field(default_factory=list, description="Allergens present, e.g. ['dairy', 'gluten'].")
    dietary_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Which known pantry dietary-restriction tags this food would conflict with, using exactly these "
            "names: no_pork, no_beef, halal_only, kosher_only, vegetarian_only, no_nuts, no_alcohol."
        ),
    )
    needs_refrigeration: bool = Field(description="Whether this food needs a fridge or freezer to stay safe.")
    perishability: Literal["low", "medium", "high"] = Field(description="How quickly this spoils if not handled.")
    concerns: list[str] = Field(default_factory=list, description="Anything unclear, unsafe, or worth double-checking.")
    confidence: float = Field(description="0 to 1: how confident you are in this breakdown.")


class PantryCandidate(BaseModel):
    """One pantry the Matching agent considered, and why it did or didn't win."""

    pantry_id: int
    pantry_name: str
    reasoning: str = Field(description="Why this pantry is (or isn't) a good match, in plain English.")


class MatchProposal(_ListFieldsAcceptNull):
    """The Matching agent's decision: which pantry (if any) should get this offer."""

    chosen_pantry_id: int | None = Field(description="The winning pantry's id, or null if none can take it.")
    ranked_candidates: list[PantryCandidate] = Field(description="Every pantry considered, best first.")
    reasoning: str = Field(description="The overall explanation: why the winner beat the alternatives.")
    concerns: list[str] = Field(default_factory=list, description="Anything a human might want to double-check.")
    confident_to_proceed: bool = Field(
        description="False if this is a genuine judgment call that should be escalated to a human (Step 11)."
    )


class DispatchPlan(_ListFieldsAcceptNull):
    """The Dispatch agent's decision: which driver (if any) should do this pickup."""

    driver_id: int | None = Field(description="The chosen driver's id, or null if nobody can do it in time.")
    eta_minutes: float | None = Field(description="Estimated minutes until this driver could arrive at pickup.")
    backup_driver_ids: list[int] = Field(default_factory=list, description="Other viable drivers, in case of decline.")
    reasoning: str = Field(description="Why this driver, over the alternatives.")
    concerns: list[str] = Field(default_factory=list, description="Anything a human might want to double-check.")


class CaseUpdate(_ListFieldsAcceptNull):
    """The Coordinator's final report on one offer: what happened and why."""

    status: Literal["driver_requested", "needs_human", "cancelled", "no_action"] = Field(
        description="What state this offer is in after your work."
    )
    summary: str = Field(description="A short plain-English summary, shown to the restaurant.")
    reasoning: str = Field(description="Your full reasoning for what you did and why.")
