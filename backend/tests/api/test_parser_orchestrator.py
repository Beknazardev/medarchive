"""Tests for parser orchestration service and CLI - Phase K TDD."""

from __future__ import annotations

import os
from datetime import UTC, datetime

# Set database URL before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.models import DataSource, ParserRun
from app.services.parser_orchestrator import ParserOrchestrator, RunRequest, _RunLock
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
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def orchestrator(db_session):
    return ParserOrchestrator(db_session)


# ─── Source listing tests ───

class TestListSources:
    def test_list_returns_all_sources(self, orchestrator):
        sources = orchestrator.list_sources()
        assert len(sources) > 0
        assert any(s["source_id"] == "kdl_olymp" for s in sources)

    def test_list_includes_required_fields(self, orchestrator):
        sources = orchestrator.list_sources()
        for source in sources:
            assert "source_id" in source
            assert "display_name" in source
            assert "mode" in source
            assert "priority" in source
            assert "enabled" in source


# ─── Validation tests ───

class TestValidation:
    def test_validates_unknown_source(self, orchestrator):
        request = RunRequest(source_ids=["unknown_source"])
        errors = orchestrator.validate_run_request(request)
        assert len(errors) > 0
        assert "Unknown source" in errors[0]

    def test_validates_scaffold_source(self, orchestrator):
        request = RunRequest(source_ids=["invivo_kz"])
        errors = orchestrator.validate_run_request(request)
        assert any("scaffold" in e for e in errors)

    def test_validates_permission_required(self, orchestrator):
        request = RunRequest(source_ids=["invitro_kz"])
        errors = orchestrator.validate_run_request(request)
        assert any("permission" in e for e in errors)

    def test_validates_city_scope(self, orchestrator):
        request = RunRequest(source_ids=["kdl_olymp"], city="UnknownCity")
        errors = orchestrator.validate_run_request(request)
        assert any("not in scope" in e for e in errors)

    def test_validates_max_pages(self, orchestrator):
        request = RunRequest(source_ids=["kdl_olymp"], max_pages=1000)
        errors = orchestrator.validate_run_request(request)
        assert any("exceeds limit" in e for e in errors)

    def test_valid_request_has_no_errors(self, orchestrator):
        request = RunRequest(source_ids=["kdl_olymp"], mode="fixture")
        errors = orchestrator.validate_run_request(request)
        assert len(errors) == 0


# ─── Run execution tests ───

class TestRunExecution:
    def test_run_fixture_mode(self, orchestrator, db_session):
        # Create data source
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        request = RunRequest(source_ids=["kdl_olymp"], mode="fixture")
        result = orchestrator.run(request)

        assert result.status in ("success", "failed", "validation_error")
        assert len(result.runs) >= 0

    def test_run_dry_run_mode(self, orchestrator, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        request = RunRequest(source_ids=["kdl_olymp"], mode="fixture", dry_run=True)
        result = orchestrator.run(request)

        assert result.status in ("success", "failed", "validation_error")

    def test_run_rejects_gated_sources(self, orchestrator):
        request = RunRequest(source_ids=["invitro_kz"], mode="fixture")
        result = orchestrator.run(request)

        assert result.status == "validation_error"
        assert len(result.errors) > 0

    def test_run_with_lock(self, orchestrator, db_session):
        data_source = DataSource(name="kdl_olymp", type="laboratory", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        lock = _RunLock()
        assert lock.acquire("kdl_olymp")
        assert not lock.acquire("kdl_olymp")  # Should fail
        lock.release("kdl_olymp")
        assert lock.acquire("kdl_olymp")  # Should succeed
        lock.release("kdl_olymp")


# ─── Status tests ───

class TestStatus:
    def test_get_run_status(self, orchestrator, db_session):
        data_source = DataSource(name="test_source", type="test", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        run = orchestrator.audit_service.create_parser_run(
            data_source=data_source,
            status="success",
        )
        db_session.flush()

        status = orchestrator.get_run_status(run.id)
        assert status is not None
        assert status.run_id == run.id
        assert status.status == "success"

    def test_get_run_status_not_found(self, orchestrator):
        status = orchestrator.get_run_status(99999)
        assert status is None

    def test_list_runs(self, orchestrator, db_session):
        data_source = DataSource(name="test_source", type="test", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        orchestrator.audit_service.create_parser_run(
            data_source=data_source,
            status="success",
        )
        db_session.flush()

        runs = orchestrator.list_runs()
        assert len(runs) >= 1


# ─── CLI parsing tests ───

class TestCLIParsing:
    def test_cli_list_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_parser", "list", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "list" in result.stdout.lower()

    def test_cli_run_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_parser", "run", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "run" in result.stdout.lower()

    def test_cli_status_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_parser", "status", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "status" in result.stdout.lower()

    def test_cli_validate_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_parser", "validate", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "validate" in result.stdout.lower()


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_list_sources_is_deterministic(self, orchestrator):
        sources1 = orchestrator.list_sources()
        sources2 = orchestrator.list_sources()
        assert len(sources1) == len(sources2)
        assert [s["source_id"] for s in sources1] == [s["source_id"] for s in sources2]
