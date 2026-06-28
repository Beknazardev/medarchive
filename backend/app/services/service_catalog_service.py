from decimal import Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicBranch,
    ClinicServicePrice,
    NormalizedService,
    Service,
    ServiceCategory,
)
from app.schemas.catalog import (
    CategoriesResponse,
    CategoryListItem,
    CitiesResponse,
    CityListItem,
    ServiceCategoryDetails,
    ServiceDetails,
    ServiceDetailsResponse,
    ServiceNormalizedDetails,
    ServicePriceDetails,
    ServiceStats,
)
from app.services.freshness_service import price_freshness


class ServiceCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_service(self, service_id: int) -> ServiceDetailsResponse | None:
        service = self.db.get(Service, service_id)
        if not service:
            return None

        normalized_service = self.db.get(NormalizedService, service.normalized_service_id)
        category = self.db.get(ServiceCategory, service.category_id)
        price_rows = self.db.execute(
            select(Clinic, ClinicBranch, ClinicServicePrice)
            .join(ClinicServicePrice, ClinicServicePrice.clinic_id == Clinic.id)
            .join(ClinicBranch, ClinicBranch.id == ClinicServicePrice.branch_id)
            .where(ClinicServicePrice.service_id == service.id)
            .order_by(ClinicServicePrice.price.asc(), Clinic.name.asc())
        ).all()

        prices = [
            self._price_details(clinic, branch, price)
            for clinic, branch, price in price_rows
        ]

        return ServiceDetailsResponse(
            data=ServiceDetails(
                id=service.id,
                name=service.name,
                normalized_service=ServiceNormalizedDetails(
                    id=normalized_service.id,
                    name=self._normalized_service_display_name(service, normalized_service),
                ),
                category=ServiceCategoryDetails(id=category.id, name=category.name),
                prices=prices,
                stats=self._stats(prices),
            )
        )

    def list_categories(self) -> CategoriesResponse:
        rows = self.db.execute(
            select(
                ServiceCategory.id,
                ServiceCategory.name,
                ServiceCategory.slug,
                func.count(distinct(Service.id)).label("services_count"),
            )
            .join(Service, Service.category_id == ServiceCategory.id, isouter=True)
            .group_by(ServiceCategory.id)
            .order_by(ServiceCategory.name.asc())
        ).all()

        return CategoriesResponse(
            data=[
                CategoryListItem(
                    id=row.id,
                    name=row.name,
                    slug=row.slug,
                    services_count=row.services_count,
                )
                for row in rows
            ]
        )

    def list_cities(self) -> CitiesResponse:
        rows = self.db.execute(
            select(
                ClinicBranch.city.label("name"),
                func.count(distinct(Clinic.id)).label("clinics_count"),
                func.count(distinct(ClinicServicePrice.service_id)).label("services_count"),
            )
            .join(Clinic, Clinic.id == ClinicBranch.clinic_id)
            .join(ClinicServicePrice, ClinicServicePrice.branch_id == ClinicBranch.id, isouter=True)
            .group_by(ClinicBranch.city)
            .order_by(ClinicBranch.city.asc())
        ).all()

        return CitiesResponse(
            data=[
                CityListItem(
                    name=row.name,
                    clinics_count=row.clinics_count,
                    services_count=row.services_count,
                )
                for row in rows
            ]
        )

    def _stats(self, prices: list[ServicePriceDetails]) -> ServiceStats:
        if not prices:
            return ServiceStats(min_price=None, max_price=None, average_price=None, count=0)

        amounts = [Decimal(price.amount) for price in prices]
        average = (sum(amounts) / Decimal(len(amounts))).quantize(Decimal("0.01"))
        return ServiceStats(
            min_price=min(amounts),
            max_price=max(amounts),
            average_price=average,
            count=len(amounts),
        )

    def _price_details(
        self,
        clinic: Clinic,
        branch: ClinicBranch,
        price: ClinicServicePrice,
    ) -> ServicePriceDetails:
        freshness = price_freshness(price.parsed_at, price.updated_at)
        return ServicePriceDetails(
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            branch_id=branch.id,
            city=branch.city,
            address=branch.address,
            latitude=float(branch.latitude) if branch.latitude else None,
            longitude=float(branch.longitude) if branch.longitude else None,
            amount=price.price,
            currency=price.currency,
            updated_at=price.updated_at,
            source_url=price.source_url,
            parsed_at=price.parsed_at,
            freshness_state=freshness.state,
            freshness_age_days=freshness.age_days,
        )

    def _normalized_service_display_name(
        self,
        service: Service,
        normalized_service: NormalizedService,
    ) -> str:
        if service.normalization_status == "unmatched":
            return service.normalized_name
        return normalized_service.name
