"""Entry point for `python -m pantrypilot.worker`.

Starts a scheduler that calls pick_up_new_offers() every 15 seconds, forever,
until you press Ctrl+C. This is what makes PantryPilot agentic rather than a
button you click: nobody tells it to run — it notices new work on its own.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from pantrypilot.agents.console import ensure_utf8_console
from pantrypilot.database import create_tables
from pantrypilot.worker.jobs import pick_up_new_offers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 15


def main() -> None:
    """Build the scheduler, register the jobs, and run until interrupted."""
    ensure_utf8_console()  # see agents/console.py — avoids a Windows print crash

    # Safe to call every time: only creates tables that don't exist yet. Without
    # this, starting the worker against a brand-new database (or before ever
    # starting the web server) would crash on its very first tick.
    create_tables()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        pick_up_new_offers,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="pick_up_new_offers",
        max_instances=1,  # never run a second check while one is still in progress
    )

    logger.info(
        "PantryPilot worker started — checking for new offers every %s seconds. Press Ctrl+C to stop.",
        CHECK_INTERVAL_SECONDS,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
