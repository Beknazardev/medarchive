"""Tests for generic city/regional clinic document adapter - Phase H TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.city_clinic_document import (
    ADAPTER_VERSION,
    MappingProfile,
    extract_with_profile,
    load_profile,
    to_scraped_contract,
    to_import_payload,
    ExtractedRow,
    ProfileExtractionResult,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "city_clinic_document"
PROFILE_DIR = Path(__file__).parent.parent.parent / "profiles"
SOURCE_URL = "https://example-clinic.kz/prices/"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="city_clinic_document",
        requested_url=SOURCE_URL,
        final_url=SOURCE_URL,
        content_type="text/html",
        status_code=200,
        content_bytes=content,
        byte_size=len(content),
        content_sha256=digest,
        captured_at=datetime(2026, 6, 27, tzinfo=UTC),
    )


# ─── Profile loading tests ───

class TestProfileLoading:
    def test_loads_valid_profile(self):
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        assert profile.profile_id == "demo_city_clinic"
        assert profile.profile_version == "1.0.0"
        assert profile.clinic.city == "Астана"

    def test_profile_rejects_invalid_checksum(self):
        import json
        profile_data = json.loads((PROFILE_DIR / "demo_city_clinic.json").read_text())
        profile_data["expected_checksums"] = ["invalid"]
        with pytest.raises(Exception):
            MappingProfile.model_validate(profile_data)

    def test_profile_validates_column_indices(self):
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        assert profile.columns.service_name >= 0
        assert profile.columns.price >= 0


# ─── Extraction tests ───

class TestExtraction:
    def test_extracts_rows_from_valid_document(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        assert isinstance(result, ProfileExtractionResult)
        assert result.profile_id == "demo_city_clinic"
        assert len(result.accepted) == 8

    def test_extracts_service_names(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        names = [r.service_name for r in result.accepted]
        assert len(names) >= 5
        assert all(len(n) > 0 for n in names)

    def test_extracts_prices(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        prices = {r.service_name: r.price for r in result.accepted}
        assert Decimal("5000") in prices.values()
        assert Decimal("1200") in prices.values()

    def test_extracts_codes(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        codes = [r.code for r in result.accepted]
        assert "001" in codes

    def test_quarantines_invalid_price(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Код</th><th>Услуга</th><th>Цена</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Услуга А</td><td>нед цена</td></tr>
        <tr><td>2</td><td>Услуга Б</td><td>1000</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="city_clinic_document",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        assert len(result.quarantined) >= 1
        assert len(result.accepted) >= 1

    def test_rejects_empty_service_name(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Код</th><th>Услуга</th><th>Цена</th></tr></thead>
        <tbody>
        <tr><td>1</td><td></td><td>1000</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="city_clinic_document",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        assert len(result.rejected) >= 1

    def test_respects_price_bounds(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Код</th><th>Услуга</th><th>Цена</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Дешевая услуга</td><td>50</td></tr>
        <tr><td>2</td><td>Дорогая услуга</td><td>10000000</td></tr>
        <tr><td>3</td><td>Нормальная услуга</td><td>5000</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="city_clinic_document",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        assert len(result.quarantined) >= 2
        assert len(result.accepted) == 1
        assert len(result.accepted[0].service_name) > 0

    def test_handles_table_not_found(self):
        html = """<html><body><p>No tables here</p></body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="city_clinic_document",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result = extract_with_profile(doc, profile)
        assert len(result.accepted) == 0
        assert len(result.errors) >= 1


# ─── Contract transform tests ───

class TestContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "city_clinic_document"
        assert len(contract["rows"]) == 8

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["adapter"]["name"] == "city_clinic_document"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "demo_city_clinic"
        assert clinic["name"] == "Демо Городская Поликлиника"
        assert clinic["city"] == "Астана"

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        for row in contract["rows"]:
            assert "row_id" in row
            assert "service_name_raw" in row
            assert "price" in row
            assert "currency" in row
            assert "updated_at" in row
            assert "source_url" in row
            assert "parsed_at" in row


# ─── Import payload tests ───

class TestImportPayload:
    def test_produces_valid_import_payload(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        payload = to_import_payload(contract)
        assert payload.source == "city_clinic_document"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) == 8

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        extraction = extract_with_profile(doc, profile)
        contract = to_scraped_contract(extraction, profile, doc)
        payload = to_import_payload(contract)
        for service in payload.services:
            assert "external_id" in service
            assert "name" in service
            assert "price" in service
            assert "currency" in service
            assert "updated_at" in service
            assert "source_url" in service
            assert "parsed_at" in service


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "demo_prices.html")
        profile = load_profile(PROFILE_DIR / "demo_city_clinic.json")
        result1 = extract_with_profile(doc, profile)
        result2 = extract_with_profile(doc, profile)
        assert len(result1.accepted) == len(result2.accepted)
        for r1, r2 in zip(result1.accepted, result2.accepted):
            assert r1.service_name == r2.service_name
            assert r1.price == r2.price


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
