"""The background worker: wakes the agent team up on its own, on a timer.

DETERMINISTIC CODE: this package only decides WHEN to run the agents (APScheduler,
a timer library). It never decides WHAT to do — that's entirely pantrypilot.agents.

Run it in its own terminal, alongside the web server:
    python -m pantrypilot.worker
"""
