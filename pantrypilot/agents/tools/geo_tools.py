"""A shared tool for estimating driving time between two points.

Used by the Matching agent (is a pantry reachable before the food spoils?) and,
from Step 8, the Dispatch agent (can this driver make it in time?).
"""

from strands import tool

from pantrypilot.services.geo import estimate_travel_minutes, haversine_km


@tool
def estimate_travel_time(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> dict:
    """Estimate driving time between two points, in minutes.

    This uses straight-line distance and an average city speed — not real traffic
    routing — but it's good enough for judging whether someone can make it in time.

    Args:
        from_lat: starting latitude.
        from_lon: starting longitude.
        to_lat: destination latitude.
        to_lon: destination longitude.
    """
    distance_km = haversine_km(from_lat, from_lon, to_lat, to_lon)
    return {"distance_km": round(distance_km, 1), "estimated_minutes": round(estimate_travel_minutes(distance_km))}
