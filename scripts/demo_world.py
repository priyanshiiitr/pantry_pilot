"""The fake demo world: a Seattle-sized set of restaurants, pantries and drivers.

This file is ONLY data (no database code), so it's easy to read and edit.
All businesses, people, phone numbers and addresses are invented.
Locations are rough coordinates of real Seattle neighbourhoods so the map looks right.

The world is deliberately varied so the agents face real trade-offs:
- Hope Community Pantry already received a lot this week (fairness question).
- Riverside Food Bank can't take pork; Rainier Valley is halal-only; Northgate has nut allergies.
- U-District Student Pantry has no fridge (can't take perishables).
- West Seattle Night Shelter only opens in the evening.
- Sam Rivera only drives weekdays 09–17 and has declined evening runs before.
- Dana Brooks is off duty.
"""

from typing import Any

DEMO_PASSWORD: str = "demo1234"

WEEKDAYS: list[str] = ["mon", "tue", "wed", "thu", "fri"]
WEEKEND: list[str] = ["sat", "sun"]
ALL_DAYS: list[str] = WEEKDAYS + WEEKEND


def hours(days: list[str], open_time: str, close_time: str) -> dict[str, list[str]]:
    """Build weekly hours, e.g. hours(WEEKDAYS, "09:00", "17:00") → {"mon": ["09:00", "17:00"], ...}."""
    return {day: [open_time, close_time] for day in days}


ADMIN: dict[str, str] = {"email": "admin@pantrypilot.test", "display_name": "Casey (Coordinator)"}

RESTAURANTS: list[dict[str, Any]] = [
    {"email": "goldencrust@pantrypilot.test", "name": "Golden Crust Bakery",
     "address": "Capitol Hill, Seattle", "lat": 47.6148, "lon": -122.3203, "phone": "206-555-0101"},
    {"email": "harbordeli@pantrypilot.test", "name": "Harbor Deli",
     "address": "Downtown, Seattle", "lat": 47.6080, "lon": -122.3380, "phone": "206-555-0102"},
    {"email": "greenbowl@pantrypilot.test", "name": "Green Bowl Kitchen",
     "address": "Fremont, Seattle", "lat": 47.6512, "lon": -122.3501, "phone": "206-555-0103"},
    {"email": "sunrise@pantrypilot.test", "name": "Sunrise Grocery",
     "address": "Beacon Hill, Seattle", "lat": 47.5689, "lon": -122.3080, "phone": "206-555-0104"},
    {"email": "noodlehouse@pantrypilot.test", "name": "Noodle House 88",
     "address": "International District, Seattle", "lat": 47.5985, "lon": -122.3240, "phone": "206-555-0105"},
]

PANTRIES: list[dict[str, Any]] = [
    {"email": "hope@pantrypilot.test", "name": "Hope Community Pantry",
     "address": "Capitol Hill, Seattle", "lat": 47.6205, "lon": -122.3160, "phone": "206-555-0201",
     "capacity_kg_per_day": 120, "has_fridge": True, "has_freezer": False, "dietary_restrictions": [],
     "opening_hours": hours(WEEKDAYS + ["sat"], "09:00", "18:00"),
     "notes": "Busy neighbourhood pantry close to many donors."},
    {"email": "riverside@pantrypilot.test", "name": "Riverside Food Bank",
     "address": "Georgetown, Seattle", "lat": 47.5470, "lon": -122.3210, "phone": "206-555-0202",
     "capacity_kg_per_day": 300, "has_fridge": True, "has_freezer": True, "dietary_restrictions": ["no_pork"],
     "opening_hours": hours(WEEKDAYS, "08:00", "16:00"),
     "notes": "Largest storage in the city. Serves a community that avoids pork."},
    {"email": "ballard@pantrypilot.test", "name": "Ballard Family Shelter",
     "address": "Ballard, Seattle", "lat": 47.6680, "lon": -122.3840, "phone": "206-555-0203",
     "capacity_kg_per_day": 80, "has_fridge": True, "has_freezer": False, "dietary_restrictions": [],
     "opening_hours": hours(ALL_DAYS, "07:00", "21:00"),
     "notes": "Shelter kitchen; serves dinner at 18:00."},
    {"email": "udistrict@pantrypilot.test", "name": "U-District Student Pantry",
     "address": "University District, Seattle", "lat": 47.6610, "lon": -122.3130, "phone": "206-555-0204",
     "capacity_kg_per_day": 60, "has_fridge": False, "has_freezer": False, "dietary_restrictions": [],
     "opening_hours": hours(WEEKDAYS, "11:00", "19:00"),
     "notes": "No refrigeration: shelf-stable food only."},
    {"email": "rainier@pantrypilot.test", "name": "Rainier Valley Community Kitchen",
     "address": "Columbia City, Seattle", "lat": 47.5600, "lon": -122.2860, "phone": "206-555-0205",
     "capacity_kg_per_day": 150, "has_fridge": True, "has_freezer": False, "dietary_restrictions": ["halal_only"],
     "opening_hours": hours(ALL_DAYS, "10:00", "20:00"),
     "notes": "Community kitchen attached to a mosque; halal food only."},
    {"email": "northgate@pantrypilot.test", "name": "Northgate Senior Center",
     "address": "Northgate, Seattle", "lat": 47.7070, "lon": -122.3250, "phone": "206-555-0206",
     "capacity_kg_per_day": 50, "has_fridge": True, "has_freezer": False, "dietary_restrictions": ["no_nuts"],
     "opening_hours": hours(WEEKDAYS, "09:00", "15:00"),
     "notes": "Several residents have severe nut allergies."},
    {"email": "westseattle@pantrypilot.test", "name": "West Seattle Night Shelter",
     "address": "West Seattle, Seattle", "lat": 47.5660, "lon": -122.3870, "phone": "206-555-0207",
     "capacity_kg_per_day": 100, "has_fridge": True, "has_freezer": True, "dietary_restrictions": [],
     "opening_hours": hours(ALL_DAYS, "17:00", "23:00"),
     "notes": "Evening-only shelter."},
]

DRIVERS: list[dict[str, Any]] = [
    {"email": "sam@pantrypilot.test", "name": "Sam Rivera", "lat": 47.6230, "lon": -122.3190,
     "phone": "206-555-0301", "service_radius_km": 10, "vehicle": "car", "max_kg": 80, "has_cooler": True,
     "availability": hours(WEEKDAYS, "09:00", "17:00"), "on_duty": True},
    {"email": "maya@pantrypilot.test", "name": "Maya Chen", "lat": 47.6700, "lon": -122.3800,
     "phone": "206-555-0302", "service_radius_km": 12, "vehicle": "hatchback", "max_kg": 60, "has_cooler": False,
     "availability": hours(ALL_DAYS, "08:00", "20:00"), "on_duty": True},
    {"email": "jordan@pantrypilot.test", "name": "Jordan Lee", "lat": 47.6050, "lon": -122.3350,
     "phone": "206-555-0303", "service_radius_km": 15, "vehicle": "cargo van", "max_kg": 150, "has_cooler": True,
     "availability": hours(ALL_DAYS, "06:00", "22:00"), "on_duty": True},
    {"email": "alex@pantrypilot.test", "name": "Alex Kim", "lat": 47.6590, "lon": -122.3150,
     "phone": "206-555-0304", "service_radius_km": 6, "vehicle": "cargo bike", "max_kg": 20, "has_cooler": False,
     "availability": hours(WEEKDAYS, "12:00", "18:00"), "on_duty": True},
    {"email": "fatima@pantrypilot.test", "name": "Fatima Noor", "lat": 47.5590, "lon": -122.2900,
     "phone": "206-555-0305", "service_radius_km": 12, "vehicle": "SUV", "max_kg": 100, "has_cooler": True,
     "availability": hours(ALL_DAYS, "10:00", "21:00"), "on_duty": True},
    {"email": "chris@pantrypilot.test", "name": "Chris Walker", "lat": 47.5630, "lon": -122.3860,
     "phone": "206-555-0306", "service_radius_km": 10, "vehicle": "pickup truck", "max_kg": 90, "has_cooler": False,
     "availability": {**hours(WEEKDAYS, "17:00", "23:00"), **hours(WEEKEND, "09:00", "21:00")}, "on_duty": True},
    {"email": "dana@pantrypilot.test", "name": "Dana Brooks", "lat": 47.7060, "lon": -122.3280,
     "phone": "206-555-0307", "service_radius_km": 14, "vehicle": "minivan", "max_kg": 70, "has_cooler": True,
     "availability": hours(WEEKDAYS, "07:00", "15:00"), "on_duty": False},
    {"email": "luis@pantrypilot.test", "name": "Luis Ortega", "lat": 47.5490, "lon": -122.3190,
     "phone": "206-555-0308", "service_radius_km": 20, "vehicle": "box truck", "max_kg": 200, "has_cooler": True,
     "availability": hours(["mon", "wed", "fri"], "09:00", "17:00"), "on_duty": True},
]

# A week of completed deliveries, so fairness numbers and driver history mean something.
# "hour" is the local pickup hour. "declined_by" = a driver who said no before someone else took it.
PAST_DELIVERIES: list[dict[str, Any]] = [
    {"restaurant": "Golden Crust Bakery", "pantry": "Hope Community Pantry", "driver": "Sam Rivera",
     "days_ago": 1, "hour": 10, "title": "Unsold bread and pastries", "quantity": "30 loaves, 60 pastries",
     "allergens": "wheat, eggs, dairy", "kg": 22, "meals": 70},
    {"restaurant": "Harbor Deli", "pantry": "Hope Community Pantry", "driver": "Jordan Lee",
     "days_ago": 1, "hour": 14, "title": "Sandwiches and salads", "quantity": "40 sandwiches, 10 salads",
     "allergens": "wheat, dairy", "kg": 15, "meals": 40},
    {"restaurant": "Green Bowl Kitchen", "pantry": "Ballard Family Shelter", "driver": "Maya Chen",
     "days_ago": 1, "hour": 19, "title": "Vegetarian grain bowls", "quantity": "35 bowls",
     "allergens": "sesame", "kg": 12, "meals": 35,
     "declined_by": {"driver": "Sam Rivera", "reason": "Sorry, I don't do evening runs."}},
    {"restaurant": "Sunrise Grocery", "pantry": "Riverside Food Bank", "driver": "Luis Ortega",
     "days_ago": 2, "hour": 11, "title": "Fresh produce", "quantity": "apples, carrots, lettuce — 6 crates",
     "allergens": "", "kg": 60, "meals": 150},
    {"restaurant": "Noodle House 88", "pantry": "Rainier Valley Community Kitchen", "driver": "Fatima Noor",
     "days_ago": 2, "hour": 15, "title": "Vegetable fried rice (no meat)", "quantity": "50 boxes",
     "allergens": "soy, egg", "kg": 18, "meals": 50},
    {"restaurant": "Golden Crust Bakery", "pantry": "Hope Community Pantry", "driver": "Sam Rivera",
     "days_ago": 2, "hour": 11, "title": "Day-old bread", "quantity": "40 loaves",
     "allergens": "wheat", "kg": 20, "meals": 60},
    {"restaurant": "Harbor Deli", "pantry": "West Seattle Night Shelter", "driver": "Chris Walker",
     "days_ago": 2, "hour": 20, "title": "Soup and sandwiches", "quantity": "20 L soup, 25 sandwiches",
     "allergens": "wheat, dairy, celery", "kg": 16, "meals": 45,
     "declined_by": {"driver": "Sam Rivera", "reason": "Too late in the evening for me."}},
    {"restaurant": "Sunrise Grocery", "pantry": "Hope Community Pantry", "driver": "Jordan Lee",
     "days_ago": 3, "hour": 13, "title": "Yogurt and milk, dated tomorrow", "quantity": "80 yogurts, 20 L milk",
     "allergens": "dairy", "kg": 25, "meals": 60},
    {"restaurant": "Green Bowl Kitchen", "pantry": "U-District Student Pantry", "driver": "Alex Kim",
     "days_ago": 3, "hour": 14, "title": "Packaged granola and crackers", "quantity": "25 packs",
     "allergens": "oats, may contain nuts", "kg": 8, "meals": 25},
    {"restaurant": "Golden Crust Bakery", "pantry": "Northgate Senior Center", "driver": "Dana Brooks",
     "days_ago": 4, "hour": 10, "title": "Nut-free bread rolls", "quantity": "120 rolls",
     "allergens": "wheat", "kg": 10, "meals": 40},
    {"restaurant": "Noodle House 88", "pantry": "Hope Community Pantry", "driver": "Jordan Lee",
     "days_ago": 4, "hour": 18, "title": "Chicken noodle boxes", "quantity": "55 boxes",
     "allergens": "wheat, soy, egg", "kg": 20, "meals": 55,
     "declined_by": {"driver": "Sam Rivera", "reason": "Evenings don't work for me."}},
    {"restaurant": "Sunrise Grocery", "pantry": "Riverside Food Bank", "driver": "Luis Ortega",
     "days_ago": 5, "hour": 9, "title": "Canned goods and rice", "quantity": "10 crates",
     "allergens": "", "kg": 80, "meals": 200},
    {"restaurant": "Harbor Deli", "pantry": "Hope Community Pantry", "driver": "Sam Rivera",
     "days_ago": 6, "hour": 12, "title": "Wraps and fruit cups", "quantity": "30 wraps, 20 fruit cups",
     "allergens": "wheat", "kg": 14, "meals": 40},
    {"restaurant": "Green Bowl Kitchen", "pantry": "Rainier Valley Community Kitchen", "driver": "Fatima Noor",
     "days_ago": 6, "hour": 16, "title": "Vegan lentil stew", "quantity": "25 L",
     "allergens": "", "kg": 18, "meals": 50},
]
