"""Tests for agents/tools/geo_tools.py: estimate_travel_time.

No database, no LLM — just checking the tool shapes services/geo.py's numbers
correctly for the model to read.
"""

from pantrypilot.agents.tools.geo_tools import estimate_travel_time

SEATTLE_DOWNTOWN = (47.6062, -122.3321)
BELLEVUE = (47.6101, -122.2015)  # roughly 10 km east — see test_geo.py


def test_estimate_travel_time_returns_distance_and_minutes() -> None:
    """The tool reports both the distance and a rounded minutes estimate."""
    result = estimate_travel_time(
        from_lat=SEATTLE_DOWNTOWN[0], from_lon=SEATTLE_DOWNTOWN[1], to_lat=BELLEVUE[0], to_lon=BELLEVUE[1]
    )

    assert 8.0 < result["distance_km"] < 13.0
    assert result["estimated_minutes"] > 0
    assert isinstance(result["estimated_minutes"], int)  # rounded, not a raw float


def test_estimate_travel_time_for_the_same_point_is_just_the_buffer() -> None:
    """Zero distance still costs a small loading buffer, not zero minutes."""
    lat, lon = SEATTLE_DOWNTOWN
    result = estimate_travel_time(from_lat=lat, from_lon=lon, to_lat=lat, to_lon=lon)

    assert result["distance_km"] == 0.0
    assert result["estimated_minutes"] > 0
