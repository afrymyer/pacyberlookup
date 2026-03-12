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
    export_parser = subparsers.add_parser("export", help="Export data for Power BI")

    # init-db - initialize database
    subparsers.add_parser("init-db", help="Initialize the database")

    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()
    setup_logging(args.log_level if hasattr(args, "log_level") else "INFO")

    load_env()

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

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
