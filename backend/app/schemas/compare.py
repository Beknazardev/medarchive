from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


CompareSort = Literal["price_asc", "price_desc", "updated_desc"]


class CompareParams(BaseModel):
    service_id: int | None = None
    normalized_service_id: int | None = None
    q: str | None = None
    city: str | None = None
    category: str | None = None
    sort: CompareSort = "price_asc"


class CompareQuery(BaseModel):
    service_id: int | None = None
    normalized_service_id: int | None = None
    q: str | None = None
    city: str | None = None
    category: str | None = None


class CompareStats(BaseModel):
    min_price: Decimal | None
    max_price: Decimal | None
    average_price: Decimal | None
    count: int
    currency: str | None


class CompareItem(BaseModel):
    clinic_id: int
    clinic_name: str
    branch_id: int
    city: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    service_id: int
    service_name: str
    display_service_name: str
    display_category_name: str
    price: Decimal
    currency: str
    updated_at: date
    source_url: str | None = None
    parsed_at: datetime
    freshness_state: Literal["fresh", "aging", "stale", "unknown"]
    freshness_age_days: int | None


class CompareData(BaseModel):
    query: CompareQuery
    stats: CompareStats
    items: list[CompareItem]


class ComparePricesResponse(BaseModel):
    data: CompareData
