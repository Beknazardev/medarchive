from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ClinicBranch
from app.schemas.search import SearchParams, SearchServicesResponse, SearchSort
from app.services.normalization_service import CITY_ALIASES
from app.services.search_service import SearchService


router = APIRouter()


class CityItem(BaseModel):
    name: str
    aliases: list[str]


class CitiesResponse(BaseModel):
    data: list[CityItem]


@router.get("/services/search", response_model=SearchServicesResponse)
async def search_services(
    q: Annotated[str | None, Query()] = None,
    city: str | None = None,
    category: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    sort: SearchSort = "relevance",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SearchServicesResponse:
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_QUERY",
                "message": "Search query is required",
                "details": [],
            },
        )

    params = SearchParams(
        q=q.strip(),
        city=city,
        category=category,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return SearchService(db).search(params)


@router.get("/cities", response_model=CitiesResponse)
async def list_cities(db: Session = Depends(get_db)) -> CitiesResponse:
    """List available cities from the database with their aliases."""
    rows = db.execute(
        select(ClinicBranch.city, func.count(ClinicBranch.id))
        .where(ClinicBranch.is_active.is_(True))
        .group_by(ClinicBranch.city)
        .order_by(func.count(ClinicBranch.id).desc())
    ).all()

    # Build reverse alias map: canonical → list of aliases
    alias_map: dict[str, list[str]] = {}
    for alias, canonical in CITY_ALIASES.items():
        if canonical not in alias_map:
            alias_map[canonical] = []
        if alias != canonical:
            alias_map[canonical].append(alias)

    cities = []
    for city_name, _count in rows:
        if not city_name:
            continue
        normalized = city_name.lower().strip()
        aliases = alias_map.get(normalized, [])
        cities.append(CityItem(name=city_name, aliases=aliases))

    return CitiesResponse(data=cities)
