"""The "forms" an agent must fill in — Pydantic models used as `structured_output_model`.

Why this matters: instead of the AI replying with loose prose ("I think Hope Pantry
is best because..."), Strands forces the reply into one of these shapes and validates
it. A judge (or our own code) can then trust that `result.structured_output` always
has these exact fields, with the right types.
"""

from pydantic import BaseModel, Field


class PantryCandidate(BaseModel):
    """One pantry the Matching agent considered, and why it did or didn't win."""

    pantry_id: int
    pantry_name: str
    reasoning: str = Field(description="Why this pantry is (or isn't) a good match, in plain English.")


class MatchProposal(BaseModel):
    """The Matching agent's decision: which pantry (if any) should get this offer."""

    chosen_pantry_id: int | None = Field(description="The winning pantry's id, or null if none can take it.")
    ranked_candidates: list[PantryCandidate] = Field(description="Every pantry considered, best first.")
    reasoning: str = Field(description="The overall explanation: why the winner beat the alternatives.")
    concerns: list[str] = Field(default_factory=list, description="Anything a human might want to double-check.")
    confident_to_proceed: bool = Field(
        description="False if this is a genuine judgment call that should be escalated to a human (Step 11)."
    )
