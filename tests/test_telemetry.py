"""Tests for agents/telemetry.py (Step 13).

No AI involved — just checking that configure_tracing() only sets up the
OpenTelemetry exporter when OTEL_CONSOLE=true, and only does it once.
"""

import pantrypilot.agents.telemetry as telemetry_module
from pantrypilot.agents.telemetry import configure_tracing
from pantrypilot.config import settings


def test_configure_tracing_does_nothing_when_disabled(monkeypatch) -> None:
    """With OTEL_CONSOLE=false (the default), calling this is a safe no-op."""
    monkeypatch.setattr(settings, "otel_console", False)
    monkeypatch.setattr(telemetry_module, "_already_configured", False)

    configure_tracing()  # must not raise, must not import strands.telemetry

    assert telemetry_module._already_configured is False


def test_configure_tracing_sets_up_the_exporter_once(monkeypatch) -> None:
    """With OTEL_CONSOLE=true, the exporter is set up exactly once even if called twice."""
    monkeypatch.setattr(settings, "otel_console", True)
    monkeypatch.setattr(telemetry_module, "_already_configured", False)

    calls: list[str] = []

    class FakeStrandsTelemetry:
        def setup_console_exporter(self) -> None:
            calls.append("setup")

    monkeypatch.setattr("strands.telemetry.StrandsTelemetry", FakeStrandsTelemetry)

    configure_tracing()
    configure_tracing()  # second call should be a no-op now

    assert calls == ["setup"]
    assert telemetry_module._already_configured is True
