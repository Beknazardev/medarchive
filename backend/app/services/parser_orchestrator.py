"""Parser run orchestration service - manages parser execution lifecycle."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.contracts import SourceConfig, SourceMode
from app.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from app.models import DataSource, ParserRun
from app.services.parser_audit_service import ParserAuditService


class RunRequest(BaseModel):
    """Request to run parser for one or more sources."""

    source_ids: list[str] = Field(min_length=1, max_length=10)
    mode: Literal["live", "fixture", "manual"] = "fixture"
    dry_run: bool = False
    city: str | None = None
    max_pages: int | None = None
    timeout_seconds: int = 300


class RunStatus(BaseModel):
    """Status of a parser run."""

    run_id: int
    source_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    received_count: int
    imported_count: int
    error_count: int
    notes: str | None


class RunResult(BaseModel):
    """Result of a parser run operation."""

    status: str
    runs: list[RunStatus]
    errors: list[str]


@dataclass
class _RunLock:
    """Per-source execution lock."""

    _locks: dict[str, threading.Lock] = field(default_factory=dict)
    _global_lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self, source_id: str) -> bool:
        with self._global_lock:
            if source_id not in self._locks:
                self._locks[source_id] = threading.Lock()
            return self._locks[source_id].acquire(blocking=False)

    def release(self, source_id: str) -> None:
        with self._global_lock:
            if source_id in self._locks:
                self._locks[source_id].release()


class ParserOrchestrator:
    """Orchestrates parser runs with isolation and locking."""

    def __init__(self, db: Session, registry: SourceRegistry | None = None) -> None:
        self.db = db
        self.registry = registry or SOURCE_REGISTRY
        self.audit_service = ParserAuditService(db)
        self._lock = _RunLock()

    def list_sources(self) -> list[dict[str, Any]]:
        """List all registered sources with their status."""
        sources = []
        for source_id in self.registry.source_ids:
            config = self.registry.get(source_id)
            sources.append(
                {
                    "source_id": source_id,
                    "display_name": config.display_name,
                    "source_type": config.source_type,
                    "mode": config.mode.value,
                    "priority": config.priority,
                    "formats": [f.value for f in config.formats],
                    "enabled": config.enabled,
                    "cities": list(config.city_scope),
                }
            )
        return sources

    def validate_run_request(self, request: RunRequest) -> list[str]:
        """Validate a run request and return any errors."""
        errors = []

        for source_id in request.source_ids:
            try:
                config = self.registry.get(source_id)
            except KeyError:
                errors.append(f"Unknown source: {source_id}")
                continue

            if config.mode is not SourceMode.LIVE and request.mode == "live":
                errors.append(
                    f"Source {source_id} is {config.mode.value}; cannot run in live mode"
                )

            if config.mode is SourceMode.SCAFFOLD:
                errors.append(f"Source {source_id} is scaffold; not ready for execution")

            if config.mode is SourceMode.MANUAL_IMPORT_ONLY and request.mode != "fixture":
                errors.append(
                    f"Source {source_id} is manual_import_only; only fixture mode allowed"
                )

            if config.mode is SourceMode.PERMISSION_REQUIRED:
                errors.append(f"Source {source_id} requires permission; cannot execute")

            if config.mode is SourceMode.OFFICIAL_API_REQUIRED:
                errors.append(f"Source {source_id} requires official API; cannot execute via CLI")

            if request.city and request.city not in config.city_scope and config.city_scope:
                errors.append(
                    f"City {request.city} not in scope for {source_id}; "
                    f"available: {', '.join(config.city_scope)}"
                )

            if request.max_pages and request.max_pages > config.max_pages_per_run:
                errors.append(
                    f"max_pages {request.max_pages} exceeds limit {config.max_pages_per_run} "
                    f"for {source_id}"
                )

        return errors

    def run(self, request: RunRequest) -> RunResult:
        """Execute parser run for requested sources."""
        errors = self.validate_run_request(request)
        if errors:
            return RunResult(status="validation_error", runs=[], errors=errors)

        run_statuses: list[RunStatus] = []
        all_errors: list[str] = []

        for source_id in request.source_ids:
            if not self._lock.acquire(source_id):
                all_errors.append(f"Source {source_id} is already running; skipped")
                continue

            try:
                status = self._run_single_source(source_id, request)
                run_statuses.append(status)
            except Exception as exc:
                all_errors.append(f"Error running {source_id}: {exc}")
            finally:
                self._lock.release(source_id)

        overall_status = "success"
        if all_errors:
            overall_status = "partial_failed" if run_statuses else "failed"

        return RunResult(
            status=overall_status,
            runs=run_statuses,
            errors=all_errors,
        )

    def _run_single_source(
        self,
        source_id: str,
        request: RunRequest,
    ) -> RunStatus:
        """Run parser for a single source."""
        config = self.registry.get(source_id)

        data_source = self.db.scalar(
            select(DataSource).where(DataSource.name == source_id)
        )
        if not data_source:
            data_source = DataSource(
                name=source_id,
                type=config.source_type,
                is_active=True,
            )
            self.db.add(data_source)
            self.db.flush()

        now = datetime.now(UTC)
        notes = f"CLI run: mode={request.mode}, dry_run={request.dry_run}"
        if request.city:
            notes += f", city={request.city}"

        parser_run = self.audit_service.create_parser_run(
            data_source=data_source,
            status="running",
            source_url=config.start_urls[0] if config.start_urls else None,
            started_at=now,
            notes=notes,
        )

        try:
            if request.mode == "fixture":
                result = self._run_fixture_mode(source_id, config, parser_run, request)
            elif request.mode == "manual":
                result = self._run_manual_mode(source_id, config, parser_run, request)
            else:
                result = self._run_live_mode(source_id, config, parser_run, request)

            self.audit_service.finish_parser_run(
                parser_run,
                status=result["status"],
                imported_count=result.get("imported_count", 0),
                error_count=result.get("error_count", 0),
            )

            return RunStatus(
                run_id=parser_run.id,
                source_id=source_id,
                status=result["status"],
                started_at=now,
                finished_at=datetime.now(UTC),
                received_count=result.get("received_count", 0),
                imported_count=result.get("imported_count", 0),
                error_count=result.get("error_count", 0),
                notes=notes,
            )

        except Exception as exc:
            self.audit_service.finish_parser_run(
                parser_run,
                status="failed",
                error_count=1,
            )
            self.audit_service.save_parser_error(
                parser_run,
                code="ORCHESTRATION_ERROR",
                message=str(exc),
                severity="error",
                stage="orchestration",
            )
            raise

    def _run_fixture_mode(
        self,
        source_id: str,
        config: SourceConfig,
        parser_run: ParserRun,
        request: RunRequest,
    ) -> dict[str, Any]:
        """Run in fixture mode - import from existing fixture files."""
        from app.services.source_fixture_import_service import (
            DEFAULT_FIXTURES_DIR,
            SourceFixtureImportService,
        )
        from pathlib import Path

        fixtures_dir = DEFAULT_FIXTURES_DIR
        fixture_file = fixtures_dir / f"{source_id}_adapter_output.json"

        if not fixture_file.exists():
            self.audit_service.save_parser_error(
                parser_run,
                code="FIXTURE_NOT_FOUND",
                message=f"Fixture file not found: {fixture_file}",
                severity="warning",
                stage="fixture",
            )
            return {
                "status": "failed",
                "received_count": 0,
                "imported_count": 0,
                "error_count": 1,
            }

        importer = SourceFixtureImportService(self.db, fixtures_dir=fixtures_dir)
        result = importer.import_fixture(fixture_file)

        return {
            "status": result.status,
            "received_count": result.received_count,
            "imported_count": result.created_count + result.updated_count + result.unchanged_count,
            "error_count": result.error_count,
        }

    def _run_manual_mode(
        self,
        source_id: str,
        config: SourceConfig,
        parser_run: ParserRun,
        request: RunRequest,
    ) -> dict[str, Any]:
        """Run in manual mode - placeholder for manual file import."""
        self.audit_service.save_parser_error(
            parser_run,
            code="MANUAL_MODE_NOT_IMPLEMENTED",
            message="Manual mode requires approved document profiles",
            severity="info",
            stage="manual",
        )
        return {
            "status": "success",
            "received_count": 0,
            "imported_count": 0,
            "error_count": 0,
        }

    def _run_live_mode(
        self,
        source_id: str,
        config: SourceConfig,
        parser_run: ParserRun,
        request: RunRequest,
    ) -> dict[str, Any]:
        """Run in live mode - fetch from public URLs."""
        if request.dry_run:
            self.audit_service.save_parser_error(
                parser_run,
                code="DRY_RUN_MODE",
                message="Dry run: would fetch from public URLs but promotion blocked",
                severity="info",
                stage="fetch",
            )
            return {
                "status": "success",
                "received_count": 0,
                "imported_count": 0,
                "error_count": 0,
            }

        self.audit_service.save_parser_error(
            parser_run,
            code="LIVE_MODE_NOT_IMPLEMENTED",
            message="Live mode requires adapter implementation",
            severity="info",
            stage="live",
        )
        return {
            "status": "success",
            "received_count": 0,
            "imported_count": 0,
            "error_count": 0,
        }

    def get_run_status(self, run_id: int) -> RunStatus | None:
        """Get status of a parser run."""
        parser_run = self.db.get(ParserRun, run_id)
        if not parser_run:
            return None

        return RunStatus(
            run_id=parser_run.id,
            source_id="",  # Would need to join with DataSource
            status=parser_run.status,
            started_at=parser_run.started_at,
            finished_at=parser_run.finished_at,
            received_count=parser_run.received_count,
            imported_count=parser_run.imported_count,
            error_count=parser_run.error_count,
            notes=parser_run.notes,
        )

    def list_runs(
        self,
        source_id: str | None = None,
        limit: int = 20,
    ) -> list[RunStatus]:
        """List recent parser runs."""
        query = select(ParserRun).order_by(ParserRun.started_at.desc()).limit(limit)
        if source_id:
            data_source = self.db.scalar(
                select(DataSource).where(DataSource.name == source_id)
            )
            if data_source:
                query = query.where(ParserRun.data_source_id == data_source.id)

        runs = self.db.scalars(query).all()
        return [
            RunStatus(
                run_id=run.id,
                source_id=source_id or "",
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                received_count=run.received_count,
                imported_count=run.imported_count,
                error_count=run.error_count,
                notes=run.notes,
            )
            for run in runs
        ]
