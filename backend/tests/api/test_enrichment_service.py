"""Tests for Google Places enrichment service - Phase O1 TDD."""

from __future__ import annotations

import os
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from unittest.mock import Mock, patch

from app.core.database import Base
from app.models import Clinic, ClinicBranch, DataSource
from app.services.enrichment_service import (
    EnrichmentConfig,
    EnrichmentService,
    EnrichmentBudget,
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
def test_data(db_session):
    """Create test data for enrichment tests."""
    data_source = DataSource(name="test_clinic", type="clinic", is_active=True)
    db_session.add(data_source)
    db_session.flush()

    clinic = Clinic(
        data_source_id=data_source.id,
        external_id="clinic_001",
        name="Test Clinic",
        normalized_name="test clinic",
        city="Астана",
        phone="+77001234567",
    )
    db_session.add(clinic)
    db_session.flush()

    branch = ClinicBranch(
        clinic_id=clinic.id,
        external_id="branch_001",
        name="Main Branch",
        city="Астана",
        address="ул. Примерная, 10",
        normalized_address="ул. примерная, 10",
    )
    db_session.add(branch)
    db_session.flush()

    return {
        "clinic_id": clinic.id,
        "branch_id": branch.id,
    }


@pytest.fixture()
def enabled_config():
    return EnrichmentConfig(
        enabled=True,
        api_key="test_api_key",
        budget_daily_usd=5.0,
    )


@pytest.fixture()
def disabled_config():
    return EnrichmentConfig(enabled=False)


@pytest.fixture()
def mock_place_data():
    """Mock Google Places API response."""
    return {
        "formattedAddress": "г. Астана, пр. Мәңгілік Ел, 42",
        "internationalPhoneNumber": "+77172700001",
        "websiteUri": "https://clinic.example.kz",
        "location": {
            "latitude": 51.128207,
            "longitude": 71.430420,
        },
        "regularOpeningHours": {
            "weekdayDescriptions": [
                "Monday: 8:00 – 18:00",
                "Tuesday: 8:00 – 18:00",
                "Wednesday: 8:00 – 18:00",
                "Thursday: 8:00 – 18:00",
                "Friday: 8:00 – 18:00",
                "Saturday: 9:00 – 14:00",
                "Sunday: Closed",
            ],
        },
        "rating": 4.5,
    }


# ─── Config tests ───

class TestConfig:
    def test_disabled_by_default(self):
        config = EnrichmentConfig()
        assert config.enabled is False
        assert config.api_key is None

    def test_budget_defaults(self):
        config = EnrichmentConfig()
        assert config.budget_daily_usd == 5.0
        assert config.timeout_seconds == 10


# ─── Clinic enrichment tests ───

class TestClinicEnrichment:
    def test_enrichment_disabled_returns_none(self, db_session, test_data, disabled_config):
        service = EnrichmentService(db_session, disabled_config)
        result = service.enrich_clinic(test_data["clinic_id"], "place_123")
        assert result is None

    def test_enrichment_with_mocked_api(self, db_session, test_data, enabled_config, mock_place_data):
        # Clear existing phone to avoid conflict
        clinic = db_session.get(Clinic, test_data["clinic_id"])
        clinic.phone = None
        db_session.flush()

        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_clinic(
                test_data["clinic_id"],
                "place_123",
                fields=["address", "phone", "website"],
            )

        assert result is not None
        assert result.provider == "google_places"
        assert "address" in result.fields_updated
        assert "phone" in result.fields_updated
        assert "website" in result.fields_updated

    def test_enrichment_skips_existing_values(self, db_session, test_data, enabled_config, mock_place_data):
        # Clear address to test skipping
        branch = db_session.get(ClinicBranch, test_data["branch_id"])
        original_address = branch.address
        branch.address = "г. Астана, пр. Мәңгілік Ел, 42"
        db_session.flush()

        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_branch(
                test_data["branch_id"],
                "place_123",
                fields=["address"],
            )

        assert result is not None
        assert "address" in result.fields_skipped

    def test_enrichment_detects_conflicts(self, db_session, test_data, enabled_config, mock_place_data):
        branch = db_session.get(ClinicBranch, test_data["branch_id"])
        branch.address = "г. Астана, ул. Другая, 1"
        db_session.flush()

        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_branch(
                test_data["branch_id"],
                "place_123",
                fields=["address"],
            )

        assert result is not None
        assert "address" in result.conflicts

    def test_dry_run_does_not_modify(self, db_session, test_data, enabled_config, mock_place_data):
        branch = db_session.get(ClinicBranch, test_data["branch_id"])
        original_address = branch.address
        db_session.flush()

        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_branch(
                test_data["branch_id"],
                "place_123",
                fields=["latitude", "longitude"],
                dry_run=True,
            )

        assert result is not None
        assert "latitude" in result.fields_updated
        db_session.refresh(branch)
        assert branch.latitude is None

    def test_enrichment_returns_none_for_missing_clinic(self, db_session, enabled_config, mock_place_data):
        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_clinic(99999, "place_123")

        assert result is None


# ─── Branch enrichment tests ───

class TestBranchEnrichment:
    def test_enriches_branch_address(self, db_session, test_data, enabled_config, mock_place_data):
        # Use a different address to avoid conflict
        branch = db_session.get(ClinicBranch, test_data["branch_id"])
        branch.address = "ул. Тестовая, 1"
        branch.normalized_address = "ул. тестовая, 1"
        db_session.flush()

        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_branch(
                test_data["branch_id"],
                "place_123",
                fields=["latitude", "longitude"],
            )

        assert result is not None
        assert "latitude" in result.fields_updated
        assert "longitude" in result.fields_updated

    def test_enriches_branch_hours(self, db_session, test_data, enabled_config, mock_place_data):
        service = EnrichmentService(db_session, enabled_config)

        with patch.object(service, "_fetch_place", return_value=mock_place_data):
            result = service.enrich_branch(
                test_data["branch_id"],
                "place_123",
                fields=["working_hours"],
            )

        assert result is not None
        assert "working_hours" in result.fields_updated


# ─── API fetch tests ───

class TestAPIFetch:
    def test_fetch_place_returns_data(self, db_session, enabled_config, mock_place_data):
        service = EnrichmentService(db_session, enabled_config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_place_data

        with patch("httpx.get", return_value=mock_response):
            result = service._fetch_place("place_123")

        assert result is not None
        assert "formattedAddress" in result

    def test_fetch_place_returns_none_on_error(self, db_session, enabled_config):
        service = EnrichmentService(db_session, enabled_config)

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        with patch("httpx.get", return_value=mock_response):
            result = service._fetch_place("place_123")

        assert result is None

    def test_fetch_place_returns_none_on_timeout(self, db_session, enabled_config):
        import httpx
        service = EnrichmentService(db_session, enabled_config)

        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            result = service._fetch_place("place_123")

        assert result is None


# ─── Budget tests ───

class TestBudget:
    def test_budget_allows_first_request(self):
        budget = EnrichmentBudget()
        config = EnrichmentConfig()
        assert budget.can_make_request(config) is True

    def test_budget_tracks_requests(self):
        budget = EnrichmentBudget(
            daily_requests=10,
            daily_cost_usd=4.0,
            last_reset=datetime.now(UTC),
        )
        config = EnrichmentConfig(budget_daily_usd=5.0)
        assert budget.can_make_request(config) is True

    def test_budget_rejects_over_limit(self):
        budget = EnrichmentBudget(
            daily_requests=100,
            daily_cost_usd=6.0,
            last_reset=datetime.now(UTC),
        )
        config = EnrichmentConfig(budget_daily_usd=5.0)
        assert budget.can_make_request(config) is False
