"""Tests for pantrypilot/services/geo.py (Step 6) — pure math, no AI, no database."""

from datetime import datetime, timezone

from pantrypilot.services.geo import estimate_travel_minutes, haversine_km, is_open_now

SEATTLE_DOWNTOWN = (47.6062, -122.3321)
BELLEVUE = (47.6101, -122.2015)  # roughly 10 km east of downtown Seattle

MONDAY_9AM_UTC = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)  # 2026-09-14 is a Monday


def test_haversine_distance_to_self_is_zero() -> None:
    """The distance between a point and itself is 0."""
    assert haversine_km(*SEATTLE_DOWNTOWN, *SEATTLE_DOWNTOWN) == 0.0


def test_haversine_distance_is_roughly_correct() -> None:
    """Downtown Seattle to Bellevue is roughly 10 km as the crow flies."""
    distance = haversine_km(*SEATTLE_DOWNTOWN, *BELLEVUE)
    assert 8.0 < distance < 13.0


def test_estimate_travel_minutes_increases_with_distance() -> None:
    """A longer trip takes longer, and even 0 km still costs the loading buffer."""
    assert estimate_travel_minutes(0) > 0
    assert estimate_travel_minutes(20) > estimate_travel_minutes(5)


def test_is_open_now_true_during_business_hours() -> None:
    """A pantry open Mon 09:00-17:00 is open at 09:00 on a Monday."""
    hours = {"mon": ["09:00", "17:00"]}
    assert is_open_now(hours, MONDAY_9AM_UTC, "UTC") is True


def test_is_open_now_false_outside_business_hours() -> None:
    """The same pantry is closed at 08:00, one hour before opening."""
    hours = {"mon": ["09:00", "17:00"]}
    too_early = MONDAY_9AM_UTC.replace(hour=8)
    assert is_open_now(hours, too_early, "UTC") is False


def test_is_open_now_false_on_a_day_not_listed() -> None:
    """A day missing from opening_hours means closed."""
    hours = {"mon": ["09:00", "17:00"]}  # no Sunday
    sunday = MONDAY_9AM_UTC.replace(day=13)  # 2026-09-13 is the Sunday before
    assert is_open_now(hours, sunday, "UTC") is False


def test_is_open_now_respects_timezone() -> None:
    """09:00 UTC is 02:00 in Seattle in September (UTC-7 during daylight saving),
    so a pantry open 09:00-17:00 Seattle-local time is NOT open at 09:00 UTC."""
    hours = {"mon": ["09:00", "17:00"]}
    assert is_open_now(hours, MONDAY_9AM_UTC, "America/Los_Angeles") is False
