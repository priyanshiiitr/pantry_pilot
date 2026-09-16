"""Per-offer conversation memory for the Coordinator.

Without this, every time run_case() builds a fresh Coordinator Agent object, it
starts from a blank slate — even if this is the third time it's looking at the
same offer because a driver declined twice. With a Strands session manager
attached, the Agent reloads its own earlier conversation (what it tried, what it
called, what it concluded) before it even reads the new prompt. This is what
lets the agent genuinely remember "I already asked Sam, he declined" rather than
being told about it in a sentence and hoping it takes note.

We use FileSessionManager: sessions are saved as files under data/sessions/, one
per offer, so this survives the worker process restarting. (An AgentCore Memory
session manager could replace this for a real AWS deployment — same interface,
see docs/aws-deployment.md.)
"""

from strands.session import FileSessionManager

from pantrypilot.config import PROJECT_ROOT

SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"


def build_offer_session_manager(offer_id: int) -> FileSessionManager:
    """Build the session manager for one offer's Coordinator conversation.

    Same `offer_id` always maps to the same session file, so calling this again
    later (even from a different process) resumes the same conversation.
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return FileSessionManager(session_id=f"offer-{offer_id}", storage_dir=str(SESSIONS_DIR))
