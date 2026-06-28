from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


SearchSort = Literal["relevance", "price_asc", "price_desc", "updated_desc"]


class SearchParams(BaseModel):
    q: str = Field(min_length=1)
    city: str | None = None
    category: str | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    sort: SearchSort = "relevance"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchClinic(BaseModel):
    id: int
    name: str


class SearchBranch(BaseModel):
    id: int
    address: str
    city: str
    latitude: float | None = None
    longitude: float | None = None


class SearchPrice(BaseModel):
    amount: Decimal
    currency: str
    updated_at: date
    source_url: str | None = None
    parsed_at: datetime
    freshness_state: Literal["fresh", "stale", "expired", "unknown"]
    freshness_age_days: int | None
    freshness_warning: str | None = None


class SearchServiceItem(BaseModel):
    service_id: int
    service_name: str
    display_service_name: str
    normalized_service_id: int
    normalized_service_name: str
    display_category_name: str
    category: str
    clinic: SearchClinic
    branch: SearchBranch
    price: SearchPrice
    source_language: str | None = None
    locale_used: str | None = None


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    total: int


class SearchServicesResponse(BaseModel):
    data: list[SearchServiceItem]
    meta: PaginationMeta
