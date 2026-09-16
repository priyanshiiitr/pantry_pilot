"""Turns on OpenTelemetry tracing for the agents, controlled by `.env`.

A "trace" is a timeline of one request's work — here, one agent run — broken
into named "spans" (one model call, one tool call, ...). Strands emits these
automatically once tracing is enabled; we don't have to instrument anything
ourselves. This is what would feed CloudWatch/X-Ray in a real AWS deployment
(see docs/aws-deployment.md) — locally, it just prints to the terminal.
"""

import logging

from pantrypilot.config import settings

logger = logging.getLogger(__name__)

_already_configured = False


def configure_tracing() -> None:
    """Turn on console tracing if OTEL_CONSOLE=true in `.env`. Safe to call more
    than once — only sets up the exporter the first time.

    Call this once, near the top of any entrypoint that runs agents (scripts,
    the worker) — see scripts/try_matching.py and worker/__main__.py.
    """
    global _already_configured
    if _already_configured or not settings.otel_console:
        return

    from strands.telemetry import StrandsTelemetry

    StrandsTelemetry().setup_console_exporter()
    _already_configured = True
    logger.info("OpenTelemetry console tracing enabled (OTEL_CONSOLE=true).")
