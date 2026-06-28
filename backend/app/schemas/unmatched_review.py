"""Schemas for unmatched service review API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class UnmatchedServiceListItem(BaseModel):
    """Schema for unmatched service list item."""

    id: int
    raw_name: str
    raw_category: str
    normalized_raw_name: str
    normalized_raw_category: str
    status: str
    confidence: float
    reason: str
    source_url: str | None
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    reviewed_at: datetime | None
    review_action: str | None
    suggested_normalized_service_id: int | None

    model_config = {"from_attributes": True}


class UnmatchedServiceDetail(BaseModel):
    """Schema for unmatched service detail."""

    id: int
    data_source_id: int
    import_batch_id: int | None
    service_id: int | None
    raw_source_row_id: int | None
    raw_name: str
    raw_category: str
    normalized_raw_name: str
    normalized_raw_category: str
    status: str
    confidence: float
    reason: str
    source_url: str | None
    raw_item: dict[str, Any] | None
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_action: str | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime
    suggested_normalized_service_id: int | None

    model_config = {"from_attributes": True}


class UnmatchedServiceListResponse(BaseModel):
    """Response for unmatched service list."""

    items: list[UnmatchedServiceListItem]
    total: int
    page: int
    page_size: int


class ReviewAction(BaseModel):
    """Action to review an unmatched service."""

    action: Literal[
        "approve_to_existing",
        "approve_with_new_synonym",
        "create_new_service",
        "reject",
        "needs_clarification",
        "ignore",
    ]
    target_normalized_service_id: int | None = None
    new_service_name: str | None = None
    new_category_name: str | None = None
    new_synonym: str | None = None
    reason: str | None = None
    reviewer: str = "admin"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid_actions = {
            "approve_to_existing",
            "approve_with_new_synonym",
            "create_new_service",
            "reject",
            "needs_clarification",
            "ignore",
        }
        if v not in valid_actions:
            raise ValueError(f"Invalid action: {v}")
        return v


class ReviewResult(BaseModel):
    """Result of a review action."""

    record_id: int
    action: str
    status: str
    message: str
    affected_services: int = 0


class UnmatchedServiceStats(BaseModel):
    """Statistics for unmatched services."""

    total: int
    open: int
    approved: int
    rejected: int
    needs_clarification: int
    ignored: int
