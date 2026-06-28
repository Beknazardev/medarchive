from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_import_api_key
from app.schemas.import_prices import ImportPricesRequest, ImportPricesResponse
from app.services.import_service import ImportService


router = APIRouter()


@router.post(
    "/import/prices",
    response_model=ImportPricesResponse,
    dependencies=[Depends(require_import_api_key)],
)
async def import_prices(payload: ImportPricesRequest, db: Session = Depends(get_db)) -> dict:
    result = ImportService(db).import_prices(payload)
    return {"data": result}
