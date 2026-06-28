from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.service_catalog_excel import load_official_service_catalog
from app.models import NormalizedService, Service, ServiceCategory
from app.services.normalization_service import NormalizationService


CANONICAL_SERVICES_PATH = Path(__file__).resolve().parents[1] / "data" / "canonical_services.json"


@dataclass(frozen=True)
class CatalogSeedResult:
    total: int
    created: int
    updated: int


@dataclass(frozen=True)
class CatalogMatchResult:
    service: NormalizedService
    match_type: str
    confidence: float


class ServiceCatalogSeedService:
    def __init__(
        self,
        db: Session,
        normalizer: NormalizationService | None = None,
    ) -> None:
        self.db = db
        self.normalizer = normalizer or NormalizationService()

    def seed_default_catalog(
        self,
        catalog: list[dict[str, Any]] | None = None,
        commit: bool = True,
    ) -> CatalogSeedResult:
        created = 0
        updated = 0
        items = catalog if catalog is not None else load_official_service_catalog()

        for item in items:
            category = self._upsert_category(str(item["category"]))
            name = str(item["name"])
            aliases = [str(alias) for alias in item.get("aliases", [])]
            normalized_name = self.normalizer.normalize_service_name(name)
            normalized_aliases = self._normalized_aliases(aliases)
            slug = self.normalizer.slugify(f"{category.normalized_name}-{normalized_name}")

            normalized_service = self.db.scalar(
                select(NormalizedService).where(NormalizedService.slug == slug)
            )
            if normalized_service:
                normalized_service.category_id = category.id
                normalized_service.name = normalized_name
                normalized_service.aliases = self._merge_aliases(
                    normalized_service.aliases,
                    normalized_aliases,
                )
                updated += 1
                continue

            self.db.add(
                NormalizedService(
                    category_id=category.id,
                    name=normalized_name,
                    slug=slug,
                    aliases=normalized_aliases,
                )
            )
            created += 1

        self.db.flush()
        if commit:
            self.db.commit()
        return CatalogSeedResult(total=len(items), created=created, updated=updated)

    def seed_canonical_services(self, commit: bool = True) -> CatalogSeedResult:
        """Seed canonical services with localized names."""
        import json

        if not CANONICAL_SERVICES_PATH.exists():
            return CatalogSeedResult(total=0, created=0, updated=0)

        with open(CANONICAL_SERVICES_PATH, encoding="utf-8") as f:
            canonical_items = json.load(f)

        created = 0
        updated = 0

        for item in canonical_items:
            canonical_key = item["canonical_key"]
            name_ru = item["name_ru"]
            name_kk = item.get("name_kk", name_ru)
            name_en = item.get("name_en", name_ru)
            category_ru = item["category_ru"]
            category_kk = item.get("category_kk", category_ru)
            category_en = item.get("category_en", category_ru)
            aliases = item.get("aliases", [])

            category = self._upsert_category_with_names(
                category_ru, category_kk, category_en
            )

            normalized_name = self.normalizer.normalize_service_name(name_ru)
            normalized_aliases = self._normalized_aliases(aliases)
            slug = self.normalizer.slugify(f"{category.normalized_name}-{normalized_name}")

            existing = self.db.scalar(
                select(NormalizedService).where(NormalizedService.canonical_key == canonical_key)
            )
            if not existing:
                existing = self.db.scalar(
                    select(NormalizedService).where(NormalizedService.slug == slug)
                )

            if existing:
                existing.canonical_key = canonical_key
                existing.name_ru = name_ru
                existing.name_kk = name_kk
                existing.name_en = name_en
                existing.category_ru = category_ru
                existing.category_kk = category_kk
                existing.category_en = category_en
                existing.aliases = self._merge_aliases(existing.aliases, normalized_aliases)
                updated += 1
            else:
                self.db.add(
                    NormalizedService(
                        category_id=category.id,
                        name=normalized_name,
                        slug=slug,
                        aliases=normalized_aliases,
                        canonical_key=canonical_key,
                        name_ru=name_ru,
                        name_kk=name_kk,
                        name_en=name_en,
                        category_ru=category_ru,
                        category_kk=category_kk,
                        category_en=category_en,
                    )
                )
                created += 1

        self.db.flush()

        existing_with_keys = self.db.scalars(
            select(NormalizedService.canonical_key).where(NormalizedService.canonical_key.isnot(None))
        ).all()
        used_canonical_keys: set[str] = set(existing_with_keys)

        canonical_map = {item["canonical_key"]: item for item in canonical_items}
        canonical_by_key = self.db.scalars(
            select(NormalizedService).where(NormalizedService.canonical_key.isnot(None))
        ).all()
        canonical_ns_map = {ns.canonical_key: ns for ns in canonical_by_key}

        all_services = self.db.scalars(select(Service)).all()
        relinked = 0

        for service in all_services:
            s_normalized = self.normalizer.normalize_service_name(service.name)
            for canonical_key, canonical_item in canonical_map.items():
                canonical_aliases = canonical_item.get("aliases", [])
                canonical_normalized = [self.normalizer.normalize_service_name(a) for a in canonical_aliases]
                canonical_name_normalized = self.normalizer.normalize_service_name(canonical_item["name_ru"])

                if (s_normalized in canonical_normalized or
                    s_normalized == canonical_name_normalized or
                    service.name in [self.normalizer.normalize_service_name(a) for a in canonical_aliases]):
                    target_ns = canonical_ns_map.get(canonical_key)
                    if target_ns and service.normalized_service_id != target_ns.id:
                        service.normalized_service_id = target_ns.id
                        service.normalization_status = "matched"
                        relinked += 1
                    break

        self.db.flush()
        if commit:
            self.db.commit()
        return CatalogSeedResult(total=len(canonical_items), created=created, updated=updated + relinked)

    def _upsert_category_with_names(
        self, name_ru: str, name_kk: str, name_en: str
    ) -> ServiceCategory:
        normalized_name = self.normalizer.normalize_text(name_ru)
        category = self.db.scalar(
            select(ServiceCategory).where(ServiceCategory.normalized_name == normalized_name)
        )
        if category:
            category.name_ru = name_ru
            category.name_kk = name_kk
            category.name_en = name_en
            return category

        category = ServiceCategory(
            name=name_ru,
            slug=self.normalizer.slugify(name_ru),
            normalized_name=normalized_name,
            name_ru=name_ru,
            name_kk=name_kk,
            name_en=name_en,
        )
        self.db.add(category)
        self.db.flush()
        return category

    def find_catalog_match(
        self,
        category_name: str,
        service_name: str,
    ) -> NormalizedService | None:
        result = self.find_catalog_match_result(category_name, service_name)
        return result.service if result else None

    def find_catalog_match_result(
        self,
        category_name: str,
        service_name: str,
    ) -> CatalogMatchResult | None:
        normalized_category = self.normalizer.normalize_text(category_name)
        normalized_service_name = self.normalizer.normalize_service_name(service_name)

        category = self.db.scalar(
            select(ServiceCategory).where(ServiceCategory.normalized_name == normalized_category)
        )
        if category:
            match = self._match_in_services(
                category.normalized_services,
                normalized_service_name,
            )
            if match:
                return match

        services = self.db.scalars(select(NormalizedService)).all()
        return self._match_in_services(services, normalized_service_name)

    def _upsert_category(self, category_name: str) -> ServiceCategory:
        normalized_name = self.normalizer.normalize_text(category_name)
        category = self.db.scalar(
            select(ServiceCategory).where(ServiceCategory.normalized_name == normalized_name)
        )
        if category:
            category.name = category_name
            category.slug = self.normalizer.slugify(category_name)
            return category

        category = ServiceCategory(
            name=category_name,
            slug=self.normalizer.slugify(category_name),
            normalized_name=normalized_name,
        )
        self.db.add(category)
        self.db.flush()
        return category

    def _normalized_aliases(self, aliases: list[str]) -> list[str]:
        values = [self.normalizer.normalize_service_name(alias) for alias in aliases]
        return sorted({value for value in values if value})

    def _merge_aliases(self, existing: list[str] | None, new_aliases: list[str]) -> list[str]:
        normalized_existing = {
            self.normalizer.normalize_service_name(alias)
            for alias in existing or []
            if alias
        }
        return sorted(normalized_existing.union(new_aliases))

    def _match_in_services(
        self,
        services: list[NormalizedService],
        normalized_service_name: str,
    ) -> CatalogMatchResult | None:
        for service in services:
            aliases = set(service.aliases or [])
            if service.name == normalized_service_name:
                return CatalogMatchResult(
                    service=service,
                    match_type="matched",
                    confidence=1.0,
                )
            if normalized_service_name in aliases:
                return CatalogMatchResult(
                    service=service,
                    match_type="alias_matched",
                    confidence=0.9,
                )
        return None
