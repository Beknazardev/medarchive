"""Tests for GPK/Hippokrat adapter - Phase F6 TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.gpk_hippokrat import (
    ADAPTER_VERSION,
    extract_gpk_hippokrat,
    transform_to_scraped_contract,
    transform_to_import_payload,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gpk_hippokrat"
SOURCE_URL = "https://gpk.kz/%D0%BF%D1%80%D0%B0%D0%B9%D1%81-%D0%BB%D0%B8%D1%81%D1%82"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="gpk_hippokrat",
        requested_url=SOURCE_URL,
        final_url=SOURCE_URL,
        content_type="text/html",
        status_code=200,
        content_bytes=content,
        byte_size=len(content),
        content_sha256=digest,
        captured_at=datetime(2026, 6, 27, tzinfo=UTC),
    )


# ─── Adapter extraction tests ───

class TestGpkHippokratExtraction:
    def test_extracts_all_rows_from_valid_fixture(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "gpk_hippokrat"
        assert len(result.candidates) >= 60

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert any("Общий анализ крови" in n for n in names)
        assert any("Почки" in n for n in names)

    def test_extracts_exact_prices(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        blood_tests = {k: v for k, v in prices.items() if "Общий анализ крови" in k}
        assert len(blood_tests) >= 1
        assert any(v == Decimal("1300") for v in blood_tests.values())
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_section_headings(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        sections = [c.raw_payload.get("section") for c in result.candidates]
        assert "Поликлинический врачебный прием" in sections
        assert "Лаборатория" in sections
        assert "УЗИ" in sections

    def test_splits_primary_repeat_consultations(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        urology = [c for c in result.candidates if "уролог" in c.service_name_raw.lower()]
        assert len(urology) >= 2
        prices = [c.price for c in urology]
        assert Decimal("7000") in prices
        assert Decimal("6000") in prices

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None

    def test_sets_source_url(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        for candidate in result.candidates:
            assert candidate.source_url == SOURCE_URL

    def test_sets_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        for candidate in result.candidates:
            assert candidate.source_id == "gpk_hippokrat"
            assert candidate.clinic_name == "Гиппократ"
            assert candidate.clinic_city == "Костанай"

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "row_number" in candidate.raw_payload
            assert "cells" in candidate.raw_payload

    def test_rejects_header_section_rows(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result = extract_gpk_hippokrat(doc)
        for candidate in result.candidates:
            assert candidate.price is not None
            assert candidate.price > 0

    def test_detects_schema_drift_on_wrong_headings(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Wrong</th><th>Headers</th><th>More</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Service A</td><td>100</td></tr>
        <tr><td>2</td><td>Service B</td><td>200</td></tr>
        <tr><td>3</td><td>Service C</td><td>300</td></tr>
        <tr><td>4</td><td>Service D</td><td>400</td></tr>
        <tr><td>5</td><td>Service E</td><td>500</td></tr>
        <tr><td>6</td><td>Service F</td><td>600</td></tr>
        <tr><td>7</td><td>Service G</td><td>700</td></tr>
        <tr><td>8</td><td>Service H</td><td>800</td></tr>
        <tr><td>9</td><td>Service I</td><td>900</td></tr>
        <tr><td>10</td><td>Service J</td><td>1000</td></tr>
        <tr><td>11</td><td>Service K</td><td>1100</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="gpk_hippokrat",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_gpk_hippokrat(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("SCHEMA_DRIFT" in e.code for e in result.errors)

    def test_empty_table_returns_error(self):
        html = """<html><body><table></table></body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="gpk_hippokrat",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_gpk_hippokrat(doc)
        assert len(result.candidates) == 0


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "gpk_hippokrat"
        assert len(contract["rows"]) >= 60

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["adapter"]["name"] == "gpk_hippokrat"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "gpk_hippokrat"
        assert clinic["name"] == "Гиппократ"
        assert clinic["city"] == "Костанай"

    def test_contract_rows_preserve_section(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "section" in row
            assert row["section"] is not None

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "row_id" in row
            assert "service_name_raw" in row
            assert "price" in row
            assert "currency" in row
            assert "updated_at" in row
            assert "source_url" in row
            assert "parsed_at" in row


# ─── Import payload transform tests ───

class TestImportPayloadTransform:
    def test_produces_valid_import_payload(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "gpk_hippokrat"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) >= 60

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "external_id" in service
            assert "name" in service
            assert "price" in service
            assert "currency" in service
            assert "updated_at" in service
            assert "source_url" in service
            assert "parsed_at" in service

    def test_import_payload_preserves_raw_item(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        extraction = extract_gpk_hippokrat(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "price_list.html")
        result1 = extract_gpk_hippokrat(doc)
        result2 = extract_gpk_hippokrat(doc)
        assert len(result1.candidates) == len(result2.candidates)
        for c1, c2 in zip(result1.candidates, result2.candidates):
            assert c1.service_name_raw == c2.service_name_raw
            assert c1.price == c2.price


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
