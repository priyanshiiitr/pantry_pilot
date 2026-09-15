# `worker/` — the background scheduler

This is what makes PantryPilot agentic instead of a button you click. Run it in
its own terminal, alongside the web server:

```powershell
python -m pantrypilot.worker
```

| File | What it does |
|---|---|
| `__main__.py` | Starts [APScheduler](https://apscheduler.readthedocs.io/) (a Python timer library) and registers the jobs below. Runs forever until Ctrl+C. |
| `jobs.py` | `pick_up_new_offers()` — every 15 seconds, finds offers still waiting and runs the full agent team on each one via `agents/runner.py`. |

More jobs arrive later: re-checking a delivery after a driver declines or times
out (Step 10), and resuming a case once an admin answers a paused decision
(Step 11).

**DETERMINISTIC CODE.** This package only decides *when* to wake the agents —
never *what* they decide. That's entirely `pantrypilot/agents/`.
