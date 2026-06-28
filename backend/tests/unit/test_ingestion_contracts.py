from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.ingestion.contracts import (
    CASE1_CONTRACT_VERSION,
    ExtractionError,
    ExtractionResult,
    IngestionRunResult,
    ParserStage,
    PriceQualifier,
    RawServiceCandidate,
    RunStatus,
    SourceConfig,
    SourceDocument,
    SourceFormat,
    SourceMode,
    SourcePolicyMetadata,
    contract_schema_fingerprint,
)


def source_config(**overrides) -> SourceConfig:
    values = {
        "source_id": "safe_source",
        "display_name": "Safe Source",
        "source_type": "laboratory",
        "mode": SourceMode.LIVE,
        "priority": "P0",
        "formats": (SourceFormat.HTML,),
        "allowed_hosts": ("prices.example.kz",),
        "allowed_path_prefixes": ("/prices",),
        "forbidden_path_prefixes": ("/prices/login", "/cabinet"),
        "start_urls": ("https://prices.example.kz/prices",),
        "city_scope": ("Астана",),
        "minimum_delay_seconds": 10,
        "max_concurrency": 1,
        "max_pages_per_run": 10,
        "max_document_bytes": 5_000_000,
        "adapter_version": "0.1.0",
        "policy": SourcePolicyMetadata(
            robots_url="https://prices.example.kz/robots.txt",
            checked_at=datetime(2026, 6, 27, tzinfo=UTC),
            terms_review_status="reviewed_public_pages_only",
            evidence_urls=("https://prices.example.kz/prices",),
            notes="Only the explicit public price path is approved.",
        ),
    }
    values.update(overrides)
    return SourceConfig.model_validate(values)


def test_source_config_is_deeply_immutable():
    config = source_config()

    with pytest.raises(ValidationError):
        config.mode = SourceMode.SCAFFOLD
    with pytest.raises(AttributeError):
        config.allowed_hosts.append("other.example.kz")
    with pytest.raises(ValidationError):
        config.policy.notes = "changed"


def test_source_config_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        source_config(mode="unreviewed")

    with pytest.raises(ValidationError):
        source_config(mode=SourceMode.SCAFFOLD, enabled=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"allowed_hosts": ("https://prices.example.kz",)},
        {"allowed_hosts": ("*.example.kz",)},
        {"allowed_hosts": ("127.0.0.1",)},
        {"start_urls": ("https://evil.example/prices",)},
        {"start_urls": ("http://prices.example.kz/prices",)},
        {"start_urls": ("https://prices.example.kz/prices/login",)},
        {"allowed_path_prefixes": ("prices",)},
        {"forbidden_path_prefixes": ("cabinet",)},
    ],
)
def test_source_config_rejects_unsafe_hosts_urls_and_paths(overrides):
    with pytest.raises(ValidationError):
        source_config(**overrides)


def test_source_document_validates_hash_size_and_is_immutable():
    body = b"<table><tr><td>1000</td></tr></table>"
    document = SourceDocument(
        source_id="safe_source",
        requested_url="https://prices.example.kz/prices",
        final_url="https://prices.example.kz/prices",
        content_type="text/html",
        status_code=200,
        headers_subset=(("content-type", "text/html"),),
        content_bytes=body,
        byte_size=len(body),
        content_sha256=sha256(body).hexdigest(),
        captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        source_document_date=date(2026, 6, 20),
    )

    assert document.content_bytes == body
    with pytest.raises(ValidationError):
        document.status_code = 500

    with pytest.raises(ValidationError):
        SourceDocument(
            source_id="safe_source",
            requested_url="https://prices.example.kz/prices",
            final_url="https://prices.example.kz/prices",
            content_type="text/html",
            status_code=200,
            content_bytes=body,
            byte_size=len(body) + 1,
            content_sha256="0" * 64,
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )


def test_raw_candidate_freezes_payload_and_validates_range_semantics():
    candidate = RawServiceCandidate(
        source_id="safe_source",
        clinic_external_id="clinic-1",
        clinic_name="Safe Clinic",
        clinic_city="Астана",
        service_external_id="service-1",
        service_name_raw="МРТ головы",
        category_raw="Диагностика",
        price_qualifier=PriceQualifier.RANGE,
        price_min=Decimal("10000"),
        price_max=Decimal("15000"),
        currency="KZT",
        duration_days=1,
        source_url="https://prices.example.kz/prices#mri",
        parsed_at=datetime(2026, 6, 27, tzinfo=UTC),
        raw_payload={"cells": ["МРТ головы", "10 000–15 000"]},
    )

    assert candidate.raw_payload["cells"] == ("МРТ головы", "10 000–15 000")
    with pytest.raises(TypeError):
        candidate.raw_payload["new"] = "value"

    with pytest.raises(ValidationError):
        RawServiceCandidate(
            source_id="safe_source",
            clinic_external_id="clinic-1",
            clinic_name="Safe Clinic",
            clinic_city="Астана",
            service_name_raw="Broken range",
            price_qualifier=PriceQualifier.RANGE,
            price_min=Decimal("15000"),
            price_max=Decimal("10000"),
            currency="KZT",
            source_url="https://prices.example.kz/prices",
            parsed_at=datetime(2026, 6, 27, tzinfo=UTC),
        )


def test_contract_schema_fingerprint_is_stable_sha256():
    fingerprint = contract_schema_fingerprint()

    assert fingerprint.startswith("sha256:")
    assert len(fingerprint.removeprefix("sha256:")) == 64
    assert CASE1_CONTRACT_VERSION == "case1.scraped_price_list.v1"


def test_extraction_and_run_results_are_immutable_and_share_fingerprint():
    error = ExtractionError(
        source_id="safe_source",
        stage=ParserStage.VALIDATE,
        code="INVALID_ROW",
        message="A row could not be validated",
        source_url="https://prices.example.kz/prices",
        retryable=False,
    )
    extraction = ExtractionResult(
        source_id="safe_source",
        adapter_version="0.1.0",
        errors=(error,),
    )
    run = IngestionRunResult(
        run_id="run-1",
        source_id="safe_source",
        status=RunStatus.PARTIAL_SUCCESS,
        extracted_count=2,
        accepted_count=1,
        rejected_count=1,
        errors=(error,),
    )

    assert extraction.schema_fingerprint == run.schema_fingerprint
    assert extraction.schema_fingerprint == contract_schema_fingerprint()
    with pytest.raises(ValidationError):
        run.accepted_count = 2

    with pytest.raises(ValidationError):
        IngestionRunResult(
            run_id="run-invalid-counts",
            source_id="safe_source",
            status=RunStatus.FAILED,
            extracted_count=1,
            accepted_count=1,
            rejected_count=1,
        )
