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
from app.schemas.search import (
    PaginationMeta,
    SearchBranch,
    SearchClinic,
    SearchParams,
    SearchPrice,
    SearchServiceItem,
    SearchServicesResponse,
)
from app.services.normalization_service import NormalizationService
from app.services.freshness_service import price_freshness
from app.services.query_expansion import expand_service_query


class SearchService:
    def __init__(self, db: Session, normalizer: NormalizationService | None = None) -> None:
        self.db = db
        self.normalizer = normalizer or NormalizationService()

    def search(self, params: SearchParams) -> SearchServicesResponse:
        query = self._base_query(params)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0

        ordered = self._apply_sort(query, params)
        rows = self.db.execute(ordered.limit(params.limit).offset(params.offset)).all()

        return SearchServicesResponse(
            data=[self._row_to_item(row) for row in rows],
            meta=PaginationMeta(limit=params.limit, offset=params.offset, total=total),
        )

    def _base_query(self, params: SearchParams):
        search_patterns = [
            f"%{term}%"
            for term in expand_service_query(params.q, self.normalizer)
        ]
        raw_pattern = f"%{params.q.strip()}%"
        service_matches = []
        for search_pattern in search_patterns:
            service_matches.extend(
                (
                    func.lower(Service.name).like(search_pattern),
                    Service.normalized_name.like(search_pattern),
                    func.lower(NormalizedService.name).like(search_pattern),
                    func.lower(ServiceCategory.name).like(search_pattern),
                )
            )

        query = (
            select(
                Service,
                NormalizedService,
                ServiceCategory,
                Clinic,
                ClinicBranch,
                ClinicServicePrice,
            )
            .join(
                ClinicServicePrice,
                ClinicServicePrice.service_id == Service.id,
            )
            .join(
                NormalizedService,
                NormalizedService.id == Service.normalized_service_id,
            )
            .join(ServiceCategory, ServiceCategory.id == Service.category_id)
            .join(Clinic, Clinic.id == ClinicServicePrice.clinic_id)
            .join(ClinicBranch, ClinicBranch.id == ClinicServicePrice.branch_id)
            .where(
                Service.is_active.is_(True),
                Clinic.is_active.is_(True),
                ClinicBranch.is_active.is_(True),
                ClinicServicePrice.is_available.is_(True),
                or_(
                    *service_matches,
                    func.lower(Clinic.name).like(raw_pattern),
                ),
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
        if params.min_price is not None:
            query = query.where(ClinicServicePrice.price >= params.min_price)
        if params.max_price is not None:
            query = query.where(ClinicServicePrice.price <= params.max_price)

        return query

    def _apply_sort(self, query, params: SearchParams):
        if params.sort == "price_asc":
            return query.order_by(ClinicServicePrice.price.asc(), Service.name.asc())
        if params.sort == "price_desc":
            return query.order_by(ClinicServicePrice.price.desc(), Service.name.asc())
        if params.sort == "updated_desc":
            return query.order_by(ClinicServicePrice.updated_at.desc(), Service.name.asc())
        return query.order_by(Service.name.asc(), ClinicServicePrice.price.asc())

    def _row_to_item(self, row) -> SearchServiceItem:
        service, normalized_service, category, clinic, branch, price = row
        freshness = price_freshness(price.parsed_at, price.updated_at)

        if normalized_service.canonical_key and normalized_service.name_ru:
            display_service_name = self._get_localized_name(
                normalized_service.name_ru,
                normalized_service.name_kk,
                normalized_service.name_en,
                service.name,
            )
            display_category_name = self._get_localized_name(
                category.name_ru,
                category.name_kk,
                category.name_en,
                category.name,
            )
        else:
            display_service_name = service.name
            display_category_name = category.name

        return SearchServiceItem(
            service_id=service.id,
            service_name=service.name,
            display_service_name=display_service_name,
            normalized_service_id=normalized_service.id,
            normalized_service_name=self._normalized_service_display_name(service, normalized_service),
            display_category_name=display_category_name,
            category=category.name,
            clinic=SearchClinic(id=clinic.id, name=clinic.name),
            branch=SearchBranch(
                id=branch.id,
                address=branch.address,
                city=branch.city,
                latitude=float(branch.latitude) if branch.latitude else None,
                longitude=float(branch.longitude) if branch.longitude else None,
            ),
            price=SearchPrice(
                amount=price.price,
                currency=price.currency,
                updated_at=price.updated_at,
                source_url=price.source_url,
                parsed_at=price.parsed_at,
                freshness_state=freshness.state,
                freshness_age_days=freshness.age_days,
                freshness_warning=freshness.warning,
            ),
        )

    def _normalized_service_display_name(
        self,
        service: Service,
        normalized_service: NormalizedService,
    ) -> str:
        if service.normalization_status == "unmatched":
            return service.normalized_name
        return normalized_service.name

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
