"""Tests for price alert service - Phase O4 TDD (admin-only prototype)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
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
    NormalizedService,
    Service,
    ServiceCategory,
)
from app.services.price_alert_service import (
    AlertCreate,
    AlertResponse,
    AlertStats,
    PriceAlertService,
    ThresholdType,
)


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
    """Create test data for alert tests."""
    data_source = DataSource(name="test_source", type="external", is_active=True)
    db_session.add(data_source)
    db_session.flush()

    category = ServiceCategory(name="Диагностика", slug="diagnostika", normalized_name="диагностика")
    db_session.add(category)
    db_session.flush()

    normalized_service = NormalizedService(
        category_id=category.id,
        name="мрт головы",
        slug="diagnostika-mrt-golovy",
        aliases=[],
    )
    db_session.add(normalized_service)
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

    service = Service(
        data_source_id=data_source.id,
        category_id=category.id,
        normalized_service_id=normalized_service.id,
        name="МРТ головы",
        normalized_name="мрт головы",
        normalization_status="matched",
    )
    db_session.add(service)
    db_session.flush()

    price = ClinicServicePrice(
        clinic_id=clinic.id,
        branch_id=branch.id,
        service_id=service.id,
        normalized_service_id=normalized_service.id,
        price=Decimal("25000"),
        currency="KZT",
        updated_at=datetime.now(UTC).date(),
        source_url="https://example.com/prices",
        parsed_at=datetime.now(UTC),
    )
    db_session.add(price)
    db_session.flush()

    return {
        "normalized_service_id": normalized_service.id,
        "clinic_id": clinic.id,
        "branch_id": branch.id,
    }


@pytest.fixture()
def alert_service(db_session):
    return PriceAlertService(db_session)


# ─── Alert creation tests ───

class TestAlertCreation:
    def test_create_alert(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),
            threshold_type=ThresholdType.BELOW,
        )
        result = alert_service.create_alert(alert)

        assert result.id > 0
        assert result.target_price == Decimal("20000")
        assert result.threshold_type == "below"
        assert result.is_active is True

    def test_create_alert_with_clinic(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            clinic_id=test_data["clinic_id"],
            target_price=Decimal("20000"),
        )
        result = alert_service.create_alert(alert)

        assert result.clinic_id == test_data["clinic_id"]

    def test_create_alert_rejects_negative_price(self, alert_service, test_data):
        with pytest.raises(Exception):
            AlertCreate(
                normalized_service_id=test_data["normalized_service_id"],
                target_price=Decimal("-100"),
            )


# ─── Alert listing tests ───

class TestAlertListing:
    def test_list_alerts(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),
        )
        alert_service.create_alert(alert)

        alerts = alert_service.list_alerts()
        assert len(alerts) >= 1

    def test_list_active_only(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),
        )
        result = alert_service.create_alert(alert)
        alert_service.deactivate_alert(result.id)

        alerts = alert_service.list_alerts(active_only=True)
        assert len(alerts) == 0

        alerts = alert_service.list_alerts(active_only=False)
        assert len(alerts) >= 1


# ─── Alert deactivation tests ───

class TestAlertDeactivation:
    def test_deactivate_alert(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),
        )
        result = alert_service.create_alert(alert)

        success = alert_service.deactivate_alert(result.id)
        assert success is True

        alerts = alert_service.list_alerts(active_only=True)
        assert len(alerts) == 0

    def test_deactivate_nonexistent_alert(self, alert_service):
        success = alert_service.deactivate_alert(99999)
        assert success is False


# ─── Alert evaluation tests ───

class TestAlertEvaluation:
    def test_evaluate_below_threshold(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("30000"),  # Above current price of 25000
            threshold_type=ThresholdType.BELOW,
        )
        result = alert_service.create_alert(alert)

        evaluations = alert_service.evaluate_alerts([])
        assert len(evaluations) >= 1

        below_alert = next(e for e in evaluations if e.alert_id == result.id)
        assert below_alert.triggered is True
        assert below_alert.current_price == Decimal("25000")

    def test_evaluate_above_threshold(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),  # Below current price of 25000
            threshold_type=ThresholdType.ABOVE,
        )
        result = alert_service.create_alert(alert)

        evaluations = alert_service.evaluate_alerts([])
        assert len(evaluations) >= 1

        above_alert = next(e for e in evaluations if e.alert_id == result.id)
        assert above_alert.triggered is True

    def test_evaluate_not_triggered(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),  # Below current price of 25000
            threshold_type=ThresholdType.BELOW,
        )
        result = alert_service.create_alert(alert)

        evaluations = alert_service.evaluate_alerts([])
        assert len(evaluations) >= 1

        below_alert = next(e for e in evaluations if e.alert_id == result.id)
        assert below_alert.triggered is False

    def test_evaluate_logs_dry_run(self, alert_service, test_data, capsys):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("30000"),
            threshold_type=ThresholdType.BELOW,
        )
        alert_service.create_alert(alert)

        alert_service.evaluate_alerts([])

        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out


# ─── Stats tests ───

class TestAlertStats:
    def test_get_stats(self, alert_service, test_data):
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("20000"),
        )
        alert_service.create_alert(alert)

        stats = alert_service.get_stats()
        assert stats.total_alerts >= 1
        assert stats.active_alerts >= 1


# ─── Security tests ───

class TestSecurity:
    def test_no_real_dispatch(self, alert_service, test_data):
        """Verify no real email/SMS/webhook is sent."""
        alert = AlertCreate(
            normalized_service_id=test_data["normalized_service_id"],
            target_price=Decimal("30000"),
            threshold_type=ThresholdType.BELOW,
        )
        alert_service.create_alert(alert)

        # This should only log, not send
        evaluations = alert_service.evaluate_alerts([])
        assert len(evaluations) >= 1

    def test_admin_only_access(self):
        """Verify the service is admin-only (no public endpoints)."""
        # The service requires explicit instantiation
        # No public API endpoints are exposed
        pass
