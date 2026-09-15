"""Tests for services/activity_log.py and the hook's formatting helpers (Step 7).

These never call a real AI model — they test the plain database-writing code and
the pure string-formatting functions the hook uses.
"""

import pytest
from sqlalchemy import select

from pantrypilot.agents.hooks.reasoning_log_hook import _format_input, _summarize_result
from pantrypilot.models import AgentLog, AgentRun
from pantrypilot.services.activity_log import finish_agent_run, list_recent_log_entries, log_event, start_agent_run


def test_start_agent_run_creates_a_row(db_session) -> None:
    """start_agent_run saves a new agent_runs row and returns its id."""
    run_id = start_agent_run(trigger="manual", offer_id=None)

    run = db_session.get(AgentRun, run_id)
    assert run is not None
    assert run.offer_id is None
    assert run.finished_at is None


def test_finish_agent_run_records_outcome(db_session) -> None:
    """finish_agent_run fills in finished_at, stop_reason and outcome."""
    run_id = start_agent_run(trigger="manual", offer_id=None)

    finish_agent_run(run_id, stop_reason="end_turn", outcome={"chosen_pantry_id": 2})

    run = db_session.get(AgentRun, run_id)
    assert run.finished_at is not None
    assert run.stop_reason == "end_turn"
    assert run.outcome == {"chosen_pantry_id": 2}


@pytest.mark.usefixtures("db_session")  # activates the temp-database swap; the test itself needs no session
def test_finish_agent_run_on_missing_run_does_nothing() -> None:
    """Finishing a run id that doesn't exist should not raise."""
    finish_agent_run(999999, stop_reason="end_turn")  # must not raise


def test_log_event_creates_a_readable_row(db_session) -> None:
    """log_event saves a row with all the given fields."""
    run_id = start_agent_run(trigger="manual", offer_id=None)

    log_event(run_id, None, "matching", "tool_call", "Calling get_offer(offer_id=3)", tool_name="get_offer")

    entry = db_session.scalar(select(AgentLog).where(AgentLog.run_id == run_id))
    assert entry.summary == "Calling get_offer(offer_id=3)"
    assert entry.tool_name == "get_offer"
    assert entry.event_type == "tool_call"


def test_list_recent_log_entries_orders_newest_first(db_session) -> None:
    """The activity feed shows the newest entries first."""
    run_id = start_agent_run(trigger="manual")
    log_event(run_id, None, "matching", "tool_call", "first")
    log_event(run_id, None, "matching", "tool_call", "second")

    entries = list_recent_log_entries(db_session)

    assert [entry.summary for entry in entries[:2]] == ["second", "first"]


def test_format_input_renders_keyword_style() -> None:
    """Tool input dicts render as readable key=value pairs."""
    assert _format_input({"pantry_id": 3, "extra_kg": 12}) == "pantry_id=3, extra_kg=12"


def test_format_input_handles_no_arguments() -> None:
    """A tool with no arguments renders as an empty string, not an error."""
    assert _format_input({}) == ""


def test_summarize_result_extracts_text_content() -> None:
    """A normal ToolResult's text content becomes the summary."""
    result = {"status": "success", "content": [{"text": "5 pantries found"}], "toolUseId": "x"}

    assert _summarize_result(result, None) == "5 pantries found"


def test_summarize_result_extracts_json_content() -> None:
    """JSON content blocks are rendered as JSON text."""
    result = {"status": "success", "content": [{"json": {"pantry_id": 1}}], "toolUseId": "x"}

    assert _summarize_result(result, None) == '{"pantry_id": 1}'


def test_summarize_result_handles_exception() -> None:
    """When the tool raised, the exception message is used instead of the (missing) result."""
    assert _summarize_result(None, ValueError("no pantry 99")) == "error: no pantry 99"


def test_summarize_result_truncates_long_text() -> None:
    """A very long tool result gets truncated so the timeline stays readable."""
    long_text = "x" * 500
    result = {"status": "success", "content": [{"text": long_text}], "toolUseId": "x"}

    summary = _summarize_result(result, None)

    assert len(summary) < 350
    assert summary.endswith("…")
