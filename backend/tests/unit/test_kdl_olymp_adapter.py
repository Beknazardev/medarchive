"""Tests for KDL Olymp adapter - Phase F1 TDD."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.kdl_olymp import (
    ADAPTER_VERSION,
    extract_kdl_olymp,
    transform_to_scraped_contract,
    transform_to_import_payload,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "kdl_olymp"
SOURCE_URL = "https://www.kdlolymp.kz/pricelist/almaty"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="kdl_olymp",
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

class TestKdlOlympExtraction:
    def test_extracts_all_rows_from_valid_fixture(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "kdl_olymp"
        assert len(result.candidates) == 15

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert "Общий анализ крови (ОАК) с лейкоцитарной формулой" in names
        assert "Витамин D (25-OH)" in names

    def test_extracts_exact_prices(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        assert prices["Общий анализ крови (ОАК) с лейкоцитарной формулой"] == Decimal("1450")
        assert prices["Витамин D (25-OH)"] == Decimal("4500")
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_duration(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        oak = next(c for c in result.candidates if "ОАК" in c.service_name_raw)
        assert oak.duration_days == 1
        assert oak.duration_raw == "1"

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None
            assert "₸" in candidate.price_raw or "тенге" in candidate.price_raw.lower() or candidate.price_raw

    def test_sets_source_url_and_parsed_at(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        for candidate in result.candidates:
            assert candidate.source_url == SOURCE_URL
            assert candidate.parsed_at is not None
            assert candidate.parsed_at.tzinfo is not None

    def test_sets_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        for candidate in result.candidates:
            assert candidate.source_id == "kdl_olymp"
            assert candidate.clinic_name == "КДЛ ОЛИМП"
            assert candidate.clinic_city == "Алматы"

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result = extract_kdl_olymp(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "row_number" in candidate.raw_payload
            assert "cells" in candidate.raw_payload

    def test_detects_schema_drift_on_missing_headings(self):
        html = b"""<html><body>
        <table>
        <thead><tr><th>Wrong</th><th>Headers</th><th>More</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Service A</td><td>100</td></tr>
        <tr><td>2</td><td>Service B</td><td>200</td></tr>
        <tr><td>3</td><td>Service C</td><td>300</td></tr>
        </tbody>
        </table>
        </body></html>"""
        doc = SourceDocument(
            source_id="kdl_olymp",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_kdl_olymp(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("SCHEMA_DRIFT" in e.code for e in result.errors)

    def test_empty_table_returns_error(self):
        html = b"""<html><body><table></table></body></html>"""
        doc = SourceDocument(
            source_id="kdl_olymp",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_kdl_olymp(doc)
        assert len(result.candidates) == 0


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "kdl_olymp"
        assert len(contract["rows"]) == 15

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["source_url"] == SOURCE_URL
        assert "robots" in source
        assert "adapter" in source
        assert source["adapter"]["name"] == "kdl_olymp"
        assert source["adapter"]["version"] == ADAPTER_VERSION

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "kdl_olymp"
        assert clinic["name"] == "КДЛ ОЛИМП"
        assert clinic["city"] == "Алматы"

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
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
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "kdl_olymp"
        assert payload.source_type == "public_price_list"
        assert payload.source_url == SOURCE_URL
        assert len(payload.services) == 15

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
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
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        extraction = extract_kdl_olymp(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "price_list_almaty.html")
        result1 = extract_kdl_olymp(doc)
        result2 = extract_kdl_olymp(doc)
        assert len(result1.candidates) == len(result2.candidates)
        for c1, c2 in zip(result1.candidates, result2.candidates):
            assert c1.service_name_raw == c2.service_name_raw
            assert c1.price == c2.price
            assert c1.duration_days == c2.duration_days


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
