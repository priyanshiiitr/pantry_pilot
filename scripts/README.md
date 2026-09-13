# `scripts/` — helper scripts you run by hand

Run them from the **project folder** with the venv active, using `python -m scripts.<name>`.

| Script | What it does |
|---|---|
| `seed_demo.py` | Creates the demo world: 5 restaurants, 7 pantries, 8 drivers, 1 admin, and a week of past deliveries. Add `--reset` to wipe existing data first. |
| `demo_world.py` | Only data: the fake Seattle world used by the seed. Edit this to change names, locations or hours. |
| `show_db.py` | Prints row counts per table plus the restaurants, pantries and drivers. |
| `reset_db.py` | Deletes all data and recreates empty tables (needs `--yes`). |

Coming later: `try_matching.py` (Step 6), `run_agent_once.py` (Step 8), `trigger_hard_case.py` (Step 11).

All demo accounts use the password **`demo1234`**.
