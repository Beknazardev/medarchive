"""Schemas for price history API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PriceHistoryItem(BaseModel):
    """Single price history item."""

    id: int
    clinic_id: int
    clinic_name: str
    branch_id: int
    branch_name: str | None
    branch_city: str
    service_id: int
    service_name: str
    old_price: Decimal | None
    new_price: Decimal
    currency: str
    change_type: str
    source_url: str | None
    parsed_at: datetime
    changed_at: datetime
    data_source_name: str
    is_historical: bool


class PriceObservationItem(BaseModel):
    """Single price observation item."""

    id: int
    clinic_id: int
    service_id: int
    price: Decimal
    currency: str
    is_available: bool
    source_url: str | None
    parsed_at: datetime
    observed_at: datetime
    change_detected: bool


class PriceHistoryResponse(BaseModel):
    """Response for price history query."""

    items: list[PriceHistoryItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class PriceObservationResponse(BaseModel):
    """Response for price observation query."""

    items: list[PriceObservationItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class PriceHistoryStats(BaseModel):
    """Statistics for price history."""

    total_changes: int
    total_observations: int
    first_observed: datetime | None
    last_observed: datetime | None
    price_min: Decimal | None
    price_max: Decimal | None
    price_avg: Decimal | None
