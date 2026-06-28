from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.catalog import (
    CategoriesResponse,
    CitiesResponse,
    ServiceDetailsResponse,
)
from app.services.service_catalog_service import ServiceCatalogService


router = APIRouter()


@router.get("/services/{service_id}", response_model=ServiceDetailsResponse)
async def get_service(service_id: int, db: Session = Depends(get_db)) -> ServiceDetailsResponse:
    result = ServiceCatalogService(db).get_service(service_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SERVICE_NOT_FOUND",
                "message": "Service not found",
                "details": [],
            },
        )
    return result


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories(db: Session = Depends(get_db)) -> CategoriesResponse:
    return ServiceCatalogService(db).list_categories()


@router.get("/cities", response_model=CitiesResponse)
async def list_cities(db: Session = Depends(get_db)) -> CitiesResponse:
    return ServiceCatalogService(db).list_cities()
