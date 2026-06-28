from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClinicImportPayload(BaseModel):
    external_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    legal_name: str | None = None
    city: str = Field(min_length=1)
    address: str | None = None
    phone: str | None = None
    website: str | None = None

    @field_validator("external_id", "name", "city", mode="before")
    @classmethod
    def required_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Field is required")
        return value

    @field_validator("website")
    @classmethod
    def valid_website(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Website must be a valid URL")
        return value


class BranchImportPayload(BaseModel):
    external_id: str | None = None
    name: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class ServiceImportPayload(BaseModel):
    external_id: str | None = None
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str | None = None
    price: Decimal = Field(ge=0)
    currency: str = Field(min_length=1)
    updated_at: date
    source_url: str | None = None
    parsed_at: datetime | None = None
    raw_source_row_id: int | None = Field(default=None, ge=1)
    raw_item: dict[str, Any] | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    is_available: bool = True

    @field_validator("name", "category", "currency", mode="before")
    @classmethod
    def required_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Field is required")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str | None) -> str | None:
        return validate_optional_url(value, "Source URL")


class RawSnapshotImportPayload(BaseModel):
    source_url: str | None = None
    requested_url: str | None = None
    final_url: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] | None = None
    content_type: str | None = None
    checksum: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    byte_size: int | None = Field(default=None, ge=0)
    storage_uri: str | None = None
    source_document_date: date | None = None
    raw_payload: dict[str, Any] | list[Any] | str | None = None
    captured_at: datetime | None = None

    @field_validator("content_type", "checksum", "content_sha256", "storage_uri", mode="before")
    @classmethod
    def optional_trimmed_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        return value or None

    @field_validator("source_url", "requested_url", "final_url")
    @classmethod
    def valid_source_url(cls, value: str | None) -> str | None:
        return validate_optional_url(value, "Snapshot source URL")

    @field_validator("content_sha256")
    @classmethod
    def normalize_content_sha256(cls, value: str | None) -> str | None:
        return value.lower() if value else None


class ImportPricesRequest(BaseModel):
    source: str = Field(min_length=1)
    source_type: str | None = None
    source_url: str | None = None
    robots_policy_notes: str | None = None
    crawl_delay_seconds: int | None = Field(default=None, ge=0)
    source_batch_id: str | None = None
    parser_run_id: int | None = Field(default=None, ge=1)
    raw_snapshot: RawSnapshotImportPayload | None = None
    clinic: ClinicImportPayload
    branch: BranchImportPayload | None = None
    services: list[dict[str, Any]] = Field(min_length=1, max_length=1000)

    @field_validator("source", mode="before")
    @classmethod
    def required_source(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Source is required")
        return value

    @field_validator("source_type", "robots_policy_notes", mode="before")
    @classmethod
    def optional_trimmed_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        return value or None

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str | None) -> str | None:
        return validate_optional_url(value, "Source URL")


def validate_optional_url(value: str | None, label: str) -> str | None:
    if value is None or value == "":
        return None
    value = value.strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} must be a valid URL")
    return value


class ImportErrorItem(BaseModel):
    index: int
    external_id: str | None = None
    code: str
    message: str
    field: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ImportPricesResult(BaseModel):
    batch_id: int
    status: str
    source: str
    clinic_id: int
    branch_id: int
    received_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    error_count: int
    errors: list[ImportErrorItem]


class ImportPricesResponse(BaseModel):
    data: ImportPricesResult
