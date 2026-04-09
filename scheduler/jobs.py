"""APScheduler jobs for recurring ingestion and briefing generation."""

from __future__ import annotations

import logging
import time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from agent.macro_agent import generate_briefing
from ingestion.loader import load_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def run_ingestion_job() -> None:
    """Execute the daily ingestion job with start and finish logging."""

    LOGGER.info("Starting scheduled ingestion job.")
    counts = load_all()
    LOGGER.info("Finished scheduled ingestion job with counts: %s", counts)


def run_briefing_job() -> None:
    """Execute the daily macro briefing job with start and finish logging."""

    LOGGER.info("Starting scheduled briefing job.")
    content = generate_briefing("visão geral")
    LOGGER.info("Finished scheduled briefing job. Briefing length=%s words.", len(content.split()))


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler and register the daily jobs.

    Returns
    -------
    BackgroundScheduler
        Started scheduler instance configured for Brazil's timezone.
    """

    scheduler = BackgroundScheduler(timezone=BRAZIL_TZ)
    scheduler.add_job(
        run_ingestion_job,
        trigger=CronTrigger(hour=8, minute=0, timezone=BRAZIL_TZ),
        id="daily_ingestion",
        replace_existing=True,
    )
    scheduler.add_job(
        run_briefing_job,
        trigger=CronTrigger(hour=8, minute=30, timezone=BRAZIL_TZ),
        id="daily_briefing",
        replace_existing=True,
    )
    scheduler.start()
    LOGGER.info("Scheduler started in background with timezone %s.", BRAZIL_TZ)
    return scheduler


def main() -> None:
    """Start the scheduler, log the next jobs and keep it alive briefly for validation."""

    scheduler = start_scheduler()
    for job in scheduler.get_jobs():
        LOGGER.info("Scheduled job %s next run at %s", job.id, job.next_run_time)

    try:
        time.sleep(3)
    finally:
        scheduler.shutdown(wait=False)
        LOGGER.info("Scheduler shutdown after validation window.")


if __name__ == "__main__":
    main()
