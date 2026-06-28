from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from app.models import Clinic, ClinicBranch, ClinicServicePrice, Service, ServiceCategory
from app.schemas.catalog import (
    ClinicBranchDetails,
    ClinicDetails,
    ClinicDetailsResponse,
    ClinicListItem,
    ClinicServicePriceDetails,
    ClinicsListResponse,
)
from app.schemas.search import PaginationMeta
from app.services.freshness_service import price_freshness
from app.services.normalization_service import NormalizationService


class ClinicService:
    def __init__(self, db: Session, normalizer: NormalizationService | None = None) -> None:
        self.db = db
        self.normalizer = normalizer or NormalizationService()

    def list_clinics(
        self,
        city: str | None = None,
        q: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ClinicsListResponse:
        filtered_ids = self._filtered_clinic_ids(city=city, q=q, category=category).subquery()
        total = self.db.scalar(select(func.count()).select_from(filtered_ids)) or 0

        summary = (
            select(
                Clinic.id,
                Clinic.name,
                Clinic.city,
                Clinic.phone,
                Clinic.website,
                func.count(distinct(ClinicBranch.id)).label("branches_count"),
                func.count(distinct(ClinicServicePrice.service_id)).label("services_count"),
                func.max(ClinicServicePrice.updated_at).label("last_updated_at"),
            )
            .join(ClinicBranch, ClinicBranch.clinic_id == Clinic.id, isouter=True)
            .join(ClinicServicePrice, ClinicServicePrice.clinic_id == Clinic.id, isouter=True)
            .where(Clinic.id.in_(select(filtered_ids.c.id)))
            .group_by(Clinic.id)
            .order_by(Clinic.name.asc())
            .limit(limit)
            .offset(offset)
        )

        rows = self.db.execute(summary).all()
        return ClinicsListResponse(
            data=[
                ClinicListItem(
                    id=row.id,
                    name=row.name,
                    city=row.city,
                    phone=row.phone,
                    website=row.website,
                    branches_count=row.branches_count,
                    services_count=row.services_count,
                    last_updated_at=row.last_updated_at,
                )
                for row in rows
            ],
            meta=PaginationMeta(limit=limit, offset=offset, total=total),
        )

    def get_clinic(self, clinic_id: int) -> ClinicDetailsResponse | None:
        clinic = self.db.get(Clinic, clinic_id)
        if not clinic:
            return None

        branches = self.db.scalars(
            select(ClinicBranch)
            .where(ClinicBranch.clinic_id == clinic.id)
            .order_by(ClinicBranch.is_default.desc(), ClinicBranch.id.asc())
        ).all()

        price_rows = self.db.execute(
            select(Service, ServiceCategory, ClinicServicePrice)
            .join(ClinicServicePrice, ClinicServicePrice.service_id == Service.id)
            .join(ServiceCategory, ServiceCategory.id == Service.category_id)
            .where(ClinicServicePrice.clinic_id == clinic.id)
            .order_by(Service.name.asc())
        ).all()

        return ClinicDetailsResponse(
            data=ClinicDetails(
                id=clinic.id,
                name=clinic.name,
                city=clinic.city,
                phone=clinic.phone,
                website=clinic.website,
                branches=[
                    ClinicBranchDetails(
                        id=branch.id,
                        name=branch.name,
                        city=branch.city,
                        address=branch.address,
                        phone=branch.phone,
                        latitude=float(branch.latitude) if branch.latitude else None,
                        longitude=float(branch.longitude) if branch.longitude else None,
                    )
                    for branch in branches
                ],
                services=[
                    self._price_details(service, category, price)
                    for service, category, price in price_rows
                ],
            )
        )

    def _price_details(
        self,
        service: Service,
        category: ServiceCategory,
        price: ClinicServicePrice,
    ) -> ClinicServicePriceDetails:
        freshness = price_freshness(price.parsed_at, price.updated_at)
        return ClinicServicePriceDetails(
            service_id=service.id,
            name=service.name,
            category=category.name,
            price=price.price,
            currency=price.currency,
            updated_at=price.updated_at,
            source_url=price.source_url,
            parsed_at=price.parsed_at,
            freshness_state=freshness.state,
            freshness_age_days=freshness.age_days,
        )

    def _filtered_clinic_ids(self, city: str | None, q: str | None, category: str | None):
        query = select(distinct(Clinic.id).label("id")).select_from(Clinic)

        if city or category:
            query = query.join(ClinicBranch, ClinicBranch.clinic_id == Clinic.id)
        if category:
            query = (
                query.join(ClinicServicePrice, ClinicServicePrice.clinic_id == Clinic.id)
                .join(Service, Service.id == ClinicServicePrice.service_id)
                .join(ServiceCategory, ServiceCategory.id == Service.category_id)
            )

        query = query.where(Clinic.is_active.is_(True))

        if city:
            query = query.where(func.lower(ClinicBranch.city) == city.lower())
        if q:
            normalized_q = self.normalizer.normalize_text(q)
            raw_pattern = f"%{q.strip().lower()}%"
            normalized_pattern = f"%{normalized_q}%"
            query = query.where(
                or_(
                    func.lower(Clinic.name).like(raw_pattern),
                    Clinic.normalized_name.like(normalized_pattern),
                )
            )
        if category:
            query = query.where(ServiceCategory.normalized_name == self.normalizer.normalize_text(category))

        return query
