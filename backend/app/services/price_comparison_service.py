from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicBranch,
    ClinicServicePrice,
    NormalizedService,
    Service,
    ServiceCategory,
)
from app.schemas.compare import (
    CompareData,
    CompareItem,
    CompareParams,
    ComparePricesResponse,
    CompareQuery,
    CompareStats,
)
from app.services.normalization_service import NormalizationService
from app.services.freshness_service import price_freshness
from app.services.query_expansion import expand_service_query


class PriceComparisonService:
    def __init__(self, db: Session, normalizer: NormalizationService | None = None) -> None:
        self.db = db
        self.normalizer = normalizer or NormalizationService()

    def compare(self, params: CompareParams) -> ComparePricesResponse:
        query = self._base_query(params)
        rows = self.db.execute(self._apply_sort(query, params)).all()
        items = [self._row_to_item(row) for row in rows]

        return ComparePricesResponse(
            data=CompareData(
                query=CompareQuery(
                    service_id=params.service_id,
                    normalized_service_id=params.normalized_service_id,
                    q=params.q,
                    city=params.city,
                    category=params.category,
                ),
                stats=self._stats(items),
                items=items,
            )
        )

    def _base_query(self, params: CompareParams):
        query = (
            select(Service, ServiceCategory, Clinic, ClinicBranch, ClinicServicePrice)
            .join(ClinicServicePrice, ClinicServicePrice.service_id == Service.id)
            .join(ServiceCategory, ServiceCategory.id == Service.category_id)
            .join(NormalizedService, NormalizedService.id == Service.normalized_service_id)
            .join(Clinic, Clinic.id == ClinicServicePrice.clinic_id)
            .join(ClinicBranch, ClinicBranch.id == ClinicServicePrice.branch_id)
            .where(
                Service.is_active.is_(True),
                Clinic.is_active.is_(True),
                ClinicBranch.is_active.is_(True),
                ClinicServicePrice.is_available.is_(True),
            )
        )

        if params.service_id is not None:
            query = query.where(Service.id == params.service_id)
        elif params.normalized_service_id is not None:
            query = query.where(Service.normalized_service_id == params.normalized_service_id)
        elif params.q:
            patterns = [
                f"%{term}%"
                for term in expand_service_query(params.q, self.normalizer)
            ]
            raw_pattern = f"%{params.q.strip().lower()}%"
            service_matches = []
            for pattern in patterns:
                service_matches.extend(
                    (
                        func.lower(Service.name).like(pattern),
                        Service.normalized_name.like(pattern),
                        func.lower(NormalizedService.name).like(pattern),
                        func.lower(ServiceCategory.name).like(pattern),
                    )
                )
            query = query.where(
                or_(
                    *service_matches,
                    func.lower(Clinic.name).like(raw_pattern),
                )
            )

        if params.city:
            resolved_city = self.normalizer.resolve_city(params.city)
            if resolved_city:
                query = query.where(func.lower(ClinicBranch.city) == resolved_city)
            else:
                query = query.where(func.lower(ClinicBranch.city).like(f"%{params.city.lower()}%"))
        if params.category:
            query = query.where(ServiceCategory.normalized_name == self.normalizer.normalize_text(params.category))

        return query

    def _apply_sort(self, query, params: CompareParams):
        if params.sort == "price_desc":
            return query.order_by(ClinicServicePrice.price.desc(), Clinic.name.asc())
        if params.sort == "updated_desc":
            return query.order_by(ClinicServicePrice.updated_at.desc(), Clinic.name.asc())
        return query.order_by(ClinicServicePrice.price.asc(), Clinic.name.asc())

    def _row_to_item(self, row) -> CompareItem:
        service, category, clinic, branch, price = row
        freshness = price_freshness(price.parsed_at, price.updated_at)
        display_service_name = self._get_localized_name(
            service.name_ru if hasattr(service, 'name_ru') else None,
            service.name_kk if hasattr(service, 'name_kk') else None,
            service.name_en if hasattr(service, 'name_en') else None,
            service.name,
        )
        display_category_name = self._get_localized_name(
            category.name_ru,
            category.name_kk,
            category.name_en,
            category.name,
        )
        return CompareItem(
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            branch_id=branch.id,
            city=branch.city,
            address=branch.address,
            latitude=float(branch.latitude) if branch.latitude else None,
            longitude=float(branch.longitude) if branch.longitude else None,
            service_id=service.id,
            service_name=service.name,
            display_service_name=display_service_name,
            display_category_name=display_category_name,
            price=price.price,
            currency=price.currency,
            updated_at=price.updated_at,
            source_url=price.source_url,
            parsed_at=price.parsed_at,
            freshness_state=freshness.state,
            freshness_age_days=freshness.age_days,
        )

    def _stats(self, items: list[CompareItem]) -> CompareStats:
        if not items:
            return CompareStats(
                min_price=None,
                max_price=None,
                average_price=None,
                count=0,
                currency=None,
            )

        prices = [Decimal(item.price) for item in items]
        currency = items[0].currency
        average = (sum(prices) / Decimal(len(prices))).quantize(Decimal("0.01"))
        return CompareStats(
            min_price=min(prices),
            max_price=max(prices),
            average_price=average,
            count=len(prices),
            currency=currency,
        )

    def _get_localized_name(
        self,
        name_ru: str | None,
        name_kk: str | None,
        name_en: str | None,
        fallback: str,
    ) -> str:
        """Return localized name with fallback chain."""
        if name_ru:
            return name_ru
        if name_en:
            return name_en
        if name_kk:
            return name_kk
        return fallback
