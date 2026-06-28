"""Tests for scheduler service and CLI - Phase L TDD."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

# Set database URL before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from app.core.database import Base
from app.models import DataSource, ParserRun
from app.services.scheduler_service import (
    SchedulerService,
    ScheduleConfig,
    ScheduleResult,
    create_default_schedule,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def scheduler(db_session):
    return SchedulerService(db_session, scheduler_id="test-scheduler")


# ─── Schedule config tests ───

class TestScheduleConfig:
    def test_default_schedule_for_live_sources(self):
        configs = create_default_schedule()
        assert len(configs) > 0
        assert any(c.source_id == "kdl_olymp" for c in configs)

    def test_schedule_config_has_required_fields(self):
        configs = create_default_schedule()
        for config in configs:
            assert config.source_id
            assert config.frequency_hours >= 1
            assert config.jitter_minutes >= 0
            assert config.mode in ("live", "fixture", "manual")


# ─── Schedule evaluation tests ───

class TestScheduleEvaluation:
    def test_disabled_source_should_not_run(self, scheduler):
        config = ScheduleConfig(source_id="test", enabled=False)
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is False
        assert "disabled" in result.reason.lower()

    def test_unknown_source_should_not_run(self, scheduler):
        config = ScheduleConfig(source_id="unknown_source")
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is False
        assert "not found" in result.reason.lower()

    def test_scaffold_source_should_not_run(self, scheduler):
        config = ScheduleConfig(source_id="invivo_kz")
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is False
        assert "scaffold" in result.reason.lower()

    def test_permission_required_should_not_run(self, scheduler):
        config = ScheduleConfig(source_id="invitro_kz")
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is False
        assert "permission" in result.reason.lower()

    def test_no_previous_run_should_run(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        config = ScheduleConfig(source_id="kdl_olymp")
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is True
        assert "no previous" in result.reason.lower()

    def test_recent_run_should_not_run(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        run = ParserRun(
            data_source_id=data_source.id,
            status="success",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.flush()

        config = ScheduleConfig(
            source_id="kdl_olymp",
            frequency_hours=24,
            jitter_minutes=0,
        )
        result = scheduler.evaluate_schedule(config)
        assert result.should_run is False
        assert "next run" in result.reason.lower()


# ─── Lock tests ───

class TestLocks:
    def test_acquire_lock_when_no_running(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        acquired = scheduler.acquire_lock("kdl_olymp")
        assert acquired is True

    def test_acquire_lock_when_running(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        run = ParserRun(
            data_source_id=data_source.id,
            status="running",
            started_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.flush()

        acquired = scheduler.acquire_lock("kdl_olymp")
        assert acquired is False

    def test_acquire_lock_recovers_stale_lock(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        stale_time = datetime.now(UTC) - timedelta(seconds=700)
        run = ParserRun(
            data_source_id=data_source.id,
            status="running",
            started_at=stale_time,
        )
        db_session.add(run)
        db_session.flush()

        acquired = scheduler.acquire_lock("kdl_olymp", ttl_seconds=600)
        assert acquired is True


# ─── Status tests ───

class TestStatus:
    def test_get_status(self, scheduler, db_session):
        status = scheduler.get_status()
        assert status.total_sources > 0
        assert status.enabled_sources >= 0

    def test_get_status_with_runs(self, scheduler, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        run = ParserRun(
            data_source_id=data_source.id,
            status="success",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        db_session.add(run)
        db_session.flush()

        status = scheduler.get_status()
        assert status.last_run_at is not None


# ─── Run scheduled tests ───

class TestRunScheduled:
    def test_run_scheduled_with_no_eligible(self, scheduler):
        results = scheduler.run_scheduled(configs=[])
        assert len(results) == 0

    def test_run_scheduled_skips_disabled(self, scheduler):
        config = ScheduleConfig(source_id="test", enabled=False)
        results = scheduler.run_scheduled(configs=[config])
        assert len(results) == 1
        assert results[0].should_run is False


# ─── CLI parsing tests ───

class TestCLIParsing:
    def test_cli_run_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_scheduler", "run", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "run" in result.stdout.lower()

    def test_cli_status_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_scheduler", "status", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "status" in result.stdout.lower()

    def test_cli_cron_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_scheduler", "cron", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "cron" in result.stdout.lower()

    def test_cli_validate_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_scheduler", "validate", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "validate" in result.stdout.lower()


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_schedule_configs_are_deterministic(self):
        configs1 = create_default_schedule()
        configs2 = create_default_schedule()
        assert len(configs1) == len(configs2)
        assert [c.source_id for c in configs1] == [c.source_id for c in configs2]
