from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.search import PaginationMeta


class ClinicListItem(BaseModel):
    id: int
    name: str
    city: str
    phone: str | None
    website: str | None
    branches_count: int
    services_count: int
    last_updated_at: date | None


class ClinicsListResponse(BaseModel):
    data: list[ClinicListItem]
    meta: PaginationMeta


class ClinicBranchDetails(BaseModel):
    id: int
    name: str | None
    city: str
    address: str
    phone: str | None
    latitude: float | None = None
    longitude: float | None = None


class ClinicServicePriceDetails(BaseModel):
    service_id: int
    name: str
    category: str
    price: Decimal
    currency: str
    updated_at: date
    source_url: str | None = None
    parsed_at: datetime
    freshness_state: Literal["fresh", "aging", "stale", "unknown"]
    freshness_age_days: int | None


class ClinicDetails(BaseModel):
    id: int
    name: str
    city: str
    phone: str | None
    website: str | None
    branches: list[ClinicBranchDetails]
    services: list[ClinicServicePriceDetails]


class ClinicDetailsResponse(BaseModel):
    data: ClinicDetails


class ServiceNormalizedDetails(BaseModel):
    id: int
    name: str


class ServiceCategoryDetails(BaseModel):
    id: int
    name: str


class ServicePriceDetails(BaseModel):
    clinic_id: int
    clinic_name: str
    branch_id: int
    city: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    amount: Decimal
    currency: str
    updated_at: date
    source_url: str | None = None
    parsed_at: datetime
    freshness_state: Literal["fresh", "aging", "stale", "unknown"]
    freshness_age_days: int | None


class ServiceStats(BaseModel):
    min_price: Decimal | None
    max_price: Decimal | None
    average_price: Decimal | None
    count: int


class ServiceDetails(BaseModel):
    id: int
    name: str
    normalized_service: ServiceNormalizedDetails
    category: ServiceCategoryDetails
    prices: list[ServicePriceDetails]
    stats: ServiceStats


class ServiceDetailsResponse(BaseModel):
    data: ServiceDetails


class CategoryListItem(BaseModel):
    id: int
    name: str
    slug: str
    services_count: int


class CategoriesResponse(BaseModel):
    data: list[CategoryListItem]


class CityListItem(BaseModel):
    name: str
    clinics_count: int
    services_count: int


class CitiesResponse(BaseModel):
    data: list[CityListItem]
