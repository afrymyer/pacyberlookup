"""Scheduler for running the feed on configured intervals.

Supports per-source polling intervals and scheduled digest delivery.
"""

import logging
import os
import signal
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
    """Run the feed with per-source polling intervals and digest scheduling."""
    global _running

    load_env()
    config = load_config(config_path)
    db_url = get_database_url()
    engine, Session = init_db(db_url)

    polling = config.get("polling", {})

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    def _make_cycle(source_types: list[str], label: str):
        """Create a cycle function for specific source types."""
        def _cycle():
            session = Session()
            try:
                orchestrator = FeedOrchestrator(session, config)
                orchestrator.run_cycle(source_filter=source_types)
            except Exception:
                logger.exception("Feed cycle failed for %s", label)
            finally:
                session.close()
        return _cycle

    def _digest_cycle():
        """Run the daily digest."""
        from .alerts.digest import send_digest
        session = Session()
        try:
            send_digest(session, hours=24)
        except Exception:
            logger.exception("Digest delivery failed")
        finally:
            session.close()

    # Per-source group polling configuration
    source_schedules = [
        ("News + CyberNews", ["news"], polling.get("news_interval_minutes", 30)),
        ("GDELT", ["gdelt"], polling.get("gdelt_interval_minutes", 30)),
        ("CISA + PA AG", ["cisa", "government"], polling.get("cisa_interval_minutes", 60)),
        ("HIBP", ["hibp"], polling.get("hibp_interval_minutes", 60)),
        ("Ransomware.live", ["ransomware_leak"], polling.get("ransomware_live_interval_minutes", 30)),
        ("Threat Intel", ["threat_intel"], polling.get("otx_interval_minutes", 60)),
        ("Social", ["social"], polling.get("social_interval_minutes", 30)),
    ]

    logger.info("Starting PA Cyber Watch feed with per-source polling:")
    for label, types, interval in source_schedules:
        logger.info("  %s: every %d minutes", label, interval)
        schedule.every(interval).minutes.do(_make_cycle(types, label))

    # Schedule daily digest
    digest_hour = os.getenv("DIGEST_HOUR", "07:00")
    schedule.every().day.at(digest_hour).do(_digest_cycle)
    logger.info("  Daily digest: at %s UTC", digest_hour)

    # Run an initial full cycle
    logger.info("Running initial full cycle...")
    session = Session()
    try:
        orchestrator = FeedOrchestrator(session, config)
        orchestrator.run_cycle()
    except Exception:
        logger.exception("Initial feed cycle failed")
    finally:
        session.close()

    while _running:
        schedule.run_pending()
        time.sleep(10)

    logger.info("Scheduler stopped")
