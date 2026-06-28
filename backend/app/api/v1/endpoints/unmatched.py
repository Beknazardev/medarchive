"""Unmatched service review API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_import_api_key
from app.schemas.unmatched_review import (
    ReviewAction,
    ReviewResult,
    UnmatchedServiceDetail,
    UnmatchedServiceListResponse,
    UnmatchedServiceStats,
)
from app.services.unmatched_review_service import UnmatchedServiceReviewService


router = APIRouter(prefix="/unmatched", tags=["unmatched"])


@router.get(
    "",
    response_model=UnmatchedServiceListResponse,
    dependencies=[Depends(require_import_api_key)],
)
async def list_unmatched_services(
    status_filter: str | None = Query(None, alias="status"),
    source_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> UnmatchedServiceListResponse:
    """List unmatched services with filtering and pagination."""
    service = UnmatchedServiceReviewService(db)
    return service.list_unmatched(
        status=status_filter,
        source_id=source_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{record_id}",
    response_model=UnmatchedServiceDetail,
    dependencies=[Depends(require_import_api_key)],
)
async def get_unmatched_service(
    record_id: int,
    db: Session = Depends(get_db),
) -> UnmatchedServiceDetail:
    """Get detailed information about an unmatched service."""
    service = UnmatchedServiceReviewService(db)
    result = service.get_detail(record_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Unmatched service {record_id} not found",
            },
        )
    return result


@router.post(
    "/{record_id}/review",
    response_model=ReviewResult,
    dependencies=[Depends(require_import_api_key)],
)
async def review_unmatched_service(
    record_id: int,
    action: ReviewAction,
    db: Session = Depends(get_db),
) -> ReviewResult:
    """Review an unmatched service with the specified action."""
    service = UnmatchedServiceReviewService(db)
    result = service.review(record_id, action)
    if result.status == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REVIEW_ERROR",
                "message": result.message,
            },
        )
    return result


@router.get(
    "/stats/overview",
    response_model=UnmatchedServiceStats,
    dependencies=[Depends(require_import_api_key)],
)
async def get_unmatched_stats(
    db: Session = Depends(get_db),
) -> UnmatchedServiceStats:
    """Get statistics for unmatched services."""
    service = UnmatchedServiceReviewService(db)
    return service.get_stats()
