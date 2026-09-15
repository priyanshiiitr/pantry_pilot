"""Turns Strands' tool-call lifecycle events into readable rows in the agent_log
table, so the admin "Agent activity" page can show exactly what an agent did —
without this file ever deciding anything itself.

This is what proves to a judge (or to you) that real reasoning happened: every
tool the agent chose to call, its inputs, and what came back, all timestamped.
"""

import json
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from pantrypilot.services.activity_log import log_event

_SUMMARY_MAX_LENGTH = 300


class ReasoningLogHook(HookProvider):
    """Attach one of these to an Agent to log every tool call it makes.

    Example:
        hook = ReasoningLogHook(run_id=run_id, offer_id=7, agent_name="matching")
        agent = Agent(..., hooks=[hook])
    """

    def __init__(self, run_id: int | None, offer_id: int | None, agent_name: str) -> None:
        """Set up the hook. `run_id` groups every log line under one agent_runs row."""
        self.run_id = run_id
        self.offer_id = offer_id
        self.agent_name = agent_name

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Tell Strands which events we want to hear about (required by HookProvider)."""
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool_call)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)

    def _on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Log that the agent is about to call a tool, and with what input."""
        tool_name = event.tool_use.get("name", "unknown_tool")
        tool_input = event.tool_use.get("input", {})
        log_event(
            self.run_id,
            self.offer_id,
            self.agent_name,
            "tool_call",
            f"Calling {tool_name}({_format_input(tool_input)})",
            tool_name=tool_name,
            details={"input": tool_input},
        )

    def _on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        """Log what a tool call returned (or the error, if it failed)."""
        tool_name = event.tool_use.get("name", "unknown_tool")
        summary_text = _summarize_result(event.result, event.exception)
        log_event(
            self.run_id,
            self.offer_id,
            self.agent_name,
            "tool_result",
            f"{tool_name} -> {summary_text}",
            tool_name=tool_name,
            details={
                "status": "error" if event.exception else _result_status(event.result),
                "duration_seconds": event.duration,
                "result": event.result if isinstance(event.result, dict) else str(event.result),
            },
        )


def _format_input(tool_input: dict[str, Any]) -> str:
    """Turn a tool's input dict into a short readable string, e.g. "pantry_id=3, extra_kg=12"."""
    return ", ".join(f"{key}={value!r}" for key, value in tool_input.items())


def _result_status(result: Any) -> str | None:
    """Read the "status" field off a ToolResult dict, if it looks like one."""
    return result.get("status") if isinstance(result, dict) else None


def _summarize_result(result: Any, exception: Exception | None) -> str:
    """Turn a tool's result (or exception) into a short readable string for the timeline.

    Defensive by design: Strands documents `result` as normally a ToolResult dict,
    but as an Exception object in some failure cases — so this never assumes a shape.
    """
    if exception is not None:
        return f"error: {exception}"
    if not isinstance(result, dict):
        return str(result)

    pieces: list[str] = []
    for block in result.get("content", []):
        if "text" in block:
            pieces.append(block["text"])
        elif "json" in block:
            pieces.append(json.dumps(block["json"]))
    text = " ".join(pieces) or "(no content)"

    if len(text) > _SUMMARY_MAX_LENGTH:
        text = text[:_SUMMARY_MAX_LENGTH] + "…"
    return text
