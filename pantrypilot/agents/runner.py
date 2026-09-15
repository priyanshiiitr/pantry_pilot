"""The ONLY entry point into the multi-agent system.

run_case() wakes the Coordinator up to work on one offer, end to end, and
records the whole thing in agent_runs/agent_log. Nothing outside this file
should build a Coordinator directly — this is where offer-claiming, error
handling and the final database write all happen consistently, every time.

resume_case() — continuing a case after a human answers a paused decision —
arrives in Step 11 once interrupts exist.
"""

from strands.models import Model

from pantrypilot import database
from pantrypilot.agents.coordinator_agent import build_coordinator_agent
from pantrypilot.agents.hooks.reasoning_log_hook import ReasoningLogHook
from pantrypilot.agents.schemas import CaseUpdate
from pantrypilot.models import Offer, RunTrigger
from pantrypilot.services.activity_log import finish_agent_run, log_event, start_agent_run
from pantrypilot.services.offers import claim_offer_for_agent, set_agent_summary


def run_case(offer_id: int, trigger: str = RunTrigger.MANUAL, model: Model | None = None) -> CaseUpdate:
    """Run the full agent team on one offer and return the Coordinator's final report.

    Raises ValueError if the offer doesn't exist. Any other failure during the
    agent run is recorded on the agent_runs row and re-raised.
    """
    with database.SessionLocal() as session:
        offer = session.get(Offer, offer_id)
        if offer is None:
            raise ValueError(f"No offer with id {offer_id}.")
        claim_offer_for_agent(session, offer)

    run_id = start_agent_run(trigger=trigger, offer_id=offer_id)
    hook = ReasoningLogHook(run_id=run_id, offer_id=offer_id, agent_name="coordinator")
    agent = build_coordinator_agent(offer_id, run_id, model=model, hooks=[hook])

    try:
        result = agent(
            f"Handle surplus food offer #{offer_id} end to end: understand it, find it a "
            "pantry, and get a driver moving — or explain clearly why you couldn't.",
            structured_output_model=CaseUpdate,
        )
    except Exception as error:
        finish_agent_run(run_id, stop_reason="error", error=str(error))
        raise

    update = result.structured_output

    with database.SessionLocal() as session:
        offer = session.get(Offer, offer_id)
        set_agent_summary(session, offer, update.summary)

    log_event(run_id, offer_id, "coordinator", "decision", update.reasoning, details=update.model_dump())
    finish_agent_run(run_id, stop_reason=result.stop_reason, outcome=update.model_dump())
    return update
