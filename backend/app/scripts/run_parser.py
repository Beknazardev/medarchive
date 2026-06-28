"""CLI commands for parser execution."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.core import database
from app.ingestion.registry import SOURCE_REGISTRY
from app.services.parser_orchestrator import ParserOrchestrator, RunRequest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MedPrice parser execution CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List sources command
    list_parser = subparsers.add_parser(
        "list",
        help="List all registered sources",
    )
    list_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run parser for specified sources",
    )
    run_parser.add_argument(
        "source_ids",
        nargs="+",
        help="Source IDs to run",
    )
    run_parser.add_argument(
        "--mode",
        choices=["live", "fixture", "manual"],
        default="fixture",
        help="Execution mode (default: fixture)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no promotion)",
    )
    run_parser.add_argument(
        "--city",
        help="City scope (for city-aware sources)",
    )
    run_parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages to process",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds (default: 300)",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show run status",
    )
    status_parser.add_argument(
        "run_id",
        type=int,
        nargs="?",
        help="Run ID to check (omit for recent runs)",
    )
    status_parser.add_argument(
        "--source",
        help="Filter by source ID",
    )
    status_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent runs to show",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a run request without executing",
    )
    validate_parser.add_argument(
        "source_ids",
        nargs="+",
        help="Source IDs to validate",
    )
    validate_parser.add_argument(
        "--mode",
        choices=["live", "fixture", "manual"],
        default="fixture",
        help="Execution mode",
    )
    validate_parser.add_argument(
        "--city",
        help="City scope",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    database.configure_database()
    db = database.SessionLocal()

    try:
        orchestrator = ParserOrchestrator(db)

        if args.command == "list":
            _handle_list(orchestrator, args)
        elif args.command == "run":
            _handle_run(orchestrator, args)
        elif args.command == "status":
            _handle_status(orchestrator, args)
        elif args.command == "validate":
            _handle_validate(orchestrator, args)
    finally:
        db.close()


def _handle_list(orchestrator: ParserOrchestrator, args: argparse.Namespace) -> None:
    """Handle list command."""
    sources = orchestrator.list_sources()

    if args.format == "json":
        print(json.dumps(sources, indent=2, ensure_ascii=False))
        return

    print(f"{'Source ID':<25} {'Display Name':<30} {'Mode':<20} {'Priority':<10} {'Enabled'}")
    print("-" * 100)
    for source in sources:
        print(
            f"{source['source_id']:<25} "
            f"{source['display_name']:<30} "
            f"{source['mode']:<20} "
            f"{source['priority']:<10} "
            f"{'Yes' if source['enabled'] else 'No'}"
        )


def _handle_run(orchestrator: ParserOrchestrator, args: argparse.Namespace) -> None:
    """Handle run command."""
    request = RunRequest(
        source_ids=args.source_ids,
        mode=args.mode,
        dry_run=args.dry_run,
        city=args.city,
        max_pages=args.max_pages,
        timeout_seconds=args.timeout,
    )

    result = orchestrator.run(request)

    print(f"Status: {result.status}")
    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")

    if result.runs:
        print("\nRuns:")
        for run in result.runs:
            print(
                f"  Run {run.run_id}: {run.source_id} - {run.status} "
                f"(received={run.received_count}, imported={run.imported_count}, "
                f"errors={run.error_count})"
            )

    exit_code = 0 if result.status == "success" else 1
    sys.exit(exit_code)


def _handle_status(orchestrator: ParserOrchestrator, args: argparse.Namespace) -> None:
    """Handle status command."""
    if args.run_id:
        status = orchestrator.get_run_status(args.run_id)
        if not status:
            print(f"Run {args.run_id} not found")
            sys.exit(1)
        _print_run_status(status)
    else:
        runs = orchestrator.list_runs(source_id=args.source, limit=args.limit)
        if not runs:
            print("No runs found")
            return
        for run in runs:
            _print_run_status(run)
            print()


def _handle_validate(orchestrator: ParserOrchestrator, args: argparse.Namespace) -> None:
    """Handle validate command."""
    request = RunRequest(
        source_ids=args.source_ids,
        mode=args.mode,
        city=args.city,
    )
    errors = orchestrator.validate_run_request(request)

    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Validation passed")
        sys.exit(0)


def _print_run_status(status: Any) -> None:
    """Print run status."""
    print(f"Run {status.run_id}:")
    print(f"  Source: {status.source_id}")
    print(f"  Status: {status.status}")
    print(f"  Started: {status.started_at}")
    if status.finished_at:
        print(f"  Finished: {status.finished_at}")
    print(f"  Received: {status.received_count}")
    print(f"  Imported: {status.imported_count}")
    print(f"  Errors: {status.error_count}")
    if status.notes:
        print(f"  Notes: {status.notes}")


if __name__ == "__main__":
    main()
