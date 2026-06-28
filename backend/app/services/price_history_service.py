"""Price history service - provides user-visible price history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicBranch,
    ClinicServicePrice,
    DataSource,
    PriceHistory,
    PriceObservation,
    Service,
)


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


class PriceHistoryService:
    """Service for querying price history."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_history(
        self,
        *,
        clinic_id: int | None = None,
        service_id: int | None = None,
        branch_id: int | None = None,
        days: int = 365,
        page: int = 1,
        page_size: int = 20,
    ) -> PriceHistoryResponse:
        """Get price history with filtering and pagination."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = (
            select(
                PriceHistory,
                Clinic,
                ClinicBranch,
                Service,
                DataSource,
            )
            .join(Clinic, Clinic.id == PriceHistory.clinic_id)
            .join(ClinicBranch, ClinicBranch.id == PriceHistory.branch_id)
            .join(Service, Service.id == PriceHistory.service_id)
            .join(DataSource, DataSource.id == PriceHistory.data_source_id)
            .where(PriceHistory.changed_at >= cutoff_date)
        )

        if clinic_id:
            query = query.where(PriceHistory.clinic_id == clinic_id)
        if service_id:
            query = query.where(PriceHistory.service_id == service_id)
        if branch_id:
            query = query.where(PriceHistory.branch_id == branch_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        query = query.order_by(PriceHistory.changed_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size + 1)

        rows = self.db.execute(query).all()

        has_more = len(rows) > page_size
        items = [
            self._row_to_history_item(row) for row in rows[:page_size]
        ]

        return PriceHistoryResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    def get_observations(
        self,
        *,
        clinic_id: int | None = None,
        service_id: int | None = None,
        days: int = 365,
        page: int = 1,
        page_size: int = 20,
    ) -> PriceObservationResponse:
        """Get price observations with filtering and pagination."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = select(PriceObservation).where(
            PriceObservation.observed_at >= cutoff_date
        )

        if clinic_id:
            query = query.where(PriceObservation.clinic_id == clinic_id)
        if service_id:
            query = query.where(PriceObservation.service_id == service_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        query = query.order_by(PriceObservation.observed_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size + 1)

        rows = self.db.scalars(query).all()

        has_more = len(rows) > page_size
        items = [
            PriceObservationItem(
                id=row.id,
                clinic_id=row.clinic_id,
                service_id=row.service_id,
                price=row.price,
                currency=row.currency,
                is_available=row.is_available,
                source_url=row.source_url,
                parsed_at=row.parsed_at,
                observed_at=row.observed_at,
                change_detected=row.change_detected,
            )
            for row in rows[:page_size]
        ]

        return PriceObservationResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    def get_stats(
        self,
        *,
        clinic_id: int | None = None,
        service_id: int | None = None,
        days: int = 365,
    ) -> PriceHistoryStats:
        """Get statistics for price history."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        history_query = select(PriceHistory).where(
            PriceHistory.changed_at >= cutoff_date
        )
        if clinic_id:
            history_query = history_query.where(PriceHistory.clinic_id == clinic_id)
        if service_id:
            history_query = history_query.where(PriceHistory.service_id == service_id)

        total_changes = self.db.scalar(
            select(func.count()).select_from(history_query.subquery())
        ) or 0

        observation_query = select(PriceObservation).where(
            PriceObservation.observed_at >= cutoff_date
        )
        if clinic_id:
            observation_query = observation_query.where(PriceObservation.clinic_id == clinic_id)
        if service_id:
            observation_query = observation_query.where(PriceObservation.service_id == service_id)

        total_observations = self.db.scalar(
            select(func.count()).select_from(observation_query.subquery())
        ) or 0

        first_observed = self.db.scalar(
            select(func.min(PriceObservation.observed_at)).where(
                PriceObservation.observed_at >= cutoff_date
            )
        )
        last_observed = self.db.scalar(
            select(func.max(PriceObservation.observed_at)).where(
                PriceObservation.observed_at >= cutoff_date
            )
        )

        price_min = self.db.scalar(
            select(func.min(PriceObservation.price)).where(
                PriceObservation.observed_at >= cutoff_date
            )
        )
        price_max = self.db.scalar(
            select(func.max(PriceObservation.price)).where(
                PriceObservation.observed_at >= cutoff_date
            )
        )
        price_avg = self.db.scalar(
            select(func.avg(PriceObservation.price)).where(
                PriceObservation.observed_at >= cutoff_date
            )
        )

        return PriceHistoryStats(
            total_changes=total_changes,
            total_observations=total_observations,
            first_observed=first_observed,
            last_observed=last_observed,
            price_min=price_min,
            price_max=price_max,
            price_avg=price_avg,
        )

    def _row_to_history_item(self, row: Any) -> PriceHistoryItem:
        """Convert a database row to a history item."""
        history, clinic, branch, service, data_source = row

        is_historical = False
        if history.changed_at:
            changed_at = history.changed_at
            if changed_at.tzinfo is None:
                changed_at = changed_at.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - changed_at).days
            if age_days > 90:
                is_historical = True

        return PriceHistoryItem(
            id=history.id,
            clinic_id=history.clinic_id,
            clinic_name=clinic.name,
            branch_id=history.branch_id,
            branch_name=branch.name,
            branch_city=branch.city,
            service_id=history.service_id,
            service_name=service.name,
            old_price=history.old_price,
            new_price=history.new_price,
            currency=history.currency,
            change_type=history.change_type,
            source_url=history.source_url,
            parsed_at=history.parsed_at or datetime.now(UTC),
            changed_at=history.changed_at or datetime.now(UTC),
            data_source_name=data_source.name,
            is_historical=is_historical,
        )
