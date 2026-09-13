"""Delete ALL PantryPilot data and recreate empty tables.

Usage (from the project folder):
    python -m scripts.reset_db --yes
"""

import argparse

from pantrypilot.database import create_tables, drop_tables, engine


def reset_database() -> None:
    """Drop every table, then create them again, empty."""
    drop_tables()
    create_tables()


def main() -> None:
    """Parse the command line and reset only if --yes was given."""
    parser = argparse.ArgumentParser(description="Delete all data and recreate empty tables.")
    parser.add_argument("--yes", action="store_true", help="confirm you really want to delete everything")
    args = parser.parse_args()

    if not args.yes:
        print("This deletes ALL PantryPilot data. Run again with --yes to confirm.")
        return

    reset_database()
    print(f"Database reset. Empty tables created in: {engine.url.database}")


if __name__ == "__main__":
    main()
