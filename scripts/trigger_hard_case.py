"""Deliberately post an offer with real characteristics that SHOULD make a
responsible agent ask a human for help — useful for a demo, or for testing the
Decisions inbox without waiting for a naturally hard case to come along.

This does NOT force an escalation in code. It only sets up a realistic, hard
situation; whether the agent actually calls ask_admin is up to its own
reasoning. If it finds a safe way through on its own, that's a legitimate
outcome too — the activity log will show why.

Usage (from the project folder, after `python -m scripts.seed_demo`):
    python -m scripts.trigger_hard_case --scenario spoilage
    python -m scripts.trigger_hard_case --scenario no_drivers
    python -m scripts.trigger_hard_case --scenario fairness
    python -m scripts.trigger_hard_case --scenario unclear_allergens
"""

import argparse
from datetime import timedelta

from sqlalchemy import select

from pantrypilot.database import SessionLocal, create_tables, utc_now
from pantrypilot.models import Offer, Restaurant

# Each scenario is a real, demo-friendly reason a coordinator might need to ask
# a human — not a rigged input designed to trip a specific code path.
SCENARIOS: dict[str, dict[str, object]] = {
    "spoilage": {
        "title": "Fresh cream pastries — extremely tight window",
        "description": (
            "80 fresh cream-filled pastries, made 3 hours ago, must be refrigerated "
            "immediately or they're unsafe to eat. Very little time to collect them."
        ),
        "quantity_text": "80 pastries",
        "allergen_notes": "dairy, eggs, gluten",
        "deadline_minutes": 10,
    },
    "no_drivers": {
        "title": "Large catering surplus, very late at night",
        "description": (
            "200 servings of catering leftovers from a corporate event, still good, "
            "but needs pickup very late tonight when most volunteers are off duty."
        ),
        "quantity_text": "200 servings",
        "allergen_notes": "varies — mixed catering trays",
        "deadline_minutes": 45,
    },
    "fairness": {
        "title": "Another large donation to an already-busy area",
        "description": (
            "150 kg of shelf-stable canned goods, no special handling needed, but the "
            "closest pantries have already received a lot of food this week."
        ),
        "quantity_text": "150 kg canned goods",
        "allergen_notes": "none listed",
        "deadline_minutes": 240,
    },
    "unclear_allergens": {
        "title": "Mystery mixed leftovers, vague description",
        "description": (
            "Assorted leftovers from tonight's service, a bit of everything — not sure "
            "exactly what's in each container. Some might have nuts, unconfirmed."
        ),
        "quantity_text": "a few trays, unclear amount",
        "allergen_notes": "unclear — possibly nuts, unconfirmed",
        "deadline_minutes": 90,
    },
}


def create_hard_case_offer(scenario_name: str) -> int:
    """Post the offer for `scenario_name` from the first seeded restaurant, and return its id."""
    scenario = SCENARIOS[scenario_name]
    with SessionLocal() as session:
        restaurant = session.scalars(select(Restaurant)).first()
        if restaurant is None:
            raise RuntimeError("No restaurant found — run `python -m scripts.seed_demo` first.")

        offer = Offer(
            restaurant=restaurant,
            title=scenario["title"],
            description=scenario["description"],
            quantity_text=scenario["quantity_text"],
            allergen_notes=scenario["allergen_notes"],
            pickup_deadline=utc_now() + timedelta(minutes=scenario["deadline_minutes"]),
        )
        session.add(offer)
        session.commit()
        return offer.id


def main() -> None:
    """Parse the command line and post the chosen scenario's offer."""
    parser = argparse.ArgumentParser(description="Post a demo offer likely to need human escalation.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True, help="which hard case to create")
    args = parser.parse_args()

    create_tables()
    offer_id = create_hard_case_offer(args.scenario)

    print(f"Created offer #{offer_id} for scenario '{args.scenario}'.")
    print("It's posted and waiting. Either:")
    print("  - start the worker (python -m pantrypilot.worker) and it'll be picked up within 15 seconds, or")
    print(f"  - run it right now:  python -m scripts.run_agent_once --offer {offer_id}")


if __name__ == "__main__":
    main()
