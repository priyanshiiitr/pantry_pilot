"""The Matching agent: decides which pantry should receive a surplus food offer.

THIS is where the real reasoning happens. Nothing in this file (or the tools it
calls) picks a pantry with an `if` statement — the model reads the tool results
and decides. Compare with pantrypilot/services/, which only ever *reports* facts
(distances, capacities, fairness numbers) and never *judges* them.
"""

from pathlib import Path

from strands import Agent
from strands.hooks import HookProvider
from strands.models import Model

from pantrypilot.agents.hooks.reasoning_log_hook import ReasoningLogHook
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
from pantrypilot.models import RunTrigger
from pantrypilot.services.activity_log import finish_agent_run, log_event, start_agent_run

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


def build_matching_agent(model: Model | None = None, hooks: list[HookProvider] | None = None) -> Agent:
    """Construct the Matching agent. Pass `model` to override the configured default
    (tests use this to plug in a scripted fake model instead of calling a real API)."""
    return Agent(
        model=model or build_model(),
        name="matching",
        system_prompt=MATCHING_SYSTEM_PROMPT,
        tools=MATCHING_TOOLS,
        hooks=hooks or [],
    )


def propose_match(
    offer_id: int, model: Model | None = None, trigger: str = RunTrigger.MANUAL, run_id: int | None = None
) -> MatchProposal:
    """Run the Matching agent on one offer and return its structured decision.

    Every tool call is recorded in the agent_log table via ReasoningLogHook, and
    the run itself is recorded in agent_runs — this is what the admin "Agent
    activity" page reads (see web/routes/admin.py).

    Pass `run_id` when calling this from inside another agent run (see
    coordinator_agent.py) so every log line nests under the same agent_runs row.
    Standalone callers (e.g. scripts/try_matching.py) leave it out and get their
    own run.
    """
    owns_run = run_id is None
    if owns_run:
        run_id = start_agent_run(trigger=trigger, offer_id=offer_id)

    hook = ReasoningLogHook(run_id=run_id, offer_id=offer_id, agent_name="matching")
    agent = build_matching_agent(model, hooks=[hook])

    try:
        result = agent(
            f"A new surplus food offer (id={offer_id}) has come in and needs a pantry match. "
            "Investigate it using your tools and decide.",
            structured_output_model=MatchProposal,
        )
    except Exception as error:
        if owns_run:
            finish_agent_run(run_id, stop_reason="error", error=str(error))
        raise

    proposal = result.structured_output
    log_event(run_id, offer_id, "matching", "decision", proposal.reasoning, details=proposal.model_dump())
    if owns_run:
        finish_agent_run(run_id, stop_reason=result.stop_reason, outcome=proposal.model_dump())
    return proposal
