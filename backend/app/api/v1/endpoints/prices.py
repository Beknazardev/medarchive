from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.compare import CompareParams, ComparePricesResponse, CompareSort
from app.services.price_comparison_service import PriceComparisonService


router = APIRouter()


@router.get("/prices/compare", response_model=ComparePricesResponse)
async def compare_prices(
    service_id: int | None = Query(default=None, ge=1),
    normalized_service_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    sort: CompareSort = "price_asc",
    db: Session = Depends(get_db),
) -> ComparePricesResponse:
    if service_id is None and normalized_service_id is None and (not q or not q.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_COMPARE_TARGET",
                "message": "service_id, normalized_service_id or q is required",
                "details": [],
            },
        )

    params = CompareParams(
        service_id=service_id,
        normalized_service_id=normalized_service_id,
        q=q.strip() if q else None,
        city=city,
        category=category,
        sort=sort,
    )
    return PriceComparisonService(db).compare(params)
