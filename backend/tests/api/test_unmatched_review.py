"""Tests for unmatched service review API - Phase J TDD."""

from __future__ import annotations

import os
from datetime import UTC, datetime

# Set database URL before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.models import (
    DataSource,
    NormalizedService,
    Service,
    ServiceCategory,
    UnmatchedServiceRecord,
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
def api_key():
    from app.core.config import settings
    return settings.import_api_key


@pytest.fixture()
def test_data(db_session):
    """Create test data for unmatched service tests."""
    # Create data source
    data_source = DataSource(name="test_source", type="external", is_active=True)
    db_session.add(data_source)
    db_session.flush()

    # Create category
    category = ServiceCategory(
        name="Диагностика",
        slug="diagnostika",
        normalized_name="диагностика",
    )
    db_session.add(category)
    db_session.flush()

    # Create normalized service
    normalized_service = NormalizedService(
        category_id=category.id,
        name="мрт головы",
        slug="diagnostika-mrt-golovy",
        aliases=[],
    )
    db_session.add(normalized_service)
    db_session.flush()

    # Create unmatched records
    records = [
        UnmatchedServiceRecord(
            data_source_id=data_source.id,
            raw_category="Диагностика",
            raw_name="МРТ головного мозга",
            normalized_raw_category="диагностика",
            normalized_raw_name="мрт головного мозга",
            status="open",
            confidence=0,
            reason="No catalog match found",
            occurrence_count=5,
        ),
        UnmatchedServiceRecord(
            data_source_id=data_source.id,
            raw_category="Анализы",
            raw_name="Общий анализ крови (ОАК)",
            normalized_raw_category="анализы",
            normalized_raw_name="общий анализ крови (оак)",
            status="open",
            confidence=0,
            reason="No catalog match found",
            occurrence_count=3,
        ),
        UnmatchedServiceRecord(
            data_source_id=data_source.id,
            raw_category="Консультации",
            raw_name="Прием терапевта",
            normalized_raw_category="консультации",
            normalized_raw_name="прием терапевта",
            status="approved",
            confidence=1.0,
            reason="Approved by admin",
            reviewed_at=datetime.now(UTC),
            reviewed_by="admin",
            review_action="approve_to_existing",
            occurrence_count=2,
        ),
    ]
    for record in records:
        db_session.add(record)
    db_session.flush()

    return {
        "data_source_id": data_source.id,
        "category_id": category.id,
        "normalized_service_id": normalized_service.id,
        "record_ids": [r.id for r in records],
    }


# ─── List endpoint tests ───

class TestListUnmatched:
    def test_list_returns_all_records(self, client, api_key, test_data):
        response = client.get(
            "/api/v1/unmatched",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_filters_by_status(self, client, api_key, test_data):
        response = client.get(
            "/api/v1/unmatched?status=open",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(item["status"] == "open" for item in data["items"])

    def test_list_filters_by_source(self, client, api_key, test_data):
        response = client.get(
            f"/api/v1/unmatched?source_id={test_data['data_source_id']}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    def test_list_pagination(self, client, api_key, test_data):
        response = client.get(
            "/api/v1/unmatched?page=1&page_size=2",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) == 2

    def test_list_requires_api_key(self, client, test_data):
        response = client.get("/api/v1/unmatched")
        assert response.status_code == 401


# ─── Detail endpoint tests ───

class TestDetailUnmatched:
    def test_get_detail_returns_record(self, client, api_key, test_data):
        record_id = test_data["record_ids"][0]
        response = client.get(
            f"/api/v1/unmatched/{record_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == record_id
        assert data["status"] == "open"

    def test_get_detail_returns_404_for_missing(self, client, api_key, test_data):
        response = client.get(
            "/api/v1/unmatched/99999",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404


# ─── Review endpoint tests ───

class TestReviewUnmatched:
    def test_approve_to_existing(self, client, api_key, test_data):
        record_id = test_data["record_ids"][0]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "approve_to_existing",
                "target_normalized_service_id": test_data["normalized_service_id"],
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action"] == "approve_to_existing"

    def test_approve_with_new_synonym(self, client, api_key, test_data):
        record_id = test_data["record_ids"][1]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "approve_with_new_synonym",
                "target_normalized_service_id": test_data["normalized_service_id"],
                "new_synonym": "ОАК",
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "synonym" in data["message"].lower()

    def test_reject(self, client, api_key, test_data):
        record_id = test_data["record_ids"][0]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "reject",
                "reason": "Not a medical service",
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action"] == "reject"

    def test_needs_clarification(self, client, api_key, test_data):
        record_id = test_data["record_ids"][0]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "needs_clarification",
                "reason": "Need to verify service name",
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action"] == "needs_clarification"

    def test_ignore(self, client, api_key, test_data):
        record_id = test_data["record_ids"][0]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "ignore",
                "reason": "Duplicate entry",
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action"] == "ignore"

    def test_cannot_review_already_reviewed(self, client, api_key, test_data):
        record_id = test_data["record_ids"][2]  # Already approved
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "reject",
                "reason": "Changed mind",
                "reviewer": "test_admin",
            },
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 400

    def test_review_requires_api_key(self, client, test_data):
        record_id = test_data["record_ids"][0]
        response = client.post(
            f"/api/v1/unmatched/{record_id}/review",
            json={
                "action": "reject",
                "reason": "Test",
                "reviewer": "test_admin",
            },
        )
        assert response.status_code == 401


# ─── Stats endpoint tests ───

class TestUnmatchedStats:
    def test_get_stats(self, client, api_key, test_data):
        response = client.get(
            "/api/v1/unmatched/stats/overview",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["open"] == 2
        assert data["approved"] == 1
