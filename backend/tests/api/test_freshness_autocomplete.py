"""Tests for freshness service and autocomplete - Phase M TDD."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta

# Set database URL before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from app.core.database import Base
from app.models import NormalizedService, ServiceCategory, UnmatchedServiceRecord
from app.services.freshness_service import (
    FreshnessInfo,
    freshness_badge,
    price_freshness,
)
from app.services.autocomplete_service import AutocompleteService
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
def autocomplete_service(db_session):
    return AutocompleteService(db_session)


# ─── Freshness contract tests ───

class TestFreshnessContract:
    def test_fresh_within_30_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 6, 20, tzinfo=UTC)  # 7 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "fresh"
        assert result.age_days == 7

    def test_stale_at_31_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 5, 27, tzinfo=UTC)  # 31 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "stale"
        assert result.age_days == 31
        assert result.warning is not None

    def test_stale_at_90_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 3, 29, tzinfo=UTC)  # 90 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "stale"
        assert result.age_days == 90

    def test_expired_at_91_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 3, 28, tzinfo=UTC)  # 91 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "expired"
        assert result.age_days == 91
        assert result.warning is not None

    def test_expired_at_100_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 3, 19, tzinfo=UTC)  # 100 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "expired"
        assert result.age_days == 100

    def test_unknown_when_no_parsed_at(self):
        result = price_freshness(None)
        assert result.state == "unknown"
        assert result.age_days is None

    def test_fresh_at_0_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 6, 27, tzinfo=UTC)
        result = price_freshness(parsed_at, now=now)
        assert result.state == "fresh"
        assert result.age_days == 0

    def test_fresh_at_30_days(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        parsed_at = datetime(2026, 5, 28, tzinfo=UTC)  # 30 days ago
        result = price_freshness(parsed_at, now=now)
        assert result.state == "fresh"
        assert result.age_days == 30

    def test_timezone_handling(self):
        now = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
        parsed_at = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        result = price_freshness(parsed_at, now=now)
        assert result.state == "fresh"
        assert result.age_days == 7

    def test_uses_updated_at_when_no_parsed_at(self):
        now = datetime(2026, 6, 27, tzinfo=UTC)
        updated_at = date(2026, 6, 20)
        result = price_freshness(None, updated_at=updated_at, now=now)
        assert result.state == "fresh"
        assert result.age_days == 7


# ─── Freshness badge tests ───

class TestFreshnessBadge:
    def test_fresh_badge(self):
        badge = freshness_badge("fresh")
        assert badge["label"] == "Fresh"
        assert badge["color"] == "green"

    def test_stale_badge(self):
        badge = freshness_badge("stale")
        assert badge["label"] == "Stale"
        assert badge["color"] == "yellow"

    def test_expired_badge(self):
        badge = freshness_badge("expired")
        assert badge["label"] == "Expired"
        assert badge["color"] == "red"

    def test_unknown_badge(self):
        badge = freshness_badge("unknown")
        assert badge["label"] == "Unknown"
        assert badge["color"] == "gray"


# ─── Autocomplete tests ───

class TestAutocomplete:
    def test_empty_query_returns_no_suggestions(self, autocomplete_service):
        result = autocomplete_service.autocomplete("")
        assert len(result.suggestions) == 0

    def test_short_query_returns_no_suggestions(self, autocomplete_service):
        result = autocomplete_service.autocomplete("a")
        assert len(result.suggestions) == 0

    def test_canonical_match(self, autocomplete_service, db_session):
        category = ServiceCategory(name="Диагностика", slug="diagnostika", normalized_name="диагностика")
        db_session.add(category)
        db_session.flush()

        service = NormalizedService(
            category_id=category.id,
            name="мрт головы",
            slug="diagnostika-mrt-golovy",
            aliases=[],
        )
        db_session.add(service)
        db_session.flush()

        result = autocomplete_service.autocomplete("мрт")
        assert len(result.suggestions) >= 1
        assert any(s.type == "canonical" for s in result.suggestions)

    def test_synonym_match(self, autocomplete_service):
        result = autocomplete_service.autocomplete("оак")
        assert len(result.suggestions) >= 1
        assert any(s.type == "synonym" for s in result.suggestions)

    def test_unmatched_match(self, autocomplete_service, db_session):
        from app.models import DataSource
        data_source = DataSource(name="test", type="test", is_active=True)
        db_session.add(data_source)
        db_session.flush()

        record = UnmatchedServiceRecord(
            data_source_id=data_source.id,
            raw_category="Тест",
            raw_name="Неизвестный анализ",
            normalized_raw_category="тест",
            normalized_raw_name="неизвестный анализ",
            status="open",
            confidence=0,
            reason="No match",
            occurrence_count=10,
        )
        db_session.add(record)
        db_session.flush()

        result = autocomplete_service.autocomplete("неизвестный")
        assert len(result.suggestions) >= 1
        assert any(s.type == "unmatched" for s in result.suggestions)

    def test_limit_results(self, autocomplete_service, db_session):
        category = ServiceCategory(name="Тест", slug="test", normalized_name="тест")
        db_session.add(category)
        db_session.flush()

        for i in range(10):
            service = NormalizedService(
                category_id=category.id,
                name=f"тест услуга {i}",
                slug=f"test-service-{i}",
                aliases=[],
            )
            db_session.add(service)
        db_session.flush()

        result = autocomplete_service.autocomplete("тест", limit=5)
        assert len(result.suggestions) <= 5

    def test_deduplicates_suggestions(self, autocomplete_service, db_session):
        category = ServiceCategory(name="Тест", slug="test", normalized_name="тест")
        db_session.add(category)
        db_session.flush()

        service = NormalizedService(
            category_id=category.id,
            name="мрт головы",
            slug="test-mrt",
            aliases=["мрт", "mri"],
        )
        db_session.add(service)
        db_session.flush()

        result = autocomplete_service.autocomplete("мрт")
        texts = [s.text for s in result.suggestions]
        assert len(texts) == len(set(texts))


# ─── CLI parsing tests ───

class TestCLIParsing:
    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "app.scripts.run_parser", "--help"],
            capture_output=True,
            text=True,
            cwd="/mnt/d/projects/aggregator-mimo/backend",
        )
        assert result.returncode == 0
        assert "parser" in result.stdout.lower() or "run" in result.stdout.lower()
