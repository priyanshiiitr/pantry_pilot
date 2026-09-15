"""Manually run the full agent team (Coordinator + specialists) on one offer.

Unlike scripts/try_matching.py (Matching agent only, nothing saved), this
actually assigns a pantry, dispatches a driver, and updates the database — the
same thing the background worker (Step 9) will do automatically.

Usage (from the project folder):
    python -m scripts.run_agent_once --offer 1
"""

import argparse

from pantrypilot.agents.console import ensure_utf8_console
from pantrypilot.agents.runner import run_case
from pantrypilot.agents.schemas import CaseUpdate


def print_update(update: CaseUpdate) -> None:
    """Print a CaseUpdate in a readable way."""
    print("\n" + "=" * 70)
    print("CASE UPDATE")
    print("=" * 70)
    print(f"Status: {update.status}")
    print(f"\nSummary (shown to the restaurant):\n  {update.summary}")
    print(f"\nFull reasoning:\n  {update.reasoning}")
    print("=" * 70 + "\n")


def main() -> None:
    """Parse the command line, run the full agent team, and print the result."""
    ensure_utf8_console()  # see agents/console.py — avoids a Windows print crash

    parser = argparse.ArgumentParser(description="Run the full agent team on one offer.")
    parser.add_argument("--offer", type=int, required=True, help="id of the offer to process")
    args = parser.parse_args()

    print(f"Running the Coordinator and its team on offer #{args.offer}...")
    print("(Everything the agents do — every tool call and decision — streams below.)\n")

    update = run_case(args.offer)
    print_update(update)


if __name__ == "__main__":
    main()
