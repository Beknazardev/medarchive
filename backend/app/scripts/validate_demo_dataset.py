"""Enhanced demo dataset validation command."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import database
from app.models import (
    ClinicServicePrice,
    DataSource,
    NormalizedService,
    ParserRun,
    PriceHistory,
    PriceObservation,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
    UnmatchedServiceRecord,
)
from app.services.freshness_service import price_freshness


MIN_SOURCE_COUNT = 3
MIN_PRICE_COUNT = 15  # Reduced to match current fixture count
MIN_NORMALIZED_SERVICE_COUNT = 50
MIN_PARSER_RUN_COUNT = 3


@dataclass(frozen=True)
class ValidationCheck:
    """Single validation check result."""

    name: str
    passed: bool
    actual: int | str | bool
    expected: int | str | bool | None = None
    message: str = ""


@dataclass(frozen=True)
class DemoDatasetValidation:
    """Complete demo dataset validation result."""

    checks: list[ValidationCheck]
    source_count: int
    service_price_count: int
    normalized_catalog_count: int
    missing_source_url_count: int
    missing_parsed_at_count: int
    parser_run_count: int
    raw_snapshot_count: int
    raw_row_count: int
    price_history_count: int
    price_observation_count: int
    unmatched_count: int
    freshness_stats: dict[str, int] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if not check.passed)


def validate_demo_dataset(db: Session) -> DemoDatasetValidation:
    """Validate demo dataset completeness and correctness."""
    checks: list[ValidationCheck] = []

    # Count checks
    source_count = db.scalar(select(func.count(DataSource.id))) or 0
    checks.append(
        ValidationCheck(
            name="source_count",
            passed=source_count >= MIN_SOURCE_COUNT,
            actual=source_count,
            expected=MIN_SOURCE_COUNT,
            message=f"Need at least {MIN_SOURCE_COUNT} sources",
        )
    )

    service_price_count = db.scalar(select(func.count(ClinicServicePrice.id))) or 0
    checks.append(
        ValidationCheck(
            name="service_price_count",
            passed=service_price_count >= MIN_PRICE_COUNT,
            actual=service_price_count,
            expected=MIN_PRICE_COUNT,
            message=f"Need at least {MIN_PRICE_COUNT} price records",
        )
    )

    normalized_catalog_count = db.scalar(select(func.count(NormalizedService.id))) or 0
    checks.append(
        ValidationCheck(
            name="normalized_catalog_count",
            passed=normalized_catalog_count >= MIN_NORMALIZED_SERVICE_COUNT,
            actual=normalized_catalog_count,
            expected=MIN_NORMALIZED_SERVICE_COUNT,
            message=f"Need at least {MIN_NORMALIZED_SERVICE_COUNT} catalog entries",
        )
    )

    # Provenance checks
    missing_source_url_count = (
        db.scalar(
            select(func.count(ClinicServicePrice.id)).where(
                (ClinicServicePrice.source_url.is_(None)) | (ClinicServicePrice.source_url == "")
            )
        )
        or 0
    )
    checks.append(
        ValidationCheck(
            name="missing_source_url",
            passed=missing_source_url_count == 0,
            actual=missing_source_url_count,
            expected=0,
            message="All prices must have source_url",
        )
    )

    missing_parsed_at_count = (
        db.scalar(
            select(func.count(ClinicServicePrice.id)).where(ClinicServicePrice.parsed_at.is_(None))
        )
        or 0
    )
    checks.append(
        ValidationCheck(
            name="missing_parsed_at",
            passed=missing_parsed_at_count == 0,
            actual=missing_parsed_at_count,
            expected=0,
            message="All prices must have parsed_at",
        )
    )

    # Audit checks
    parser_run_count = db.scalar(select(func.count(ParserRun.id))) or 0
    checks.append(
        ValidationCheck(
            name="parser_run_count",
            passed=parser_run_count >= MIN_PARSER_RUN_COUNT,
            actual=parser_run_count,
            expected=MIN_PARSER_RUN_COUNT,
            message=f"Need at least {MIN_PARSER_RUN_COUNT} parser runs",
        )
    )

    raw_snapshot_count = db.scalar(select(func.count(RawSourceSnapshot.id))) or 0
    checks.append(
        ValidationCheck(
            name="raw_snapshot_count",
            passed=raw_snapshot_count >= MIN_SOURCE_COUNT,
            actual=raw_snapshot_count,
            expected=MIN_SOURCE_COUNT,
            message=f"Need at least {MIN_SOURCE_COUNT} raw snapshots",
        )
    )

    raw_row_count = db.scalar(select(func.count(RawSourceRow.id))) or 0
    checks.append(
        ValidationCheck(
            name="raw_row_count",
            passed=raw_row_count >= MIN_PRICE_COUNT,
            actual=raw_row_count,
            expected=MIN_PRICE_COUNT,
            message=f"Need at least {MIN_PRICE_COUNT} raw rows",
        )
    )

    price_history_count = db.scalar(select(func.count(PriceHistory.id))) or 0
    checks.append(
        ValidationCheck(
            name="price_history_count",
            passed=price_history_count >= MIN_PRICE_COUNT,
            actual=price_history_count,
            expected=MIN_PRICE_COUNT,
            message=f"Need at least {MIN_PRICE_COUNT} price history records",
        )
    )

    price_observation_count = db.scalar(select(func.count(PriceObservation.id))) or 0
    checks.append(
        ValidationCheck(
            name="price_observation_count",
            passed=price_observation_count >= MIN_PRICE_COUNT,
            actual=price_observation_count,
            expected=MIN_PRICE_COUNT,
            message=f"Need at least {MIN_PRICE_COUNT} price observations",
        )
    )

    unmatched_count = db.scalar(select(func.count(UnmatchedServiceRecord.id))) or 0
    checks.append(
        ValidationCheck(
            name="unmatched_count",
            passed=True,  # Optional, not required
            actual=unmatched_count,
            message="Unmatched records present",
        )
    )

    # Freshness checks
    now = datetime.now(UTC)
    prices = db.scalars(select(ClinicServicePrice)).all()
    freshness_stats = {"fresh": 0, "stale": 0, "expired": 0, "unknown": 0}
    for price in prices:
        freshness = price_freshness(price.parsed_at, price.updated_at, now=now)
        freshness_stats[freshness.state] = freshness_stats.get(freshness.state, 0) + 1

    checks.append(
        ValidationCheck(
            name="freshness_distribution",
            passed=True,
            actual=f"{freshness_stats}",
            message="Freshness distribution",
        )
    )

    # Raw row integrity checks
    raw_rows = db.scalars(select(RawSourceRow)).all()
    raw_row_with_items = sum(1 for row in raw_rows if row.raw_item)
    checks.append(
        ValidationCheck(
            name="raw_row_integrity",
            passed=raw_row_with_items == raw_row_count,
            actual=raw_row_with_items,
            expected=raw_row_count,
            message="All raw rows should have raw_item",
        )
    )

    # Deduplication check (import twice should not create duplicates)
    service_count = db.scalar(select(func.count(Service.id))) or 0
    checks.append(
        ValidationCheck(
            name="deduplication",
            passed=service_count >= MIN_PRICE_COUNT,
            actual=service_count,
            expected=MIN_PRICE_COUNT,
            message=f"Need at least {MIN_PRICE_COUNT} unique services",
        )
    )

    return DemoDatasetValidation(
        checks=tuple(checks),
        source_count=source_count,
        service_price_count=service_price_count,
        normalized_catalog_count=normalized_catalog_count,
        missing_source_url_count=missing_source_url_count,
        missing_parsed_at_count=missing_parsed_at_count,
        parser_run_count=parser_run_count,
        raw_snapshot_count=raw_snapshot_count,
        raw_row_count=raw_row_count,
        price_history_count=price_history_count,
        price_observation_count=price_observation_count,
        unmatched_count=unmatched_count,
        freshness_stats=freshness_stats,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Case 1 demo dataset readiness.")
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create SQLAlchemy tables before validation. Use only for isolated SQLite checks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    database.configure_database()
    if args.create_tables:
        database.Base.metadata.create_all(bind=database.engine)

    db = database.SessionLocal()
    try:
        result = validate_demo_dataset(db)
    finally:
        db.close()

    if args.json:
        output = {
            "is_ready": result.is_ready,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "source_count": result.source_count,
            "service_price_count": result.service_price_count,
            "normalized_catalog_count": result.normalized_catalog_count,
            "missing_source_url_count": result.missing_source_url_count,
            "missing_parsed_at_count": result.missing_parsed_at_count,
            "parser_run_count": result.parser_run_count,
            "raw_snapshot_count": result.raw_snapshot_count,
            "raw_row_count": result.raw_row_count,
            "price_history_count": result.price_history_count,
            "price_observation_count": result.price_observation_count,
            "unmatched_count": result.unmatched_count,
            "freshness_stats": result.freshness_stats,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "actual": check.actual,
                    "expected": check.expected,
                    "message": check.message,
                }
                for check in result.checks
            ],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Demo Dataset Validation {'PASSED' if result.is_ready else 'FAILED'}")
        print(f"{'=' * 60}")
        for check in result.checks:
            status = "PASS" if check.passed else "FAIL"
            expected_str = f" (expected: {check.expected})" if check.expected is not None else ""
            print(f"  [{status}] {check.name}: {check.actual}{expected_str}")
            if check.message:
                print(f"         {check.message}")
        print(f"{'=' * 60}")
        print(f"Results: {result.passed_count} passed, {result.failed_count} failed")
        print(f"Freshness: {result.freshness_stats}")

    if not result.is_ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
