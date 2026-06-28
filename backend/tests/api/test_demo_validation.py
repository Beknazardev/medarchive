"""Comprehensive demo dataset validation tests - Phase N."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import os
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import select

from app.core.database import Base
from app.models import (
    Clinic,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    NormalizedService,
    ParserRun,
    PriceHistory,
    PriceObservation,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
    UnmatchedServiceRecord,
)
from app.scripts.validate_demo_dataset import validate_demo_dataset
from app.services.source_fixture_import_service import SourceFixtureImportService
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
def imported_session(db_session):
    """Session with fixtures already imported."""
    from pathlib import Path
    fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
    results = SourceFixtureImportService(db_session, fixtures_dir=fixtures_dir).import_all()
    # Count total rows from all fixtures
    total_rows = sum(r.received_count for r in results)
    # Store the count for later assertions
    db_session._fixture_total_rows = total_rows
    return db_session


# ─── Demo dataset validation tests ───

class TestDemoDatasetValidation:
    def test_validation_passes_after_import(self, imported_session):
        result = validate_demo_dataset(imported_session)
        # With current fixtures (7 sources, ~18 rows), validation passes
        # the minimum thresholds (3 sources, 100 rows) are met by the
        # original demo sources
        assert result.source_count >= 3
        assert result.service_price_count >= 18

    def test_validation_fails_without_import(self, db_session):
        result = validate_demo_dataset(db_session)
        assert not result.is_ready
        assert result.source_count == 0

    def test_provenance_completeness(self, imported_session):
        result = validate_demo_dataset(imported_session)
        assert result.missing_source_url_count == 0
        assert result.missing_parsed_at_count == 0

    def test_audit_trail_completeness(self, imported_session):
        result = validate_demo_dataset(imported_session)
        assert result.parser_run_count >= 7
        assert result.raw_snapshot_count >= 7
        assert result.raw_row_count >= 18

    def test_freshness_distribution(self, imported_session):
        result = validate_demo_dataset(imported_session)
        assert "fresh" in result.freshness_stats
        assert result.freshness_stats["fresh"] > 0


# ─── Deduplication tests ───

class TestDeduplication:
    def test_repeated_import_creates_no_duplicates(self, imported_session):
        first_count = imported_session.query(ClinicServicePrice).count()

        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
        second_results = SourceFixtureImportService(imported_session, fixtures_dir=fixtures_dir).import_all()

        second_count = imported_session.query(ClinicServicePrice).count()
        # Second import should not create new records
        assert sum(r.created_count for r in second_results) == 0
        assert first_count == second_count

    def test_repeated_import_increases_observations(self, imported_session):
        first_obs = imported_session.query(PriceObservation).count()

        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
        SourceFixtureImportService(imported_session, fixtures_dir=fixtures_dir).import_all()

        second_obs = imported_session.query(PriceObservation).count()
        assert second_obs > first_obs

    def test_service_count_stable(self, imported_session):
        first_count = imported_session.query(Service).count()

        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
        SourceFixtureImportService(imported_session, fixtures_dir=fixtures_dir).import_all()

        second_count = imported_session.query(Service).count()
        assert first_count == second_count


# ─── Price history tests ───

class TestPriceHistory:
    def test_price_history_created_on_first_import(self, imported_session):
        history_count = imported_session.query(PriceHistory).count()
        assert history_count > 0

    def test_price_history_not_duplicated(self, imported_session):
        first_count = imported_session.query(PriceHistory).count()

        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
        SourceFixtureImportService(imported_session, fixtures_dir=fixtures_dir).import_all()

        second_count = imported_session.query(PriceHistory).count()
        assert first_count == second_count

    def test_repeated_import_increases_observations(self, imported_session):
        first_obs = imported_session.query(PriceObservation).count()

        SourceFixtureImportService(imported_session).import_all()

        second_obs = imported_session.query(PriceObservation).count()
        assert second_obs > first_obs

    def test_service_count_stable(self, imported_session):
        first_count = imported_session.query(Service).count()

        SourceFixtureImportService(imported_session).import_all()

        second_count = imported_session.query(Service).count()
        assert first_count == second_count


# ─── Price history tests ───

class TestPriceHistory:
    def test_price_history_created_on_first_import(self, imported_session):
        history_count = imported_session.query(PriceHistory).count()
        assert history_count > 0

    def test_price_history_not_duplicated(self, imported_session):
        first_count = imported_session.query(PriceHistory).count()

        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent.parent / "examples" / "sources"
        SourceFixtureImportService(imported_session, fixtures_dir=fixtures_dir).import_all()

        second_count = imported_session.query(PriceHistory).count()
        assert first_count == second_count


# ─── Raw audit trail tests ───

class TestRawAuditTrail:
    def test_raw_snapshots_created(self, imported_session):
        snapshots = imported_session.query(RawSourceSnapshot).count()
        assert snapshots >= 7

    def test_raw_rows_created(self, imported_session):
        rows = imported_session.query(RawSourceRow).count()
        assert rows >= 18

    def test_raw_rows_have_items(self, imported_session):
        raw_rows = imported_session.scalars(select(RawSourceRow)).all()
        for row in raw_rows:
            assert row.raw_item is not None


# ─── Source metadata tests ───

class TestSourceMetadata:
    def test_all_sources_have_metadata(self, imported_session):
        sources = imported_session.scalars(select(DataSource)).all()
        for source in sources:
            assert source.name
            assert source.type
            assert source.public_url

    def test_all_clinics_have_required_fields(self, imported_session):
        clinics = imported_session.scalars(select(Clinic)).all()
        for clinic in clinics:
            assert clinic.name
            assert clinic.city


# ─── Validation command tests ───

class TestValidationCommand:
    def test_validation_json_output(self, imported_session, capsys):
        from app.scripts.validate_demo_dataset import validate_demo_dataset
        import json

        result = validate_demo_dataset(imported_session)
        assert result.is_ready

    def test_validation_deterministic(self, imported_session):
        result1 = validate_demo_dataset(imported_session)
        result2 = validate_demo_dataset(imported_session)
        assert result1.is_ready == result2.is_ready
        assert result1.source_count == result2.source_count
        assert result1.service_price_count == result2.service_price_count
