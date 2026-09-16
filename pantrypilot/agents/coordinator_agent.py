"""The Coordinator agent: manages one offer end to end, using the other three
agents (Intake, Matching, Dispatch) as tools — the "agents-as-tools" pattern.

THIS is where the routing decision happens: whether to re-run matching, whether
dispatch's answer is good enough, whether to commit or flag for a human. None of
that is a fixed sequence in code — the Coordinator decides, every time, based on
what its specialists actually reported back.

Note: Strands also offers `some_agent.as_tool(...)` to turn an existing Agent
directly into a tool. We build our own thin wrapper functions instead (below),
because we want explicit control over structured output, run-id nesting for the
activity log, and clean typed return values — see run_intake/run_matching/
run_dispatch.
"""

from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.hooks import HookProvider
from strands.models import Model
from strands.session import SessionManager
from strands.types.tools import AgentTool

from pantrypilot.agents.dispatch_agent import propose_dispatch
from pantrypilot.agents.intake_agent import run_intake_case
from pantrypilot.agents.matching_agent import propose_match
from pantrypilot.agents.model_provider import build_model
from pantrypilot.agents.tools.action_tools import build_action_tools, notify_user
from pantrypilot.agents.tools.human_tools import build_ask_admin_tool
from pantrypilot.agents.tools.memory_tools import recall_facts, remember_fact

_PROMPT_PATH = Path(__file__).parent / "prompts" / "coordinator.md"
COORDINATOR_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def _build_specialist_tools(offer_id: int, run_id: int) -> list[AgentTool]:
    """Build the run_intake/run_matching/run_dispatch tools, each bound to this
    offer and nested under this run via closure (see agents/tools/action_tools.py
    for why we do this instead of trusting the model to pass offer_id correctly).
    """

    @tool
    def run_intake() -> dict[str, Any]:
        """Ask the Intake specialist to turn this offer's raw text into clean,
        structured data: estimated weight/meals, allergens, dietary conflicts,
        perishability and any concerns. Usually a good first step."""
        return run_intake_case(offer_id, run_id=run_id).model_dump()

    @tool
    def run_matching() -> dict[str, Any]:
        """Ask the Matching specialist to investigate nearby pantries and propose
        which one should receive this offer, with full reasoning."""
        return propose_match(offer_id, run_id=run_id).model_dump()

    @tool
    def run_dispatch(pantry_id: int) -> dict[str, Any]:
        """Ask the Dispatch specialist to find a driver who can deliver to
        `pantry_id` in time.

        Args:
            pantry_id: the pantry chosen by run_matching.
        """
        return propose_dispatch(offer_id, pantry_id, run_id=run_id).model_dump()

    return [run_intake, run_matching, run_dispatch]


def build_coordinator_agent(
    offer_id: int,
    run_id: int,
    model: Model | None = None,
    hooks: list[HookProvider] | None = None,
    session_manager: SessionManager | None = None,
) -> Agent:
    """Construct the Coordinator agent for one offer/run.

    Pass `session_manager` (see agents/sessions.py) so the agent remembers its
    own earlier conversation about this offer across separate run_case() calls
    — e.g. it recalls exactly what it already tried when a driver declines and
    the worker wakes it up again.
    """
    tools = [
        *_build_specialist_tools(offer_id, run_id),
        *build_action_tools(offer_id),
        build_ask_admin_tool(offer_id),
        notify_user,
        recall_facts,
        remember_fact,
    ]
    return Agent(
        model=model or build_model(),
        name="coordinator",
        system_prompt=COORDINATOR_SYSTEM_PROMPT,
        tools=tools,
        hooks=hooks or [],
        session_manager=session_manager,
    )
