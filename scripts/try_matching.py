"""Manually run the Matching agent against one offer and print its decision.

This is the first time an AI agent actually reasons in this project — nothing is
wired into the app yet (no button, no background job). It's here so you can watch
the agent think before we build anything around it.

Usage (from the project folder):
    python -m scripts.try_matching --offer 1
"""

import argparse

from pantrypilot.agents.console import ensure_utf8_console
from pantrypilot.agents.matching_agent import propose_match
from pantrypilot.agents.schemas import MatchProposal


def print_proposal(proposal: MatchProposal) -> None:
    """Print a MatchProposal in a readable way."""
    print("\n" + "=" * 70)
    print("MATCH PROPOSAL")
    print("=" * 70)

    if proposal.chosen_pantry_id is not None:
        print(f"Chosen pantry: #{proposal.chosen_pantry_id}")
    else:
        print("Chosen pantry: NONE — the agent could not find a safe, timely match.")
    print(f"Confident to proceed: {proposal.confident_to_proceed}")

    print("\nReasoning:")
    print(f"  {proposal.reasoning}")

    if proposal.concerns:
        print("\nConcerns for a human to double-check:")
        for concern in proposal.concerns:
            print(f"  - {concern}")

    print("\nCandidates considered:")
    for candidate in proposal.ranked_candidates:
        print(f"  #{candidate.pantry_id} {candidate.pantry_name}")
        print(f"      {candidate.reasoning}")
    print("=" * 70 + "\n")


def main() -> None:
    """Parse the command line, run the agent, and print its decision."""
    ensure_utf8_console()  # see agents/console.py — avoids a Windows print crash

    parser = argparse.ArgumentParser(description="Run the Matching agent on one offer.")
    parser.add_argument("--offer", type=int, required=True, help="id of the offer to match")
    args = parser.parse_args()

    print(f"Running the Matching agent on offer #{args.offer}...")
    print("(Everything the agent does — its tool calls and thinking — streams below.)\n")

    proposal = propose_match(args.offer)
    print_proposal(proposal)


if __name__ == "__main__":
    main()
