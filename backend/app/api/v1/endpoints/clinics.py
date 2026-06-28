from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.catalog import ClinicDetailsResponse, ClinicsListResponse
from app.services.clinic_service import ClinicService


router = APIRouter()


@router.get("/clinics", response_model=ClinicsListResponse)
async def list_clinics(
    city: str | None = None,
    q: str | None = None,
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ClinicsListResponse:
    return ClinicService(db).list_clinics(
        city=city,
        q=q,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/clinics/{clinic_id}", response_model=ClinicDetailsResponse)
async def get_clinic(clinic_id: int, db: Session = Depends(get_db)) -> ClinicDetailsResponse:
    result = ClinicService(db).get_clinic(clinic_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CLINIC_NOT_FOUND",
                "message": "Clinic not found",
                "details": [],
            },
        )
    return result
