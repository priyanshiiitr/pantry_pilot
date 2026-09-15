"""Fixes a Windows-only gotcha that otherwise crashes agent runs.

Strands' default callback prints the model's reasoning to the terminal live, as it
streams in. The AI model sometimes generates Unicode characters (narrow spaces,
smart quotes, em dashes...) that Windows' default console encoding (cp1252) cannot
print. Without this fix, that raises UnicodeEncodeError mid-stream, which then
cascades into confusing async-generator cleanup errors — it can look like the
agent is stuck looping, when what actually happened is a crashed print() call.

Call ensure_utf8_console() once at the top of any script or worker entrypoint
that runs an agent and prints its output live.
"""

import sys


def ensure_utf8_console() -> None:
    """Make stdout/stderr accept any Unicode character the model might print.

    Safe to call more than once, and a harmless no-op on streams that don't
    support reconfiguring (e.g. output already redirected to a file).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
