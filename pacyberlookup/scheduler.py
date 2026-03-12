"""Scheduler for running the feed on configured intervals."""

import logging
import signal
import sys
import time

import schedule

from .models import init_db
from .orchestrator import FeedOrchestrator
from .utils.config import get_database_url, load_config, load_env

logger = logging.getLogger(__name__)

_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def run_once(config_path: str | None = None):
    """Run a single feed cycle."""
    load_env()
    config = load_config(config_path)
    db_url = get_database_url()
    engine, Session = init_db(db_url)

    session = Session()
    try:
        orchestrator = FeedOrchestrator(session, config)
        results = orchestrator.run_cycle()
        logger.info("Single run complete: %d incidents", len(results))
        return results
    finally:
        session.close()


def run_scheduled(config_path: str | None = None):
    """Run the feed on a scheduled loop."""
    global _running

    load_env()
    config = load_config(config_path)
    db_url = get_database_url()
    engine, Session = init_db(db_url)

    polling = config.get("polling", {})
    interval = polling.get("news_interval_minutes", 30)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    def _cycle():
        session = Session()
        try:
            orchestrator = FeedOrchestrator(session, config)
            orchestrator.run_cycle()
        except Exception:
            logger.exception("Feed cycle failed")
        finally:
            session.close()

    # Run immediately on start
    logger.info("Starting PA Cyber Watch feed (interval: %d minutes)", interval)
    _cycle()

    schedule.every(interval).minutes.do(_cycle)

    while _running:
        schedule.run_pending()
        time.sleep(10)

    logger.info("Scheduler stopped")
