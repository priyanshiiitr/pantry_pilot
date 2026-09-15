"""The Dispatch agent: finds a volunteer driver for an offer that already has a
pantry chosen.

THIS is where the driver decision happens. Nothing here decides the pantry —
that already happened in matching_agent.py — Dispatch only answers "who should
drive this, and can they make it in time?".
"""

from pathlib import Path

from strands import Agent
from strands.hooks import HookProvider
from strands.models import Model

from pantrypilot.agents.hooks.reasoning_log_hook import ReasoningLogHook
from pantrypilot.agents.model_provider import build_model
from pantrypilot.agents.schemas import DispatchPlan
from pantrypilot.agents.tools.driver_tools import get_available_drivers, get_driver_history
from pantrypilot.agents.tools.geo_tools import estimate_travel_time
from pantrypilot.agents.tools.memory_tools import recall_facts
from pantrypilot.agents.tools.offer_tools import get_current_time, get_offer
from pantrypilot.agents.tools.pantry_tools import get_pantry_profile
from pantrypilot.models import RunTrigger
from pantrypilot.services.activity_log import finish_agent_run, log_event, start_agent_run

_PROMPT_PATH = Path(__file__).parent / "prompts" / "dispatch.md"
DISPATCH_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

DISPATCH_TOOLS = [
    get_offer,
    get_current_time,
    get_pantry_profile,
    get_available_drivers,
    get_driver_history,
    estimate_travel_time,
    recall_facts,
]


def build_dispatch_agent(model: Model | None = None, hooks: list[HookProvider] | None = None) -> Agent:
    """Construct the Dispatch agent."""
    return Agent(
        model=model or build_model(),
        name="dispatch",
        system_prompt=DISPATCH_SYSTEM_PROMPT,
        tools=DISPATCH_TOOLS,
        hooks=hooks or [],
    )


def propose_dispatch(
    offer_id: int,
    pantry_id: int,
    model: Model | None = None,
    trigger: str = RunTrigger.MANUAL,
    run_id: int | None = None,
) -> DispatchPlan:
    """Run the Dispatch agent for one offer/pantry pair and return its driver choice.

    Pass `run_id` to nest this under an existing agent run (see coordinator_agent.py).
    """
    owns_run = run_id is None
    if owns_run:
        run_id = start_agent_run(trigger=trigger, offer_id=offer_id)

    hook = ReasoningLogHook(run_id=run_id, offer_id=offer_id, agent_name="dispatch")
    agent = build_dispatch_agent(model, hooks=[hook])

    try:
        result = agent(
            f"Offer id={offer_id} has been matched to pantry id={pantry_id}. Find the best "
            "driver to do this pickup and delivery, or explain why nobody can.",
            structured_output_model=DispatchPlan,
        )
    except Exception as error:
        if owns_run:
            finish_agent_run(run_id, stop_reason="error", error=str(error))
        raise

    plan = result.structured_output
    log_event(run_id, offer_id, "dispatch", "decision", plan.reasoning, details=plan.model_dump())
    if owns_run:
        finish_agent_run(run_id, stop_reason=result.stop_reason, outcome=plan.model_dump())
    return plan
