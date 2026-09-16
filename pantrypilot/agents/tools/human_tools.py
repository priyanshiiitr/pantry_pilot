"""The Coordinator's escalation tool: genuinely pausing the agent to ask a human.

THIS is the human-in-the-loop centerpiece. `ask_admin` doesn't just log a note —
it calls `tool_context.interrupt(...)`, which halts the agent's event loop right
where it is. Strands returns control to whoever called the agent (see
agents/runner.py) with `result.stop_reason == "interrupt"`. Nothing continues
until a real admin picks an option and we resume the SAME conversation with
their answer — even if the whole worker process restarts in between, because
the interrupt state is saved by the per-offer session (agents/sessions.py).

Deliberately thin: this tool does no database writing itself. Saving the
decision card and resuming later are runner.py's job (see
agents/runner.py:_handle_agent_result and resume_case) — this keeps the
"where does this get persisted" logic in exactly one place.
"""

from typing import Any

from strands import tool
from strands.types.tools import AgentTool, ToolContext


def build_ask_admin_tool(offer_id: int) -> AgentTool:
    """Build the ask_admin tool, bound to `offer_id` so its interrupt name stays
    the same every time this offer's Coordinator needs to ask something — see
    agents/tools/action_tools.py for why tools are built as closures like this.
    """

    @tool(context=True)
    def ask_admin(
        tool_context: ToolContext,
        title: str,
        situation: str,
        reasoning: str,
        options: list[dict[str, str]],
        recommended_option: str,
        urgency: str,
    ) -> dict[str, Any]:
        """Pause and ask a human admin to make a judgment call you cannot safely
        make alone. Use this when: no pantry or driver can respond safely and in
        time, a dietary/safety concern you can't resolve, the best match would
        give one pantry far more than its fair share, or the offer is genuinely
        ambiguous or unsafe. This is not a failure — it's the responsible choice
        when you're genuinely stuck.

        Always propose 2-4 concrete, distinct options with their real
        consequences, and say which you'd recommend and why. You'll receive the
        admin's choice back as your tool result and can continue from there.

        Args:
            title: a short headline for the decision card, e.g. "No pantry can take this before it spoils".
            situation: the concrete facts a human needs to make this call — what you found, and why it matters.
            reasoning: why you can't responsibly decide this yourself.
            options: 2-4 choices, each a dict with "label" and "consequence" keys,
                e.g. [{"label": "Send to Riverside anyway", "consequence": "Arrives 20 min after closing."}].
            recommended_option: the label of the option you'd pick, plus a one-sentence why.
            urgency: "low", "medium", or "high" — how quickly this needs an answer.
        """
        card = {
            "title": title,
            "situation": situation,
            "reasoning": reasoning,
            "options": options,
            "recommended_option": recommended_option,
            "urgency": urgency,
        }
        # First call: raises InterruptException, which halts the agent (see module docstring).
        # Second call (after the admin answers and runner.resume_case() re-invokes the agent):
        # returns the admin's response instead of raising.
        admin_response = tool_context.interrupt(f"ask_admin_offer_{offer_id}", reason=card)
        return {"admin_decision": admin_response}

    return ask_admin
