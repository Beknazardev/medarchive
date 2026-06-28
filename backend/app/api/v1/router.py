from fastapi import APIRouter

from app.api.v1.endpoints.autocomplete import router as autocomplete_router
from app.api.v1.endpoints.catalog import router as catalog_router
from app.api.v1.endpoints.clinics import router as clinics_router
from app.api.v1.endpoints.import_prices import router as import_prices_router
from app.api.v1.endpoints.price_history import router as price_history_router
from app.api.v1.endpoints.prices import router as prices_router
from app.api.v1.endpoints.services import router as services_router
from app.api.v1.endpoints.unmatched import router as unmatched_router


api_router = APIRouter()
api_router.include_router(import_prices_router)
api_router.include_router(prices_router)
api_router.include_router(services_router)
api_router.include_router(clinics_router)
api_router.include_router(catalog_router)
api_router.include_router(unmatched_router)
api_router.include_router(autocomplete_router)
api_router.include_router(price_history_router)


@api_router.get("/")
async def api_root() -> dict:
    return {
        "data": {
            "message": "API v1 is ready",
        },
        "meta": {},
    }
