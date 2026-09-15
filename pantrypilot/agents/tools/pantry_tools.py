"""Tools for finding and evaluating pantries: distance, profile, capacity, fairness."""

from datetime import timedelta

from sqlalchemy import func, select
from strands import tool

from pantrypilot import database
from pantrypilot.config import settings
from pantrypilot.database import utc_now
from pantrypilot.models import Delivery, Pantry
from pantrypilot.services.fairness import COUNTED_DELIVERY_STATUSES, fairness_snapshot
from pantrypilot.services.geo import haversine_km, is_open_now


@tool
def find_nearby_pantries(lat: float, lon: float, radius_km: float = 15.0) -> list[dict]:
    """Find pantries within `radius_km` of a location, nearest first.

    Only pantries currently accepting donations are returned. This tells you WHO
    is nearby, not whether they can take THIS offer — use get_pantry_profile and
    check_pantry_capacity for that.

    Args:
        lat: latitude of the location to search from (e.g. the restaurant's).
        lon: longitude of the location to search from.
        radius_km: how far to search, in kilometers.
    """
    with database.SessionLocal() as session:
        pantries = list(session.scalars(select(Pantry).where(Pantry.accepting_donations.is_(True))))

    nearby = []
    for pantry in pantries:
        distance_km = haversine_km(lat, lon, pantry.lat, pantry.lon)
        if distance_km <= radius_km:
            nearby.append({"pantry_id": pantry.id, "name": pantry.name, "distance_km": round(distance_km, 1)})

    nearby.sort(key=lambda entry: entry["distance_km"])
    return nearby


@tool
def get_pantry_profile(pantry_id: int) -> dict:
    """Get one pantry's storage, dietary restrictions, opening hours and notes.

    Args:
        pantry_id: the id of the pantry to look up.
    """
    with database.SessionLocal() as session:
        pantry = session.get(Pantry, pantry_id)
        if pantry is None:
            return {"error": f"No pantry with id {pantry_id}."}
        return {
            "pantry_id": pantry.id,
            "name": pantry.name,
            "address": pantry.address,
            "lat": pantry.lat,
            "lon": pantry.lon,
            "has_fridge": pantry.has_fridge,
            "has_freezer": pantry.has_freezer,
            "dietary_restrictions": pantry.dietary_restrictions,
            "opening_hours": pantry.opening_hours,
            "is_open_right_now": is_open_now(pantry.opening_hours, utc_now(), settings.city_timezone),
            "accepting_donations": pantry.accepting_donations,
            "notes": pantry.notes,
        }


@tool
def check_pantry_capacity(pantry_id: int) -> dict:
    """Check how much of a pantry's daily capacity is already committed today.

    Args:
        pantry_id: the id of the pantry to check.
    """
    with database.SessionLocal() as session:
        pantry = session.get(Pantry, pantry_id)
        if pantry is None:
            return {"error": f"No pantry with id {pantry_id}."}

        today_start = utc_now() - timedelta(hours=24)  # a rolling 24h window, simple and good enough for a demo
        committed_today = session.scalar(
            select(func.sum(Delivery.kg)).where(
                Delivery.pantry_id == pantry_id,
                Delivery.status.in_(COUNTED_DELIVERY_STATUSES),
                Delivery.created_at >= today_start,
            )
        )
        committed_today = float(committed_today or 0.0)

        return {
            "pantry_id": pantry_id,
            "capacity_kg_per_day": pantry.capacity_kg_per_day,
            "committed_last_24h_kg": round(committed_today, 1),
            "remaining_kg_today": round(max(pantry.capacity_kg_per_day - committed_today, 0.0), 1),
        }


@tool
def calculate_fairness_score(pantry_id: int, extra_kg: float) -> dict:
    """See how this pantry's recent deliveries compare with other pantries, and how
    adding `extra_kg` more would change that. Use this to avoid giving one pantry
    far more than its fair share while others get little.

    Args:
        pantry_id: the id of the pantry to check.
        extra_kg: how many kg this potential new delivery would add.
    """
    with database.SessionLocal() as session:
        return fairness_snapshot(session, pantry_id, extra_kg)
