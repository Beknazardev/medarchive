"""Price history API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.price_history import (
    PriceHistoryResponse,
    PriceHistoryStats,
    PriceObservationResponse,
)
from app.services.price_history_service import PriceHistoryService


router = APIRouter(prefix="/prices", tags=["prices"])


@router.get(
    "/history",
    response_model=PriceHistoryResponse,
)
async def get_price_history(
    clinic_id: int | None = None,
    service_id: int | None = None,
    branch_id: int | None = None,
    days: int = Query(365, ge=1, le=1825),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PriceHistoryResponse:
    """Get price history with filtering and pagination."""
    service = PriceHistoryService(db)
    return service.get_history(
        clinic_id=clinic_id,
        service_id=service_id,
        branch_id=branch_id,
        days=days,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/observations",
    response_model=PriceObservationResponse,
)
async def get_price_observations(
    clinic_id: int | None = None,
    service_id: int | None = None,
    days: int = Query(365, ge=1, le=1825),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PriceObservationResponse:
    """Get price observations with filtering and pagination."""
    service = PriceHistoryService(db)
    return service.get_observations(
        clinic_id=clinic_id,
        service_id=service_id,
        days=days,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/history/stats",
    response_model=PriceHistoryStats,
)
async def get_price_history_stats(
    clinic_id: int | None = None,
    service_id: int | None = None,
    days: int = Query(365, ge=1, le=1825),
    db: Session = Depends(get_db),
) -> PriceHistoryStats:
    """Get statistics for price history."""
    service = PriceHistoryService(db)
    return service.get_stats(
        clinic_id=clinic_id,
        service_id=service_id,
        days=days,
    )
