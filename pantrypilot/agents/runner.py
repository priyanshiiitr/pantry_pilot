"""The ONLY entry point into the multi-agent system.

run_case() wakes the Coordinator up to work on one offer, end to end, and
records the whole thing in agent_runs/agent_log. resume_case() continues a
case after an admin has answered a paused decision. Nothing outside this file
should build a Coordinator directly — this is where offer-claiming, error
handling and the final database write all happen consistently, every time.
"""

from strands.agent import AgentResult
from strands.models import Model

from pantrypilot import database
from pantrypilot.agents.coordinator_agent import build_coordinator_agent
from pantrypilot.agents.hooks.reasoning_log_hook import ReasoningLogHook
from pantrypilot.agents.schemas import CaseUpdate
from pantrypilot.agents.sessions import build_offer_session_manager
from pantrypilot.models import DecisionStatus, Offer, RunTrigger
from pantrypilot.services.activity_log import finish_agent_run, log_event, start_agent_run
from pantrypilot.services.decisions import create_decision, get_decision, mark_decision_failed, mark_decision_resumed
from pantrypilot.services.offers import claim_offer_for_agent, flag_needs_human, set_agent_summary

DEFAULT_TASK_TEMPLATE = (
    "Handle surplus food offer #{offer_id} end to end: understand it, find it a "
    "pantry, and get a driver moving — or explain clearly why you couldn't."
)

# Used by resume_case's second turn — see the comment where it's used for why
# this is a separate call rather than combined with the interrupt response.
RESUME_REPORT_PROMPT = (
    "Now that you've resumed, finish taking any remaining actions, then report "
    "your final CaseUpdate summarizing what happened and why."
)


def run_case(
    offer_id: int,
    trigger: str = RunTrigger.MANUAL,
    model: Model | None = None,
    context_message: str | None = None,
) -> CaseUpdate | None:
    """Run the full agent team on one offer.

    Returns the Coordinator's final report, or None if it paused to ask an
    admin a question instead (see agents/tools/human_tools.py) — check the
    Decisions inbox (services/decisions.py) for what it's waiting on.

    Pass `context_message` to tell the Coordinator something specific instead of
    the generic opening prompt — e.g. "Driver Sam declined: car trouble. Find
    another solution." (see worker/jobs.py, which builds this from the note left
    by requeue_offer_for_retry). Its per-offer session (agents/sessions.py) also
    remembers the earlier attempt on its own either way.

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
    session_manager = build_offer_session_manager(offer_id)
    agent = build_coordinator_agent(offer_id, run_id, model=model, hooks=[hook], session_manager=session_manager)

    task = context_message or DEFAULT_TASK_TEMPLATE.format(offer_id=offer_id)

    try:
        result = agent(task, structured_output_model=CaseUpdate)
    except Exception as error:
        finish_agent_run(run_id, stop_reason="error", error=str(error))
        raise

    return _handle_agent_result(result, run_id, offer_id)


def resume_case(decision_id: int, model: Model | None = None) -> CaseUpdate | None:
    """Continue a Coordinator conversation that paused at ask_admin, now that an
    admin has answered (see services/decisions.py).

    Rebuilds the SAME per-offer session (agents/sessions.py), so the agent picks
    up exactly where it left off — even if the worker process restarted since it
    paused. May itself return None again, if the agent needs to ask something
    else before it can finish.

    Raises ValueError if the decision isn't in "answered" state.
    """
    with database.SessionLocal() as session:
        decision = get_decision(session, decision_id)
        if decision.status != DecisionStatus.ANSWERED:
            raise ValueError(f"Decision {decision_id} is '{decision.status}', not 'answered'.")
        offer_id = decision.offer_id
        interrupt_id = decision.interrupt_id
        admin_response = {"chosen_option": decision.chosen_option, "admin_note": decision.admin_note}

    run_id = start_agent_run(trigger=RunTrigger.ADMIN_DECISION, offer_id=offer_id)
    hook = ReasoningLogHook(run_id=run_id, offer_id=offer_id, agent_name="coordinator")
    session_manager = build_offer_session_manager(offer_id)
    agent = build_coordinator_agent(offer_id, run_id, model=model, hooks=[hook], session_manager=session_manager)

    try:
        # Resuming with a raw interruptResponse list is an unusual input shape —
        # asking for structured_output_model in that SAME call was observed (live,
        # against Groq's gpt-oss-120b) to sometimes confuse the model into calling
        # a nonexistent tool named "json" (the internal schema key, not a real
        # tool) instead of continuing normally. Splitting into two ordinary turns
        # avoids it: resume first in plain form, then ask for the structured
        # report once the conversation is back to a normal shape.
        result = agent([{"interruptResponse": {"interruptId": interrupt_id, "response": admin_response}}])
        if result.stop_reason != "interrupt":
            result = agent(RESUME_REPORT_PROMPT, structured_output_model=CaseUpdate)
    except Exception as error:
        finish_agent_run(run_id, stop_reason="error", error=str(error))
        with database.SessionLocal() as session:
            mark_decision_failed(session, get_decision(session, decision_id))
        raise

    with database.SessionLocal() as session:
        mark_decision_resumed(session, get_decision(session, decision_id))
    log_event(run_id, offer_id, "coordinator", "resumed", "Resumed after the admin's decision.")

    return _handle_agent_result(result, run_id, offer_id)


def _handle_agent_result(result: AgentResult, run_id: int, offer_id: int) -> CaseUpdate | None:
    """Shared by run_case and resume_case: interpret whatever the Coordinator's
    agent() call just returned, and record it consistently.

    Two outcomes:
    - The agent paused to ask a human (result.stop_reason == "interrupt"): save
      a new pending Decision from the interrupt's card, mark the offer
      needs_human, and return None.
    - The agent finished (produced a CaseUpdate): save its summary/reasoning and
      return the CaseUpdate.
    """
    if result.stop_reason == "interrupt":
        interrupt = result.interrupts[0]
        card = interrupt.reason if isinstance(interrupt.reason, dict) else {"reasoning": str(interrupt.reason)}

        with database.SessionLocal() as session:
            offer = session.get(Offer, offer_id)
            create_decision(session, offer_id, interrupt.id, interrupt.name, card)
            flag_needs_human(session, offer, card.get("title", "The agent needs a human decision."))

        log_event(run_id, offer_id, "coordinator", "interrupt", card.get("title", "Escalated to admin"), details=card)
        finish_agent_run(run_id, stop_reason="interrupt", outcome=card)
        return None

    update = result.structured_output

    with database.SessionLocal() as session:
        offer = session.get(Offer, offer_id)
        set_agent_summary(session, offer, update.summary)

    log_event(run_id, offer_id, "coordinator", "decision", update.reasoning, details=update.model_dump())
    finish_agent_run(run_id, stop_reason=result.stop_reason, outcome=update.model_dump())
    return update
