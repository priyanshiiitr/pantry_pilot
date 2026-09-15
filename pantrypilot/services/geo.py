"""Distance, rough travel time, and "is this place open right now?".

DETERMINISTIC CODE: plain math and calendar arithmetic. No AI involved — the
agents call these through tools, but the numbers themselves are just computed.
"""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

EARTH_RADIUS_KM = 6371.0

# A simple average for city driving with stops and lights. This is a rough demo
# estimate, not real traffic-aware routing (there's no routing API in this project).
AVERAGE_CITY_SPEED_KMH = 25.0
LOADING_BUFFER_MINUTES = 5.0  # time to park, load/unload — added on top of driving time

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # datetime.weekday(): Monday=0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line ("as the crow flies") distance between two points, in kilometers.

    This is the haversine formula, which treats the Earth as a sphere. It's a good
    enough estimate for a demo; real routing would follow actual roads.
    """
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = (math.radians(value) for value in (lat1, lon1, lat2, lon2))
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def estimate_travel_minutes(distance_km: float, average_speed_kmh: float = AVERAGE_CITY_SPEED_KMH) -> float:
    """A rough estimate of driving time: distance ÷ average speed, plus a loading buffer."""
    return (distance_km / average_speed_kmh) * 60 + LOADING_BUFFER_MINUTES


def is_open_now(weekly_hours: dict[str, list[str]], moment_utc: datetime, timezone_name: str) -> bool:
    """Whether a place following `weekly_hours` (see models/places.py) is open at `moment_utc`.

    `weekly_hours` looks like {"mon": ["09:00", "17:00"], ...} — a missing day means closed.
    """
    local_moment = moment_utc.astimezone(ZoneInfo(timezone_name))
    todays_hours = weekly_hours.get(_WEEKDAY_KEYS[local_moment.weekday()])
    if not todays_hours:
        return False
    open_time, close_time = todays_hours
    current_time = local_moment.strftime("%H:%M")
    return open_time <= current_time <= close_time
