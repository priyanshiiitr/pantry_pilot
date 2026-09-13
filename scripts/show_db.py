"""Print what's in the database: row counts per table, then the pantries and drivers.

Usage (from the project folder):
    python -m scripts.show_db
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pantrypilot.database import Base, SessionLocal, create_tables
from pantrypilot.models import Driver, Pantry, Restaurant


def count_rows_per_table(session: Session) -> dict[str, int]:
    """Return {table name: number of rows} for every table."""
    counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        counts[table.name] = session.scalar(select(func.count()).select_from(table)) or 0
    return counts


def print_counts(session: Session) -> None:
    """Print one line per table with its row count."""
    print("\nRows per table")
    print("--------------")
    for table_name, count in count_rows_per_table(session).items():
        print(f"  {table_name:<20} {count}")


def print_restaurants(session: Session) -> None:
    """Print every restaurant with its location."""
    print("\nRestaurants")
    print("-----------")
    for restaurant in session.scalars(select(Restaurant).order_by(Restaurant.id)):
        print(f"  #{restaurant.id} {restaurant.name:<26} {restaurant.address}")


def print_pantries(session: Session) -> None:
    """Print every pantry with capacity, storage and dietary restrictions."""
    print("\nPantries")
    print("--------")
    for pantry in session.scalars(select(Pantry).order_by(Pantry.id)):
        storage = "fridge" if pantry.has_fridge else "no fridge"
        if pantry.has_freezer:
            storage += "+freezer"
        restrictions = ", ".join(pantry.dietary_restrictions) or "none"
        print(
            f"  #{pantry.id} {pantry.name:<34} {pantry.capacity_kg_per_day:>5.0f} kg/day  "
            f"{storage:<16} restrictions: {restrictions}"
        )


def print_drivers(session: Session) -> None:
    """Print every driver with vehicle, capacity and duty status."""
    print("\nDrivers")
    print("-------")
    for driver in session.scalars(select(Driver).order_by(Driver.id)):
        duty = "on duty" if driver.on_duty else "OFF duty"
        cooler = "cooler" if driver.has_cooler else "no cooler"
        days = ", ".join(driver.availability.keys())
        print(
            f"  #{driver.id} {driver.name:<14} {driver.vehicle:<12} {driver.max_kg:>4.0f} kg  "
            f"{cooler:<10} {duty:<9} days: {days}"
        )


def main() -> None:
    """Open the database and print the overview."""
    create_tables()  # harmless if they exist; avoids errors on a brand-new database
    with SessionLocal() as session:
        print_counts(session)
        print_restaurants(session)
        print_pantries(session)
        print_drivers(session)


if __name__ == "__main__":
    main()
