

"""Tests for agents/sessions.py — the per-offer agent conversation files.

These use tmp_path rather than the real data/sessions/, so a test run can never
delete a conversation a live agent is mid-way through.
"""


def test_clearing_sessions_removes_every_saved_conversation(tmp_path, monkeypatch) -> None:
    """A database reset restarts offer ids, so surviving sessions become wrong.

    Without this, the next offer #15 would load the previous offer #15's
    conversation and the agent would confidently "remember" work it never did on
    food that no longer exists.
    """
    from pantrypilot.agents import sessions

    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "offer-15").mkdir()
    (tmp_path / "sessions" / "offer-15" / "state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sessions" / "stray.json").write_text("{}", encoding="utf-8")

    removed = sessions.clear_agent_sessions()

    assert removed == 2
    assert list((tmp_path / "sessions").iterdir()) == []


def test_clearing_sessions_when_there_are_none_is_fine(tmp_path, monkeypatch) -> None:
    """A fresh clone has no sessions directory at all — that isn't an error."""
    from pantrypilot.agents import sessions

    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "never-created")

    assert sessions.clear_agent_sessions() == 0
