from datetime import UTC, datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicBranch,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    ImportErrorRecord,
    NormalizedService,
    ParserRun,
    PriceObservation,
    PriceHistory,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
    ServiceCategory,
    UnmatchedServiceRecord,
)
from app.schemas.import_prices import (
    ImportErrorItem,
    ImportPricesRequest,
    ImportPricesResult,
    ServiceImportPayload,
)
from app.services.normalization_service import NormalizationService
from app.services.parser_audit_service import ParserAuditService
from app.services.service_catalog_seed_service import ServiceCatalogSeedService


@dataclass(frozen=True)
class ProcessServiceResult:
    status: str
    service: Service
    current_price: ClinicServicePrice
    normalization_status: str = "unknown"
    normalization_confidence: float = 0.0


class ImportService:
    def __init__(self, db: Session, normalizer: NormalizationService | None = None) -> None:
        self.db = db
        self.normalizer = normalizer or NormalizationService()
        self.catalog_seed_service = ServiceCatalogSeedService(self.db, self.normalizer)
        self.parser_audit_service = ParserAuditService(self.db)
        self.service_adapter = TypeAdapter(ServiceImportPayload)

    def import_prices(self, payload: ImportPricesRequest) -> ImportPricesResult:
        data_source = self._upsert_data_source(payload)
        clinic = self._upsert_clinic(data_source, payload)
        branch = self._upsert_branch(clinic, payload)
        import_started_at = datetime.now(UTC)
        parser_run = self._get_parser_run(payload.parser_run_id)
        raw_snapshot = self._save_raw_snapshot(data_source, parser_run, payload)

        batch = ImportBatch(
            data_source_id=data_source.id,
            source_batch_id=payload.source_batch_id,
            parser_run_id=parser_run.id if parser_run else None,
            status="failed",
            received_count=len(payload.services),
            created_count=0,
            updated_count=0,
            unchanged_count=0,
            error_count=0,
            raw_payload=self._payload_for_json(payload),
            started_at=import_started_at,
        )
        self.db.add(batch)
        self.db.flush()

        errors: list[ImportErrorItem] = []

        for index, raw_service in enumerate(payload.services):
            try:
                service_payload = self.service_adapter.validate_python(raw_service)
                result = self._process_service(
                    data_source=data_source,
                    clinic=clinic,
                    branch=branch,
                    batch=batch,
                    service_payload=service_payload,
                    default_source_url=payload.source_url,
                    default_parsed_at=import_started_at,
                )
                raw_row = self._save_or_link_raw_row(
                    data_source=data_source,
                    parser_run=parser_run,
                    raw_snapshot=raw_snapshot,
                    batch=batch,
                    row_index=index,
                    raw_service=raw_service,
                    service_payload=service_payload,
                    service=result.service,
                    current_price=result.current_price,
                )
                self._create_price_observation(
                    data_source=data_source,
                    parser_run=parser_run,
                    batch=batch,
                    raw_row=raw_row,
                    current_price=result.current_price,
                    service=result.service,
                    service_payload=service_payload,
                    source_url=service_payload.source_url or payload.source_url,
                    parsed_at=service_payload.parsed_at or import_started_at,
                    change_detected=result.status != "unchanged",
                )
                if result.normalization_status == "unmatched":
                    self._save_or_update_unmatched_record(
                        data_source=data_source,
                        batch=batch,
                        service=result.service,
                        raw_row=raw_row,
                        service_payload=service_payload,
                        source_url=service_payload.source_url or payload.source_url,
                        raw_item=service_payload.raw_item or raw_service,
                        confidence=result.normalization_confidence,
                    )
                if result.status == "created":
                    batch.created_count += 1
                elif result.status == "updated":
                    batch.updated_count += 1
                else:
                    batch.unchanged_count += 1
            except ValidationError as exc:
                error = self._validation_error(index, raw_service, exc)
                errors.append(error)
                self._save_import_error(batch, error, raw_service)
                self._save_invalid_raw_row(
                    data_source=data_source,
                    parser_run=parser_run,
                    raw_snapshot=raw_snapshot,
                    batch=batch,
                    row_index=index,
                    raw_service=raw_service,
                    error=error,
                )
            except Exception as exc:
                error = ImportErrorItem(
                    index=index,
                    external_id=self._external_id(raw_service),
                    code="UNKNOWN_ERROR",
                    message=str(exc),
                    field=None,
                )
                errors.append(error)
                self._save_import_error(batch, error, raw_service)
                self._save_invalid_raw_row(
                    data_source=data_source,
                    parser_run=parser_run,
                    raw_snapshot=raw_snapshot,
                    batch=batch,
                    row_index=index,
                    raw_service=raw_service,
                    error=error,
                )

        batch.error_count = len(errors)
        imported_count = batch.created_count + batch.updated_count + batch.unchanged_count
        if batch.error_count == 0:
            batch.status = "success"
        elif imported_count > 0:
            batch.status = "partial_success"
        else:
            batch.status = "failed"
        batch.finished_at = datetime.now(UTC)
        if parser_run:
            parser_run.imported_count += imported_count

        self.db.commit()
        self.db.refresh(batch)
        self.db.refresh(clinic)
        self.db.refresh(branch)

        return ImportPricesResult(
            batch_id=batch.id,
            status=batch.status,
            source=data_source.name,
            clinic_id=clinic.id,
            branch_id=branch.id,
            received_count=batch.received_count,
            created_count=batch.created_count,
            updated_count=batch.updated_count,
            unchanged_count=batch.unchanged_count,
            error_count=batch.error_count,
            errors=errors,
        )

    def _upsert_data_source(self, payload: ImportPricesRequest) -> DataSource:
        data_source = self.db.scalar(select(DataSource).where(DataSource.name == payload.source))
        if data_source:
            self._apply_data_source_metadata(data_source, payload)
            return data_source
        data_source = DataSource(name=payload.source, type=payload.source_type or "external", is_active=True)
        self._apply_data_source_metadata(data_source, payload)
        self.db.add(data_source)
        self.db.flush()
        return data_source

    def _apply_data_source_metadata(
        self,
        data_source: DataSource,
        payload: ImportPricesRequest,
    ) -> None:
        if payload.source_type is not None:
            data_source.type = payload.source_type
        if payload.source_url is not None:
            data_source.public_url = payload.source_url
        if payload.robots_policy_notes is not None:
            data_source.robots_policy_notes = payload.robots_policy_notes
        if payload.crawl_delay_seconds is not None:
            data_source.crawl_delay_seconds = payload.crawl_delay_seconds

    def _upsert_clinic(self, data_source: DataSource, payload: ImportPricesRequest) -> Clinic:
        clinic_payload = payload.clinic
        normalized_name = self.normalizer.normalize_text(clinic_payload.name)
        normalized_city = self.normalizer.normalize_text(clinic_payload.city)

        clinic = self.db.scalar(
            select(Clinic).where(
                Clinic.data_source_id == data_source.id,
                Clinic.external_id == clinic_payload.external_id,
            )
        )
        if not clinic:
            clinic = self.db.scalar(
                select(Clinic).where(
                    Clinic.normalized_name == normalized_name,
                    Clinic.city == clinic_payload.city,
                )
            )
        if clinic:
            clinic.name = clinic_payload.name
            clinic.normalized_name = normalized_name
            clinic.legal_name = clinic_payload.legal_name
            clinic.city = clinic_payload.city
            clinic.phone = clinic_payload.phone
            clinic.website = clinic_payload.website
            return clinic

        clinic = Clinic(
            data_source_id=data_source.id,
            external_id=clinic_payload.external_id,
            name=clinic_payload.name,
            normalized_name=normalized_name,
            legal_name=clinic_payload.legal_name,
            city=clinic_payload.city,
            phone=clinic_payload.phone,
            website=clinic_payload.website,
            is_active=True,
        )
        self.db.add(clinic)
        self.db.flush()
        return clinic

    def _upsert_branch(self, clinic: Clinic, payload: ImportPricesRequest) -> ClinicBranch:
        branch_payload = payload.branch
        if branch_payload:
            external_id = branch_payload.external_id
            name = branch_payload.name
            city = branch_payload.city or payload.clinic.city
            address = branch_payload.address or payload.clinic.address or "Default branch"
            phone = branch_payload.phone or payload.clinic.phone
            latitude = branch_payload.latitude
            longitude = branch_payload.longitude
            is_default = False
        else:
            external_id = None
            name = "Default branch"
            city = payload.clinic.city
            address = payload.clinic.address or "Default branch"
            phone = payload.clinic.phone
            latitude = None
            longitude = None
            is_default = True

        normalized_address = self.normalizer.normalize_text(address)
        branch = None
        if external_id:
            branch = self.db.scalar(
                select(ClinicBranch).where(
                    ClinicBranch.clinic_id == clinic.id,
                    ClinicBranch.external_id == external_id,
                )
            )
        if not branch:
            branch = self.db.scalar(
                select(ClinicBranch).where(
                    ClinicBranch.clinic_id == clinic.id,
                    ClinicBranch.normalized_address == normalized_address,
                )
            )
        if branch:
            branch.name = name
            branch.city = city
            branch.address = address
            branch.normalized_address = normalized_address
            branch.phone = phone
            branch.latitude = latitude
            branch.longitude = longitude
            branch.is_default = is_default
            return branch

        branch = ClinicBranch(
            clinic_id=clinic.id,
            external_id=external_id,
            name=name,
            city=city,
            address=address,
            normalized_address=normalized_address,
            phone=phone,
            latitude=latitude,
            longitude=longitude,
            is_default=is_default,
            is_active=True,
        )
        self.db.add(branch)
        self.db.flush()
        return branch

    def _get_parser_run(self, parser_run_id: int | None) -> ParserRun | None:
        if parser_run_id is None:
            return None
        return self.db.get(ParserRun, parser_run_id)

    def _save_raw_snapshot(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None,
        payload: ImportPricesRequest,
    ) -> RawSourceSnapshot | None:
        if payload.raw_snapshot is None:
            return None
        return self.parser_audit_service.save_raw_snapshot(
            data_source=data_source,
            parser_run=parser_run,
            source_url=payload.raw_snapshot.source_url or payload.source_url,
            requested_url=payload.raw_snapshot.requested_url,
            final_url=payload.raw_snapshot.final_url,
            http_status=payload.raw_snapshot.http_status,
            response_headers=payload.raw_snapshot.response_headers,
            content_type=payload.raw_snapshot.content_type,
            checksum=payload.raw_snapshot.checksum,
            content_sha256=payload.raw_snapshot.content_sha256,
            byte_size=payload.raw_snapshot.byte_size,
            storage_uri=payload.raw_snapshot.storage_uri,
            source_document_date=payload.raw_snapshot.source_document_date,
            raw_payload=payload.raw_snapshot.raw_payload,
            captured_at=payload.raw_snapshot.captured_at,
        )

    def _process_service(
        self,
        data_source: DataSource,
        clinic: Clinic,
        branch: ClinicBranch,
        batch: ImportBatch,
        service_payload: ServiceImportPayload,
        default_source_url: str | None,
        default_parsed_at: datetime,
    ) -> ProcessServiceResult:
        normalized_name = self.normalizer.normalize_service_name(service_payload.name)
        catalog_match = self.catalog_seed_service.find_catalog_match_result(
            service_payload.category,
            service_payload.name,
        )
        if catalog_match:
            normalized_service = catalog_match.service
            category = catalog_match.service.category
            normalization_status = catalog_match.match_type
            normalization_confidence = catalog_match.confidence
        else:
            category = self._upsert_category(service_payload.category)
            normalized_service = self._upsert_unmatched_normalized_service(category)
            normalization_status = "unmatched"
            normalization_confidence = 0.0
        service = self._upsert_service(
            data_source=data_source,
            category=category,
            normalized_service=normalized_service,
            service_payload=service_payload,
            normalized_name=normalized_name,
            normalization_status=normalization_status,
            normalization_confidence=normalization_confidence,
        )
        result = self._upsert_price(
            data_source=data_source,
            clinic=clinic,
            branch=branch,
            service=service,
            normalized_service=normalized_service,
            batch=batch,
            service_payload=service_payload,
            source_url=service_payload.source_url or default_source_url,
            parsed_at=service_payload.parsed_at or default_parsed_at,
        )
        return ProcessServiceResult(
            status=result.status,
            service=result.service,
            current_price=result.current_price,
            normalization_status=normalization_status,
            normalization_confidence=normalization_confidence,
        )

    def _upsert_category(self, category_name: str) -> ServiceCategory:
        normalized_name = self.normalizer.normalize_text(category_name)
        category = self.db.scalar(
            select(ServiceCategory).where(ServiceCategory.normalized_name == normalized_name)
        )
        if category:
            return category
        category = ServiceCategory(
            name=category_name,
            slug=self.normalizer.slugify(category_name),
            normalized_name=normalized_name,
        )
        self.db.add(category)
        self.db.flush()
        return category

    def _upsert_normalized_service(
        self,
        category: ServiceCategory,
        normalized_name: str,
    ) -> NormalizedService:
        slug = self.normalizer.slugify(f"{category.normalized_name}-{normalized_name}")
        normalized_service = self.db.scalar(
            select(NormalizedService).where(NormalizedService.slug == slug)
        )
        if normalized_service:
            return normalized_service
        normalized_service = NormalizedService(
            category_id=category.id,
            name=normalized_name,
            slug=slug,
            aliases=[],
        )
        self.db.add(normalized_service)
        self.db.flush()
        return normalized_service

    def _upsert_unmatched_normalized_service(self, category: ServiceCategory) -> NormalizedService:
        normalized_name = "unmatched service"
        slug = self.normalizer.slugify(f"{category.normalized_name}-{normalized_name}")
        normalized_service = self.db.scalar(
            select(NormalizedService).where(NormalizedService.slug == slug)
        )
        if normalized_service:
            return normalized_service
        normalized_service = NormalizedService(
            category_id=category.id,
            name=normalized_name,
            slug=slug,
            aliases=[],
        )
        self.db.add(normalized_service)
        self.db.flush()
        return normalized_service

    def _upsert_service(
        self,
        data_source: DataSource,
        category: ServiceCategory,
        normalized_service: NormalizedService,
        service_payload: ServiceImportPayload,
        normalized_name: str,
        normalization_status: str,
        normalization_confidence: float,
    ) -> Service:
        service = None
        if service_payload.external_id:
            service = self.db.scalar(
                select(Service).where(
                    Service.data_source_id == data_source.id,
                    Service.external_id == service_payload.external_id,
                )
            )
        if not service:
            service = self.db.scalar(
                select(Service).where(
                    Service.normalized_service_id == normalized_service.id,
                    Service.normalized_name == normalized_name,
                )
            )
        if service:
            service.category_id = category.id
            service.normalized_service_id = normalized_service.id
            service.name = service_payload.name
            service.normalized_name = normalized_name
            service.normalization_status = normalization_status
            service.normalization_confidence = normalization_confidence
            service.description = service_payload.description
            service.duration_minutes = service_payload.duration_minutes
            service.is_active = True
            return service

        service = Service(
            data_source_id=data_source.id,
            external_id=service_payload.external_id,
            category_id=category.id,
            normalized_service_id=normalized_service.id,
            name=service_payload.name,
            normalized_name=normalized_name,
            normalization_status=normalization_status,
            normalization_confidence=normalization_confidence,
            description=service_payload.description,
            duration_minutes=service_payload.duration_minutes,
            is_active=True,
        )
        self.db.add(service)
        self.db.flush()
        return service

    def _save_or_update_unmatched_record(
        self,
        data_source: DataSource,
        batch: ImportBatch,
        service: Service,
        raw_row: RawSourceRow | None,
        service_payload: ServiceImportPayload,
        source_url: str | None,
        raw_item: dict[str, Any],
        confidence: float,
    ) -> UnmatchedServiceRecord:
        record = self.db.scalar(
            select(UnmatchedServiceRecord).where(UnmatchedServiceRecord.service_id == service.id)
        )
        if record is None:
            now = datetime.now(UTC)
            record = UnmatchedServiceRecord(
                data_source_id=data_source.id,
                service_id=service.id,
                reason="NO_CATALOG_MATCH",
                occurrence_count=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(record)
        else:
            record.occurrence_count += 1
            record.last_seen_at = datetime.now(UTC)

        record.import_batch_id = batch.id
        record.raw_source_row_id = raw_row.id if raw_row else None
        record.raw_category = service_payload.category
        record.raw_name = service_payload.name
        record.normalized_raw_category = self.normalizer.normalize_text(service_payload.category)
        record.normalized_raw_name = self.normalizer.normalize_service_name(service_payload.name)
        record.confidence = confidence
        record.source_url = source_url
        record.raw_item = raw_item
        if record.status != "resolved":
            record.status = "open"
        self.db.flush()
        return record

    def _upsert_price(
        self,
        data_source: DataSource,
        clinic: Clinic,
        branch: ClinicBranch,
        service: Service,
        normalized_service: NormalizedService,
        batch: ImportBatch,
        service_payload: ServiceImportPayload,
        source_url: str | None,
        parsed_at: datetime,
    ) -> ProcessServiceResult:
        current_price = self.db.scalar(
            select(ClinicServicePrice).where(
                ClinicServicePrice.clinic_id == clinic.id,
                ClinicServicePrice.branch_id == branch.id,
                ClinicServicePrice.service_id == service.id,
                ClinicServicePrice.currency == service_payload.currency,
            )
        )
        now = datetime.now(UTC)
        if not current_price:
            current_price = ClinicServicePrice(
                clinic_id=clinic.id,
                branch_id=branch.id,
                service_id=service.id,
                normalized_service_id=normalized_service.id,
                price=service_payload.price,
                currency=service_payload.currency,
                is_available=service_payload.is_available,
                updated_at=service_payload.updated_at,
                source_url=source_url,
                parsed_at=parsed_at,
                last_seen_at=now,
            )
            self.db.add(current_price)
            self.db.flush()
            self._create_price_history(
                current_price=current_price,
                clinic=clinic,
                branch=branch,
                service=service,
                data_source=data_source,
                batch=batch,
                old_price=None,
                new_price=service_payload.price,
                currency=service_payload.currency,
                source_url=source_url,
                parsed_at=parsed_at,
                change_type="created",
            )
            return ProcessServiceResult(
                status="created",
                service=service,
                current_price=current_price,
            )

        if Decimal(current_price.price) == service_payload.price:
            current_price.last_seen_at = now
            current_price.is_available = service_payload.is_available
            current_price.updated_at = service_payload.updated_at
            current_price.source_url = source_url
            current_price.parsed_at = parsed_at
            return ProcessServiceResult(
                status="unchanged",
                service=service,
                current_price=current_price,
            )

        old_price = Decimal(current_price.price)
        current_price.price = service_payload.price
        current_price.updated_at = service_payload.updated_at
        current_price.last_seen_at = now
        current_price.is_available = service_payload.is_available
        current_price.source_url = source_url
        current_price.parsed_at = parsed_at
        self._create_price_history(
            current_price=current_price,
            clinic=clinic,
            branch=branch,
            service=service,
            data_source=data_source,
            batch=batch,
            old_price=old_price,
            new_price=service_payload.price,
            currency=service_payload.currency,
            source_url=source_url,
            parsed_at=parsed_at,
            change_type="updated",
        )
        return ProcessServiceResult(
            status="updated",
            service=service,
            current_price=current_price,
        )

    def _save_or_link_raw_row(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None,
        raw_snapshot: RawSourceSnapshot | None,
        batch: ImportBatch,
        row_index: int,
        raw_service: dict[str, Any],
        service_payload: ServiceImportPayload,
        service: Service,
        current_price: ClinicServicePrice,
    ) -> RawSourceRow:
        if service_payload.raw_source_row_id is not None:
            raw_row = self.db.get(RawSourceRow, service_payload.raw_source_row_id)
            if raw_row:
                raw_row.import_batch_id = batch.id
                raw_row.service_id = service.id
                raw_row.clinic_service_price_id = current_price.id
                raw_row.validation_status = "valid"
                raw_row.rejection_details = None
                return raw_row

        raw_item = service_payload.raw_item if service_payload.raw_item is not None else raw_service
        return self.parser_audit_service.save_raw_row(
            data_source=data_source,
            parser_run=parser_run,
            snapshot=raw_snapshot,
            import_batch_id=batch.id,
            row_index=row_index,
            source_url=service_payload.source_url,
            raw_item=raw_item,
            service_id=service.id,
            clinic_service_price_id=current_price.id,
            validation_status="valid",
        )

    def _save_invalid_raw_row(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None,
        raw_snapshot: RawSourceSnapshot | None,
        batch: ImportBatch,
        row_index: int,
        raw_service: dict[str, Any],
        error: ImportErrorItem,
    ) -> None:
        self.parser_audit_service.save_raw_row(
            data_source=data_source,
            parser_run=parser_run,
            snapshot=raw_snapshot,
            import_batch_id=batch.id,
            row_index=row_index,
            source_url=self._source_url(raw_service),
            raw_item=raw_service.get("raw_item") or raw_service,
            validation_status="invalid",
            rejection_details={
                "code": error.code,
                "message": error.message,
                "field": error.field,
            },
        )

    def _create_price_observation(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None,
        batch: ImportBatch,
        raw_row: RawSourceRow,
        current_price: ClinicServicePrice,
        service: Service,
        service_payload: ServiceImportPayload,
        source_url: str | None,
        parsed_at: datetime,
        change_detected: bool,
    ) -> None:
        self.db.add(
            PriceObservation(
                clinic_service_price_id=current_price.id,
                clinic_id=current_price.clinic_id,
                branch_id=current_price.branch_id,
                service_id=service.id,
                normalized_service_id=current_price.normalized_service_id,
                import_batch_id=batch.id,
                data_source_id=data_source.id,
                parser_run_id=parser_run.id if parser_run else None,
                raw_source_row_id=raw_row.id,
                price=service_payload.price,
                currency=service_payload.currency,
                is_available=service_payload.is_available,
                source_updated_at=service_payload.updated_at,
                source_url=source_url,
                parsed_at=parsed_at,
                change_detected=change_detected,
            )
        )

    def _create_price_history(
        self,
        current_price: ClinicServicePrice,
        clinic: Clinic,
        branch: ClinicBranch,
        service: Service,
        data_source: DataSource,
        batch: ImportBatch,
        old_price: Decimal | None,
        new_price: Decimal,
        currency: str,
        source_url: str | None,
        parsed_at: datetime,
        change_type: str,
    ) -> None:
        self.db.add(
            PriceHistory(
                clinic_service_price_id=current_price.id,
                clinic_id=clinic.id,
                branch_id=branch.id,
                service_id=service.id,
                old_price=old_price,
                new_price=new_price,
                currency=currency,
                change_type=change_type,
                import_batch_id=batch.id,
                data_source_id=data_source.id,
                source_url=source_url,
                parsed_at=parsed_at,
            )
        )

    def _validation_error(
        self,
        index: int,
        raw_service: dict[str, Any],
        exc: ValidationError,
    ) -> ImportErrorItem:
        first_error = exc.errors()[0]
        loc = ".".join(str(item) for item in first_error.get("loc", ()))
        return ImportErrorItem(
            index=index,
            external_id=self._external_id(raw_service),
            code="VALIDATION_ERROR",
            message=str(first_error.get("msg", "Invalid service item")),
            field=f"services[{index}].{loc}" if loc else f"services[{index}]",
        )

    def _save_import_error(
        self,
        batch: ImportBatch,
        error: ImportErrorItem,
        raw_service: dict[str, Any],
    ) -> None:
        self.db.add(
            ImportErrorRecord(
                import_batch_id=batch.id,
                row_index=error.index,
                external_id=error.external_id,
                code=error.code,
                message=error.message,
                field=error.field,
                raw_item=raw_service,
            )
        )

    def _payload_for_json(self, payload: ImportPricesRequest) -> dict[str, Any]:
        return payload.model_dump(mode="json")

    def _external_id(self, raw_service: dict[str, Any]) -> str | None:
        external_id = raw_service.get("external_id")
        return str(external_id) if external_id is not None else None

    def _source_url(self, raw_service: dict[str, Any]) -> str | None:
        source_url = raw_service.get("source_url")
        return str(source_url) if source_url is not None else None
