"""Tests for price history service and API - Phase O3 TDD."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    Clinic,
    ClinicBranch,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    PriceHistory,
    PriceObservation,
    Service,
    ServiceCategory,
)
from app.services.price_history_service import PriceHistoryService


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
    """Create test data for price history tests."""
    now = datetime.now(UTC)

    data_source = DataSource(name="test_source", type="external", is_active=True)
    db_session.add(data_source)
    db_session.flush()

    category = ServiceCategory(name="Диагностика", slug="diagnostika", normalized_name="диагностика")
    db_session.add(category)
    db_session.flush()

    service = Service(
        data_source_id=data_source.id,
        category_id=category.id,
        normalized_service_id=1,
        name="МРТ головы",
        normalized_name="мрт головы",
        normalization_status="matched",
    )
    db_session.add(service)
    db_session.flush()

    clinic = Clinic(
        data_source_id=data_source.id,
        external_id="clinic_001",
        name="Test Clinic",
        normalized_name="test clinic",
        city="Астана",
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

    price = ClinicServicePrice(
        clinic_id=clinic.id,
        branch_id=branch.id,
        service_id=service.id,
        normalized_service_id=1,
        price=Decimal("25000"),
        currency="KZT",
        updated_at=datetime.now(UTC).date(),
        source_url="https://example.com/prices",
        parsed_at=now,
    )
    db_session.add(price)
    db_session.flush()

    import_batch = ImportBatch(
        data_source_id=data_source.id,
        status="success",
        received_count=1,
        created_count=1,
    )
    db_session.add(import_batch)
    db_session.flush()

    history = PriceHistory(
        clinic_service_price_id=price.id,
        clinic_id=clinic.id,
        branch_id=branch.id,
        service_id=service.id,
        old_price=None,
        new_price=Decimal("25000"),
        currency="KZT",
        change_type="created",
        import_batch_id=import_batch.id,
        data_source_id=data_source.id,
        source_url="https://example.com/prices",
        parsed_at=now,
        changed_at=now,
    )
    db_session.add(history)
    db_session.flush()

    observation = PriceObservation(
        clinic_service_price_id=price.id,
        clinic_id=clinic.id,
        branch_id=branch.id,
        service_id=service.id,
        normalized_service_id=1,
        import_batch_id=import_batch.id,
        data_source_id=data_source.id,
        price=Decimal("25000"),
        currency="KZT",
        source_updated_at=datetime.now(UTC).date(),
        source_url="https://example.com/prices",
        parsed_at=now,
        change_detected=False,
        observed_at=now,
    )
    db_session.add(observation)
    db_session.flush()

    return {
        "clinic_id": clinic.id,
        "branch_id": branch.id,
        "service_id": service.id,
        "history_id": history.id,
        "observation_id": observation.id,
    }


@pytest.fixture()
def history_service(db_session):
    return PriceHistoryService(db_session)


# ─── History query tests ───

class TestHistoryQuery:
    def test_get_history_returns_items(self, history_service, test_data):
        result = history_service.get_history()
        assert result.total >= 1
        assert len(result.items) >= 1

    def test_get_history_filters_by_clinic(self, history_service, test_data):
        result = history_service.get_history(clinic_id=test_data["clinic_id"])
        assert result.total >= 1
        assert all(item.clinic_id == test_data["clinic_id"] for item in result.items)

    def test_get_history_filters_by_service(self, history_service, test_data):
        result = history_service.get_history(service_id=test_data["service_id"])
        assert result.total >= 1
        assert all(item.service_id == test_data["service_id"] for item in result.items)

    def test_get_history_pagination(self, history_service, test_data):
        result = history_service.get_history(page=1, page_size=1)
        assert len(result.items) <= 1
        assert result.page == 1
        assert result.page_size == 1

    def test_get_history_has_more(self, history_service, test_data):
        # With only 1 record, page_size=1 should not have more
        result = history_service.get_history(page=1, page_size=1)
        assert result.has_more is False

        # With page_size=2, should not have more
        result = history_service.get_history(page=1, page_size=2)
        assert result.has_more is False

    def test_get_history_no_changes(self, history_service, test_data):
        future_date = datetime.now(UTC) + timedelta(days=365)
        result = history_service.get_history(days=1)
        # Should return items within last day
        assert result.total >= 0


# ─── Observation query tests ───

class TestObservationQuery:
    def test_get_observations_returns_items(self, history_service, test_data):
        result = history_service.get_observations()
        assert result.total >= 1
        assert len(result.items) >= 1

    def test_get_observations_filters_by_clinic(self, history_service, test_data):
        result = history_service.get_observations(clinic_id=test_data["clinic_id"])
        assert result.total >= 1
        assert all(item.clinic_id == test_data["clinic_id"] for item in result.items)

    def test_get_observations_filters_by_service(self, history_service, test_data):
        result = history_service.get_observations(service_id=test_data["service_id"])
        assert result.total >= 1
        assert all(item.service_id == test_data["service_id"] for item in result.items)

    def test_get_observations_pagination(self, history_service, test_data):
        result = history_service.get_observations(page=1, page_size=1)
        assert len(result.items) <= 1
        assert result.page == 1


# ─── Stats tests ───

class TestStats:
    def test_get_stats(self, history_service, test_data):
        result = history_service.get_stats()
        assert result.total_changes >= 1
        assert result.total_observations >= 1
        assert result.first_observed is not None
        assert result.last_observed is not None

    def test_get_stats_filters_by_clinic(self, history_service, test_data):
        result = history_service.get_stats(clinic_id=test_data["clinic_id"])
        assert result.total_changes >= 1

    def test_get_stats_price_range(self, history_service, test_data):
        result = history_service.get_stats()
        assert result.price_min is not None
        assert result.price_max is not None
        assert result.price_min <= result.price_max


# ─── Historical label tests ───

class TestHistoricalLabel:
    def test_old_changes_are_historical(self, db_session, test_data):
        old_date = datetime.now(UTC) - timedelta(days=100)
        history = PriceHistory(
            clinic_service_price_id=test_data["clinic_id"],
            clinic_id=test_data["clinic_id"],
            branch_id=test_data["branch_id"],
            service_id=test_data["service_id"],
            old_price=Decimal("20000"),
            new_price=Decimal("25000"),
            currency="KZT",
            change_type="changed",
            import_batch_id=1,
            data_source_id=1,
            changed_at=old_date,
            parsed_at=old_date,
        )
        db_session.add(history)
        db_session.flush()

        service = PriceHistoryService(db_session)
        result = service.get_history(days=365)

        old_items = [item for item in result.items if item.changed_at == old_date]
        assert len(old_items) == 1
        assert old_items[0].is_historical is True

    def test_recent_changes_are_not_historical(self, test_data, history_service):
        result = history_service.get_history()
        recent_items = [item for item in result.items if not item.is_historical]
        assert len(recent_items) >= 1


# ─── API endpoint tests ───

class TestAPIEndpoints:
    def test_history_endpoint(self, client, db_session, test_data):
        response = client.get("/api/v1/prices/history")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_observations_endpoint(self, client, db_session, test_data):
        response = client.get("/api/v1/prices/observations")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_stats_endpoint(self, client, db_session, test_data):
        response = client.get("/api/v1/prices/history/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_changes" in data
        assert "total_observations" in data


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self, history_service, test_data):
        result1 = history_service.get_history()
        result2 = history_service.get_history()
        assert result1.total == result2.total
        assert len(result1.items) == len(result2.items)
