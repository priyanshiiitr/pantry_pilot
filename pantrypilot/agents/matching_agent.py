"""The Matching agent: decides which pantry should receive a surplus food offer.

THIS is where the real reasoning happens. Nothing in this file (or the tools it
calls) picks a pantry with an `if` statement — the model reads the tool results
and decides. Compare with pantrypilot/services/, which only ever *reports* facts
(distances, capacities, fairness numbers) and never *judges* them.
"""

from pathlib import Path

from strands import Agent
from strands.models import Model

from pantrypilot.agents.model_provider import build_model
from pantrypilot.agents.schemas import MatchProposal
from pantrypilot.agents.tools.geo_tools import estimate_travel_time
from pantrypilot.agents.tools.memory_tools import recall_facts
from pantrypilot.agents.tools.offer_tools import get_current_time, get_offer
from pantrypilot.agents.tools.pantry_tools import (
    calculate_fairness_score,
    check_pantry_capacity,
    find_nearby_pantries,
    get_pantry_profile,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "matching.md"
MATCHING_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

MATCHING_TOOLS = [
    get_offer,
    get_current_time,
    find_nearby_pantries,
    get_pantry_profile,
    check_pantry_capacity,
    calculate_fairness_score,
    estimate_travel_time,
    recall_facts,
]


def build_matching_agent(model: Model | None = None) -> Agent:
    """Construct the Matching agent. Pass `model` to override the configured default
    (tests use this to plug in a scripted fake model instead of calling a real API)."""
    return Agent(
        model=model or build_model(),
        name="matching",
        system_prompt=MATCHING_SYSTEM_PROMPT,
        tools=MATCHING_TOOLS,
    )


def propose_match(offer_id: int, model: Model | None = None) -> MatchProposal:
    """Run the Matching agent on one offer and return its structured decision."""
    agent = build_matching_agent(model)
    result = agent(
        f"A new surplus food offer (id={offer_id}) has come in and needs a pantry match. "
        "Investigate it using your tools and decide.",
        structured_output_model=MatchProposal,
    )
    return result.structured_output
