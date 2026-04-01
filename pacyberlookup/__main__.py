"""CLI entry point for PA Cyber Incident Detection Feed."""

import argparse
import logging
import sys

from .export.powerbi import export_all
from .models import init_db
from .scheduler import run_once, run_scheduled
from .seed import seed_entities
from .utils.config import get_database_url, load_config, load_env


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(
        description="PA Cyber Incident Detection Feed",
        prog="pacyberlookup",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run - single cycle
    run_parser = subparsers.add_parser("run", help="Run a single feed cycle")
    run_parser.add_argument("--config", help="Path to config YAML")

    # start - scheduled loop
    start_parser = subparsers.add_parser("start", help="Start the scheduled feed loop")
    start_parser.add_argument("--config", help="Path to config YAML")

    # seed - load seed entities
    seed_parser = subparsers.add_parser("seed", help="Seed the entity database")
    seed_parser.add_argument("--file", help="Path to seed CSV file")

    # export - export Power BI data
    subparsers.add_parser("export", help="Export data for Power BI")

    # init-db - initialize database
    subparsers.add_parser("init-db", help="Initialize the database")

    # status - interactive CLI dashboard
    status_parser = subparsers.add_parser("status", help="Show feed status dashboard")
    status_parser.add_argument("--hours", type=int, default=24,
                               help="Lookback period in hours (default: 24)")

    # digest - send a digest report now
    digest_parser = subparsers.add_parser("digest", help="Send a digest report now")
    digest_parser.add_argument("--hours", type=int, default=24,
                               help="Lookback period in hours (default: 24)")

    # health - show source health
    health_parser = subparsers.add_parser("health", help="Show source health status")
    health_parser.add_argument("--hours", type=int, default=24,
                               help="Lookback period in hours (default: 24)")

    # timeline - show incident timeline
    timeline_parser = subparsers.add_parser("timeline", help="Show incident timeline")
    timeline_parser.add_argument("incident_id", type=int, help="Incident ID to show timeline for")

    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()
    setup_logging(args.log_level if hasattr(args, "log_level") else "INFO")

    load_env()

    # Validate --hours if present
    if hasattr(args, "hours") and args.hours is not None:
        if args.hours < 1:
            print("Error: --hours must be at least 1")
            sys.exit(1)
        if args.hours > 8760:
            print("Error: --hours cannot exceed 8760 (1 year)")
            sys.exit(1)

    if args.command == "run":
        run_once(args.config)

    elif args.command == "start":
        run_scheduled(args.config)

    elif args.command == "seed":
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            seed_entities(session, args.file)
        finally:
            session.close()

    elif args.command == "export":
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            paths = export_all(session)
            for name, path in paths.items():
                print(f"Exported {name}: {path}")
        finally:
            session.close()

    elif args.command == "init-db":
        db_url = get_database_url()
        init_db(db_url)
        print(f"Database initialized: {db_url}")

    elif args.command == "status":
        from .dashboard import print_dashboard
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            print_dashboard(session, args.hours)
        finally:
            session.close()

    elif args.command == "digest":
        from .alerts.digest import send_digest
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            success = send_digest(session, args.hours)
            if success:
                print("Digest sent successfully")
            else:
                print("Digest delivery failed (check Teams/email config)")
        finally:
            session.close()

    elif args.command == "health":
        from .health import SourceHealthTracker
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            tracker = SourceHealthTracker(session)
            print()
            print("  SOURCE HEALTH STATUS")
            print("  " + "=" * 75)
            print(tracker.render_health_table(args.hours))
            print()
            failing = tracker.get_failing_sources(min_consecutive=3, hours=args.hours)
            if failing:
                print("  WARNINGS:")
                for f in failing:
                    print(f"    {f['source_name']}: {f['consecutive_failures']} "
                          f"consecutive failures. Last error: {f['last_error_message']}")
                print()
        finally:
            session.close()

    elif args.command == "timeline":
        from .timeline import get_incident_timeline
        db_url = get_database_url()
        engine, Session = init_db(db_url)
        session = Session()
        try:
            events = get_incident_timeline(session, args.incident_id)
            if not events:
                print(f"No timeline events for incident {args.incident_id}")
            else:
                print(f"\n  INCIDENT {args.incident_id} TIMELINE")
                print("  " + "=" * 60)
                for e in events:
                    ts = e["timestamp"].strftime("%Y-%m-%d %H:%M") if e["timestamp"] else "?"
                    prev = e["previous_status"] or "None"
                    print(f"  {ts}  {prev} -> {e['status']}")
                    if e["trigger"]:
                        print(f"           Trigger: {e['trigger']}")
                    if e["source"]:
                        print(f"           Source: {e['source']}")
                    if e["notes"]:
                        print(f"           Notes: {e['notes']}")
                    print(f"           Score at time: {e['confidence_score_at']}")
                    print()
        finally:
            session.close()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
