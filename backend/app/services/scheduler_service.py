"""Scheduler service for production-safe scheduled execution."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ingestion.contracts import SourceConfig, SourceMode
from app.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from app.models import DataSource, ParserRun
from app.services.parser_audit_service import ParserAuditService
from app.services.parser_orchestrator import ParserOrchestrator, RunRequest

logger = logging.getLogger(__name__)


class ScheduleConfig(BaseModel):
    """Configuration for scheduled execution."""

    source_id: str
    enabled: bool = True
    frequency_hours: int = Field(default=24, ge=1, le=168)
    jitter_minutes: int = Field(default=30, ge=0, le=60)
    max_pages: int | None = None
    city: str | None = None
    mode: Literal["live", "fixture", "manual"] = "fixture"
    timeout_seconds: int = 600
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_seconds: int = Field(default=300, ge=60, le=3600)


class SchedulerLock(BaseModel):
    """Database-backed scheduler lock."""

    source_id: str
    locked_by: str
    locked_at: datetime
    heartbeat_at: datetime
    lock_ttl_seconds: int = 600


class SchedulerStatus(BaseModel):
    """Status of the scheduler."""

    total_sources: int
    enabled_sources: int
    locked_sources: int
    last_run_at: datetime | None
    next_run_at: datetime | None


@dataclass
class ScheduleResult:
    """Result of a schedule evaluation."""

    source_id: str
    should_run: bool
    reason: str
    next_run_at: datetime | None = None


class SchedulerService:
    """Production-safe scheduler with database-backed locks."""

    def __init__(
        self,
        db: Session,
        registry: SourceRegistry | None = None,
        scheduler_id: str | None = None,
    ) -> None:
        self.db = db
        self.registry = registry or SOURCE_REGISTRY
        self.orchestrator = ParserOrchestrator(db, registry)
        self.audit_service = ParserAuditService(db)
        self.scheduler_id = scheduler_id or f"scheduler-{id(self)}"

    def get_schedule_configs(self) -> list[ScheduleConfig]:
        """Get schedule configurations for all enabled live sources."""
        configs = []
        for source_id in self.registry.source_ids:
            config = self.registry.get(source_id)
            if config.mode is SourceMode.LIVE and config.enabled:
                configs.append(
                    ScheduleConfig(
                        source_id=source_id,
                        enabled=True,
                        frequency_hours=24 if config.priority == "P0" else 48,
                    )
                )
        return configs

    def evaluate_schedule(self, config: ScheduleConfig) -> ScheduleResult:
        """Evaluate whether a source should run based on schedule."""
        if not config.enabled:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=False,
                reason="Source disabled in schedule config",
            )

        try:
            source_config = self.registry.get(config.source_id)
        except KeyError:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=False,
                reason="Source not found in registry",
            )

        if source_config.mode is not SourceMode.LIVE:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=False,
                reason=f"Source mode is {source_config.mode.value}, not live",
            )

        if not source_config.enabled:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=False,
                reason="Source disabled in registry",
            )

        last_run = self._get_last_successful_run(config.source_id)
        if last_run is None:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=True,
                reason="No previous successful run",
                next_run_at=datetime.now(UTC),
            )

        frequency = timedelta(hours=config.frequency_hours)
        jitter = timedelta(minutes=random.randint(0, config.jitter_minutes))
        next_run = last_run + frequency + jitter

        if datetime.now(UTC) >= next_run:
            return ScheduleResult(
                source_id=config.source_id,
                should_run=True,
                reason=f"Scheduled interval elapsed (last run: {last_run})",
                next_run_at=next_run,
            )

        return ScheduleResult(
            source_id=config.source_id,
            should_run=False,
            reason=f"Next run scheduled at {next_run}",
            next_run_at=next_run,
        )

    def acquire_lock(self, source_id: str, ttl_seconds: int = 600) -> bool:
        """Acquire a database-backed lock for a source."""
        now = datetime.now(UTC)

        existing_lock = self.db.scalar(
            select(ParserRun).where(
                ParserRun.data_source_id == self._get_data_source_id(source_id),
                ParserRun.status == "running",
            )
        )
        if existing_lock:
            lock_age = (now - existing_lock.started_at).total_seconds()
            if lock_age < ttl_seconds:
                logger.info(f"Source {source_id} is locked by run {existing_lock.id}")
                return False
            else:
                logger.warning(
                    f"Stale lock detected for {source_id} (age: {lock_age:.0f}s); "
                    f"recovering"
                )
                self.audit_service.finish_parser_run(
                    existing_lock,
                    status="failed",
                    error_count=0,
                )

        return True

    def release_lock(self, source_id: str, run_id: int) -> None:
        """Release the lock for a source."""
        pass

    def update_heartbeat(self, source_id: str, run_id: int) -> None:
        """Update heartbeat for a running parser run."""
        parser_run = self.db.get(ParserRun, run_id)
        if parser_run and parser_run.status == "running":
            parser_run.notes = (
                (parser_run.notes or "")
                + f"\nheartbeat:{datetime.now(UTC).isoformat()}"
            )
            self.db.flush()

    def run_scheduled(self, configs: list[ScheduleConfig] | None = None) -> list[ScheduleResult]:
        """Run scheduled tasks for all eligible sources."""
        if configs is None:
            configs = self.get_schedule_configs()

        results: list[ScheduleResult] = []

        for config in configs:
            evaluation = self.evaluate_schedule(config)
            results.append(evaluation)

            if not evaluation.should_run:
                continue

            if not self.acquire_lock(config.source_id):
                results[-1].reason += " (lock not acquired)"
                continue

            try:
                request = RunRequest(
                    source_ids=[config.source_id],
                    mode=config.mode,
                    dry_run=False,
                    city=config.city,
                    max_pages=config.max_pages,
                    timeout_seconds=config.timeout_seconds,
                )
                run_result = self.orchestrator.run(request)

                if run_result.status == "success":
                    logger.info(
                        f"Successfully ran scheduled task for {config.source_id}"
                    )
                else:
                    logger.warning(
                        f"Scheduled task for {config.source_id} completed with "
                        f"status: {run_result.status}"
                    )

            except Exception as exc:
                logger.error(
                    f"Error running scheduled task for {config.source_id}: {exc}"
                )

        return results

    def get_status(self) -> SchedulerStatus:
        """Get scheduler status."""
        configs = self.get_schedule_configs()
        enabled_count = sum(1 for c in configs if c.enabled)

        last_run = self.db.scalar(
            select(ParserRun).order_by(ParserRun.finished_at.desc()).limit(1)
        )

        next_runs = []
        for config in configs:
            if config.enabled:
                evaluation = self.evaluate_schedule(config)
                if evaluation.next_run_at:
                    next_runs.append(evaluation.next_run_at)

        return SchedulerStatus(
            total_sources=len(configs),
            enabled_sources=enabled_count,
            locked_sources=0,
            last_run_at=last_run.finished_at if last_run else None,
            next_run_at=min(next_runs) if next_runs else None,
        )

    def _get_last_successful_run(self, source_id: str) -> datetime | None:
        """Get the last successful run time for a source."""
        data_source_id = self._get_data_source_id(source_id)
        if data_source_id is None:
            return None

        last_run = self.db.scalar(
            select(ParserRun).where(
                ParserRun.data_source_id == data_source_id,
                ParserRun.status == "success",
            ).order_by(ParserRun.finished_at.desc()).limit(1)
        )

        return last_run.finished_at if last_run else None

    def _get_data_source_id(self, source_id: str) -> int | None:
        """Get data source ID for a source."""
        data_source = self.db.scalar(
            select(DataSource).where(DataSource.name == source_id)
        )
        return data_source.id if data_source else None


def create_default_schedule() -> list[ScheduleConfig]:
    """Create default schedule configuration for all live sources."""
    configs = []
    registry = SOURCE_REGISTRY

    for source_id in registry.source_ids:
        config = registry.get(source_id)
        if config.mode is SourceMode.LIVE and config.enabled:
            configs.append(
                ScheduleConfig(
                    source_id=source_id,
                    enabled=True,
                    frequency_hours=24 if config.priority == "P0" else 48,
                    jitter_minutes=30,
                    mode="fixture",
                    timeout_seconds=600,
                )
            )

    return configs
