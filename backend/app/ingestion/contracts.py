from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


INGESTION_CONTRACT_VERSION = "medprice.ingestion.v1"
CASE1_CONTRACT_VERSION = "case1.scraped_price_list.v1"
SOURCE_ID_PATTERN = r"^[a-z0-9][a-z0-9_]{1,63}$"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SourceMode(str, Enum):
    LIVE = "live"
    SCAFFOLD = "scaffold"
    MANUAL_IMPORT_ONLY = "manual_import_only"
    PERMISSION_REQUIRED = "permission_required"
    OFFICIAL_API_REQUIRED = "official_api_required"


class ParserStage(str, Enum):
    POLICY = "policy"
    FETCH = "fetch"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    VALIDATE = "validate"
    NORMALIZE = "normalize"
    IMPORT = "import"
    STORAGE = "storage"


class PriceQualifier(str, Enum):
    EXACT = "exact"
    FROM = "from"
    RANGE = "range"
    INDICATIVE = "indicative"
    BASE_FEE_TOTAL = "base_fee_total"
    ON_REQUEST = "on_request"


class SourceFormat(str, Enum):
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    XLS = "xls"
    XLSX = "xlsx"
    JSON = "json"
    API = "api"


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    BLOCKED = "blocked"


class FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourcePolicyMetadata(FrozenContract):
    robots_url: str | None = None
    checked_at: datetime | None = None
    terms_review_status: str = Field(min_length=1, max_length=100)
    evidence_urls: tuple[str, ...] = ()
    notes: str = Field(min_length=1)

    @field_validator("robots_url")
    @classmethod
    def validate_robots_url(cls, value: str | None) -> str | None:
        return _validate_https_url(value, "robots_url") if value else None

    @field_validator("evidence_urls")
    @classmethod
    def validate_evidence_urls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_https_url(value, "evidence URL") for value in values)

    @field_validator("checked_at")
    @classmethod
    def validate_checked_at(cls, value: datetime | None) -> datetime | None:
        return _validate_aware_datetime(value, "checked_at") if value else None


class SourceConfig(FrozenContract):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=100)
    mode: SourceMode
    priority: Literal["P0", "P1", "P2", "scaffold"]
    formats: tuple[SourceFormat, ...] = Field(min_length=1)
    allowed_hosts: tuple[str, ...] = ()
    allowed_path_prefixes: tuple[str, ...] = ()
    forbidden_path_prefixes: tuple[str, ...] = ()
    start_urls: tuple[str, ...] = ()
    city_scope: tuple[str, ...] = ()
    minimum_delay_seconds: Decimal = Field(default=Decimal("10"), ge=0)
    max_concurrency: int = Field(default=1, ge=1, le=4)
    max_pages_per_run: int = Field(default=1, ge=1, le=1000)
    max_document_bytes: int = Field(default=10_000_000, ge=1, le=100_000_000)
    adapter_version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    policy: SourcePolicyMetadata
    enabled: bool = False
    adapter_module: str | None = None

    @field_validator("allowed_hosts")
    @classmethod
    def validate_allowed_hosts(cls, hosts: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for host in hosts:
            candidate = host.strip().lower().rstrip(".")
            if (
                not candidate
                or "://" in candidate
                or "/" in candidate
                or "*" in candidate
                or candidate == "localhost"
            ):
                raise ValueError("allowed_hosts must contain exact public hostnames")
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                pass
            else:
                raise ValueError("IP literals are not allowed in source configurations")
            if "." not in candidate:
                raise ValueError("allowed_hosts must contain qualified hostnames")
            normalized.append(candidate)
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_hosts must not contain duplicates")
        return tuple(normalized)

    @field_validator("allowed_path_prefixes", "forbidden_path_prefixes")
    @classmethod
    def validate_path_prefixes(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for path in paths:
            if not path.startswith("/") or "?" in path or "#" in path or "://" in path:
                raise ValueError("path prefixes must be absolute URL paths without query/fragment")
            normalized.append(path.rstrip("/") or "/")
        if len(normalized) != len(set(normalized)):
            raise ValueError("path prefixes must not contain duplicates")
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_execution_policy(self) -> SourceConfig:
        if self.mode is not SourceMode.LIVE and self.enabled:
            raise ValueError("only live sources may be enabled")
        if self.mode is SourceMode.LIVE:
            if not self.allowed_hosts or not self.allowed_path_prefixes or not self.start_urls:
                raise ValueError("live sources require explicit hosts, paths, and start URLs")
            if self.policy.checked_at is None:
                raise ValueError("live sources require a policy checked_at timestamp")
        for start_url in self.start_urls:
            parsed = urlparse(_validate_https_url(start_url, "start URL"))
            host = (parsed.hostname or "").lower()
            path = parsed.path or "/"
            if host not in self.allowed_hosts:
                raise ValueError("start URL host is not in allowed_hosts")
            if parsed.query or parsed.fragment:
                raise ValueError("start URLs must not contain query strings or fragments")
            if not _path_matches(path, self.allowed_path_prefixes):
                raise ValueError("start URL path is outside allowed_path_prefixes")
            if _path_matches(path, self.forbidden_path_prefixes):
                raise ValueError("start URL path matches forbidden_path_prefixes")
        return self


class SourceDocument(FrozenContract):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    requested_url: str
    final_url: str
    content_type: str = Field(min_length=1, max_length=255)
    status_code: int = Field(ge=100, le=599)
    headers_subset: tuple[tuple[str, str], ...] = ()
    content_bytes: bytes | None = None
    byte_size: int = Field(ge=0)
    content_sha256: str
    storage_uri: str | None = None
    captured_at: datetime
    source_document_date: date | None = None

    @field_validator("requested_url", "final_url")
    @classmethod
    def validate_document_url(cls, value: str) -> str:
        return _validate_https_url(value, "document URL")

    @field_validator("content_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if not SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("content_sha256 must contain 64 hexadecimal characters")
        return normalized

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _validate_aware_datetime(value, "captured_at")

    @field_validator("headers_subset")
    @classmethod
    def normalize_headers(
        cls,
        headers: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        normalized = tuple((name.strip().lower(), value.strip()) for name, value in headers)
        if any(not name or "\r" in value or "\n" in value for name, value in normalized):
            raise ValueError("headers_subset contains an invalid header")
        return normalized

    @model_validator(mode="after")
    def validate_content_metadata(self) -> SourceDocument:
        if self.content_bytes is None and not self.storage_uri:
            raise ValueError("content_bytes or storage_uri is required")
        if self.content_bytes is not None:
            if len(self.content_bytes) != self.byte_size:
                raise ValueError("byte_size does not match content_bytes")
            digest = hashlib.sha256(self.content_bytes).hexdigest()
            if digest != self.content_sha256:
                raise ValueError("content_sha256 does not match content_bytes")
        return self


class RawServiceCandidate(FrozenContract):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    clinic_external_id: str = Field(min_length=1, max_length=255)
    clinic_name: str = Field(min_length=1, max_length=255)
    clinic_city: str = Field(min_length=1, max_length=100)
    clinic_address: str | None = None
    clinic_phone: str | None = None
    clinic_working_hours: str | None = None
    branch_external_id: str | None = None
    branch_name: str | None = None
    branch_address: str | None = None
    service_external_id: str | None = None
    service_name_raw: str = Field(min_length=1)
    category_raw: str | None = None
    price_raw: str | None = None
    price_qualifier: PriceQualifier = PriceQualifier.EXACT
    price: Decimal | None = Field(default=None, ge=0)
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0)
    additional_fee: Decimal | None = Field(default=None, ge=0)
    total_price: Decimal | None = Field(default=None, ge=0)
    currency: Literal["KZT", "USD"] = "KZT"
    duration_minutes: int | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=0)
    duration_raw: str | None = None
    source_url: str
    parsed_at: datetime
    source_updated_at: date | None = None
    is_available: bool = True
    raw_payload: Any = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return _validate_https_url(value, "source_url", allow_fragment=True)

    @field_validator("parsed_at")
    @classmethod
    def validate_parsed_at(cls, value: datetime) -> datetime:
        return _validate_aware_datetime(value, "parsed_at")

    @field_validator("raw_payload", mode="after")
    @classmethod
    def freeze_raw_payload(cls, value: Any) -> Any:
        return _freeze_json(value)

    @model_validator(mode="after")
    def validate_price_semantics(self) -> RawServiceCandidate:
        if self.price_qualifier is PriceQualifier.EXACT and self.price is None:
            raise ValueError("exact price requires price")
        if self.price_qualifier is PriceQualifier.FROM and self.price is None and self.price_min is None:
            raise ValueError("from price requires price or price_min")
        if self.price_qualifier is PriceQualifier.RANGE:
            if self.price_min is None or self.price_max is None:
                raise ValueError("range price requires price_min and price_max")
            if self.price_max < self.price_min:
                raise ValueError("price_max must be greater than or equal to price_min")
        if self.price_qualifier is PriceQualifier.BASE_FEE_TOTAL:
            if self.base_price is None or self.total_price is None:
                raise ValueError("base_fee_total requires base_price and total_price")
            if self.total_price < self.base_price:
                raise ValueError("total_price must be greater than or equal to base_price")
        return self


class ExtractionError(FrozenContract):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    stage: ParserStage
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1)
    source_url: str | None = None
    retryable: bool = False

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        return _validate_https_url(value, "source_url", allow_fragment=True) if value else None


class ExtractionResult(FrozenContract):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    adapter_version: str
    documents: tuple[SourceDocument, ...] = ()
    candidates: tuple[RawServiceCandidate, ...] = ()
    errors: tuple[ExtractionError, ...] = ()
    schema_fingerprint: str = Field(default_factory=lambda: contract_schema_fingerprint())

    @model_validator(mode="after")
    def validate_source_links(self) -> ExtractionResult:
        linked_source_ids = {
            item.source_id for item in (*self.documents, *self.candidates, *self.errors)
        }
        if linked_source_ids.difference({self.source_id}):
            raise ValueError("all extraction items must match the result source_id")
        return self


class IngestionRunResult(FrozenContract):
    run_id: str = Field(min_length=1, max_length=255)
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    status: RunStatus
    extracted_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    errors: tuple[ExtractionError, ...] = ()
    schema_fingerprint: str = Field(default_factory=lambda: contract_schema_fingerprint())

    @model_validator(mode="after")
    def validate_counts_and_errors(self) -> IngestionRunResult:
        if self.accepted_count + self.rejected_count > self.extracted_count:
            raise ValueError("accepted_count + rejected_count cannot exceed extracted_count")
        if any(error.source_id != self.source_id for error in self.errors):
            raise ValueError("all run errors must match the run source_id")
        return self


def contract_schema_fingerprint() -> str:
    models = (
        SourceConfig,
        SourceDocument,
        RawServiceCandidate,
        ExtractionError,
        ExtractionResult,
        IngestionRunResult,
    )
    payload = json.dumps(
        {
            "contract": INGESTION_CONTRACT_VERSION,
            "case1_boundary": CASE1_CONTRACT_VERSION,
            "models": {model.__name__: model.model_json_schema() for model in models},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _validate_https_url(value: str, label: str, allow_fragment: bool = False) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must be an absolute HTTPS URL without credentials")
    if parsed.query:
        raise ValueError(f"{label} must not contain a query string")
    if parsed.fragment and not allow_fragment:
        raise ValueError(f"{label} must not contain a fragment")
    return value.strip()


def _path_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        prefix == "/" or path == prefix or path.startswith(f"{prefix}/")
        for prefix in prefixes
    )


def _validate_aware_datetime(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool, Decimal, date, datetime)):
        return value
    raise ValueError(f"raw_payload contains unsupported type: {type(value).__name__}")
