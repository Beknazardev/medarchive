"""Autocomplete API endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.autocomplete import AutocompleteResponse
from app.services.autocomplete_service import AutocompleteService


router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


@router.get(
    "",
    response_model=AutocompleteResponse,
)
async def autocomplete(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max suggestions"),
    db: Session = Depends(get_db),
) -> AutocompleteResponse:
    """Get autocomplete suggestions for service names."""
    service = AutocompleteService(db)
    return service.autocomplete(q, limit)
