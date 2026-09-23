"""The Intake agent: turns a restaurant's raw offer text into clean, structured data.

THIS is where the reading and inference happens. Nothing here decides where the
food goes — that's the Matching agent's job (matching_agent.py). Intake only
answers "what is this, roughly how much, and does anything look off?".
"""

from pathlib import Path

from strands import Agent
from strands.hooks import HookProvider
from strands.models import Model

from pantrypilot.agents.hooks.reasoning_log_hook import ReasoningLogHook
from pantrypilot.agents.model_provider import build_model
from pantrypilot.agents.schemas import OfferDetails
from pantrypilot.agents.tools.offer_tools import get_current_time, get_offer
from pantrypilot.models import RunTrigger
from pantrypilot.services.activity_log import finish_agent_run, log_event, start_agent_run
from pantrypilot.services.offers import save_structured_details

_PROMPT_PATH = Path(__file__).parent / "prompts" / "intake.md"
INTAKE_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

INTAKE_TOOLS = [get_offer, get_current_time]


def build_intake_agent(model: Model | None = None, hooks: list[HookProvider] | None = None) -> Agent:
    """Construct the Intake agent."""
    return Agent(
        model=model or build_model(),
        name="intake",
        system_prompt=INTAKE_SYSTEM_PROMPT,
        tools=INTAKE_TOOLS,
        hooks=hooks or [],
    )


def run_intake_case(
    offer_id: int, model: Model | None = None, trigger: str = RunTrigger.MANUAL, run_id: int | None = None
) -> OfferDetails:
    """Run the Intake agent on one offer and return its structured breakdown.

    Pass `run_id` when calling this from inside another agent run (see
    coordinator_agent.py) so every log line nests under the same agent_runs row,
    instead of creating a separate one. Standalone callers (e.g. a future
    scripts/try_intake.py) leave it out and get their own run.
    """
    owns_run = run_id is None
    if owns_run:
        run_id = start_agent_run(trigger=trigger, offer_id=offer_id)

    hook = ReasoningLogHook(run_id=run_id, offer_id=offer_id, agent_name="intake")
    agent = build_intake_agent(model, hooks=[hook])

    try:
        result = agent(
            f"A new surplus food offer (id={offer_id}) needs its raw text turned into "
            "structured data. Investigate it using your tools and report back.",
            structured_output_model=OfferDetails,
        )
    except Exception as error:
        if owns_run:
            finish_agent_run(run_id, stop_reason="error", error=str(error))
        raise

    details = result.structured_output
    # Save it on the offer, not just in the log. Matching and Dispatch read it
    # back through get_offer; without this each of them re-derives the weight and
    # allergens from the raw text, and they disagree — watching a real run,
    # Intake computed 38.0kg while Dispatch separately guessed "maybe 30-40kg"
    # and filtered a driver's capacity on its own guess.
    save_structured_details(offer_id, details.model_dump())

    summary = f"Estimated {details.estimated_kg}kg, {details.estimated_meals} meals."
    log_event(run_id, offer_id, "intake", "decision", summary, details=details.model_dump())
    if owns_run:
        finish_agent_run(run_id, stop_reason=result.stop_reason, outcome=details.model_dump())
    return details
