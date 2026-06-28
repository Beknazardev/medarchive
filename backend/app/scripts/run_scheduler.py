"""CLI commands for scheduled parser execution."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.core import database
from app.services.scheduler_service import SchedulerService, create_default_schedule


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MedPrice scheduler CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run scheduler command
    run_parser = subparsers.add_parser(
        "run",
        help="Run scheduled tasks for eligible sources",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show scheduler status",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate schedule configuration",
    )

    # Generate cron command
    cron_parser = subparsers.add_parser(
        "cron",
        help="Generate cron configuration",
    )
    cron_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in minutes (default: 60)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    database.configure_database()
    db = database.SessionLocal()

    try:
        scheduler = SchedulerService(db)

        if args.command == "run":
            _handle_run(scheduler, args)
        elif args.command == "status":
            _handle_status(scheduler)
        elif args.command == "validate":
            _handle_validate(scheduler)
        elif args.command == "cron":
            _handle_cron(args)
    finally:
        db.close()


def _handle_run(scheduler: SchedulerService, args: argparse.Namespace) -> None:
    """Handle run command."""
    if args.dry_run:
        configs = scheduler.get_schedule_configs()
        print("Dry run - would execute:")
        for config in configs:
            evaluation = scheduler.evaluate_schedule(config)
            status = "RUN" if evaluation.should_run else "SKIP"
            print(f"  [{status}] {config.source_id}: {evaluation.reason}")
        return

    results = scheduler.run_scheduled()

    print(f"Scheduled run completed: {len(results)} sources evaluated")
    for result in results:
        status = "RUN" if result.should_run else "SKIP"
        print(f"  [{status}] {result.source_id}: {result.reason}")


def _handle_status(scheduler: SchedulerService) -> None:
    """Handle status command."""
    status = scheduler.get_status()
    print(f"Scheduler Status:")
    print(f"  Total sources: {status.total_sources}")
    print(f"  Enabled sources: {status.enabled_sources}")
    print(f"  Locked sources: {status.locked_sources}")
    if status.last_run_at:
        print(f"  Last run: {status.last_run_at}")
    if status.next_run_at:
        print(f"  Next run: {status.next_run_at}")


def _handle_validate(scheduler: SchedulerService) -> None:
    """Handle validate command."""
    configs = scheduler.get_schedule_configs()
    print(f"Valid schedule configuration: {len(configs)} sources")

    for config in configs:
        evaluation = scheduler.evaluate_schedule(config)
        print(f"  {config.source_id}: {evaluation.reason}")


def _handle_cron(args: argparse.Namespace) -> None:
    """Handle cron command - generate cron configuration."""
    interval = args.interval
    print(f"# MedPrice Scheduler Cron Configuration")
    print(f"# Check every {interval} minutes")
    print(f"*/{interval} * * * * cd /app && python -m app.scripts.run_scheduler run >> /var/log/scheduler.log 2>&1")
    print()
    print(f"# Docker Compose alternative:")
    print(f"services:")
    print(f"  scheduler:")
    print(f"    build:")
    print(f"      context: ./backend")
    print(f"    command: python -m app.scripts.run_scheduler run")
    print(f"    environment:")
    print(f"      DATABASE_URL: postgresql+psycopg://postgres:postgres@postgres:5432/aggregator")
    print(f"    depends_on:")
    print(f"      postgres:")
    print(f"        condition: service_healthy")
    print(f"    restart: unless-stopped")


if __name__ == "__main__":
    main()
