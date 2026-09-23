"""Manually run the full agent team (Coordinator + specialists) on one offer.

Unlike scripts/try_matching.py (Matching agent only, nothing saved), this
actually assigns a pantry, dispatches a driver, and updates the database — the
same thing the background worker (Step 9) will do automatically.

Usage (from the project folder):
    python -m scripts.run_agent_once --offer 1
"""

import argparse

from pantrypilot import database
from pantrypilot.agents.console import ensure_utf8_console
from pantrypilot.agents.runner import run_case
from pantrypilot.agents.schemas import CaseUpdate
from pantrypilot.agents.telemetry import configure_tracing
from pantrypilot.services.decisions import list_pending_decisions


def print_update(update: CaseUpdate) -> None:
    """Print a CaseUpdate in a readable way."""
    print("\n" + "=" * 70)
    print("CASE UPDATE — the agent finished on its own")
    print("=" * 70)
    print(f"Status: {update.status}")
    print(f"\nSummary (shown to the restaurant):\n  {update.summary}")
    print(f"\nFull reasoning:\n  {update.reasoning}")
    print("=" * 70 + "\n")


def print_pending_decision(offer_id: int) -> None:
    """Print the question the agent paused on, when it asked for a human instead.

    run_case returns None in that case (the conversation is genuinely suspended
    mid-tool-call, see agents/tools/human_tools.py), so there is no CaseUpdate to
    show — the decision card it wrote is the actual result.
    """
    with database.SessionLocal() as session:
        decision = list_pending_decisions(session)[0]
        card = decision.card

        print("\n" + "=" * 70)
        print("PAUSED — the agent stopped to ask a human")
        print("=" * 70)
        print(f"Decision #{decision.id} on offer #{offer_id}   urgency: {card.get('urgency', 'unknown')}")
        print(f"\n{card.get('title', '(no title)')}")
        print(f"\nSituation:\n  {card.get('situation', '')}")
        print(f"\nWhy it won't decide alone:\n  {card.get('reasoning', '')}")
        print("\nOptions it wrote for you:")
        for option in card.get("options", []):
            print(f"  - {option.get('label')}")
            print(f"      consequence: {option.get('consequence')}")
        print(f"\nIts recommendation:\n  {card.get('recommended_option', '')}")
        print("\nAnswer it at http://localhost:5173/admin/decisions — the worker will")
        print("then resume this exact paused conversation with your answer.")
        print("=" * 70 + "\n")


def main() -> None:
    """Parse the command line, run the full agent team, and print the result."""
    ensure_utf8_console()  # see agents/console.py — avoids a Windows print crash
    configure_tracing()  # prints OpenTelemetry spans if OTEL_CONSOLE=true in .env

    parser = argparse.ArgumentParser(description="Run the full agent team on one offer.")
    parser.add_argument("--offer", type=int, required=True, help="id of the offer to process")
    args = parser.parse_args()

    print(f"Running the Coordinator and its team on offer #{args.offer}...")
    print("(Everything the agents do — every tool call and decision — streams below.)\n")

    update = run_case(args.offer)
    if update is None:
        print_pending_decision(args.offer)
    else:
        print_update(update)


if __name__ == "__main__":
    main()
