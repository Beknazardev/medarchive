import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    DataSource,
    ParserErrorRecord,
    ParserRun,
    RawSourceRow,
    RawSourceSnapshot,
)
from app.ingestion.contracts import ParserStage, SourceDocument


DEFAULT_RAW_RETENTION_DAYS = 90


class ParserAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_parser_run(
        self,
        data_source: DataSource,
        status: str = "running",
        source_url: str | None = None,
        started_at: datetime | None = None,
        parsed_at: datetime | None = None,
        received_count: int = 0,
        imported_count: int = 0,
        error_count: int = 0,
        notes: str | None = None,
    ) -> ParserRun:
        parser_run = ParserRun(
            data_source_id=data_source.id,
            status=status,
            source_url=source_url,
            started_at=started_at or datetime.now(UTC),
            parsed_at=parsed_at,
            received_count=received_count,
            imported_count=imported_count,
            error_count=error_count,
            raw_snapshot_count=0,
            raw_row_count=0,
            notes=notes,
        )
        self.db.add(parser_run)
        self.db.flush()
        return parser_run

    def finish_parser_run(
        self,
        parser_run: ParserRun,
        status: str,
        imported_count: int | None = None,
        error_count: int | None = None,
        finished_at: datetime | None = None,
    ) -> ParserRun:
        parser_run.status = status
        parser_run.finished_at = finished_at or datetime.now(UTC)
        if imported_count is not None:
            parser_run.imported_count = imported_count
        if error_count is not None:
            parser_run.error_count = error_count
        self.db.flush()
        return parser_run

    def save_parser_error(
        self,
        parser_run: ParserRun,
        code: str,
        message: str,
        severity: str = "error",
        stage: str = "unknown",
        retryable: bool = False,
        source_url: str | None = None,
        raw_item: dict[str, Any] | list[Any] | str | None = None,
    ) -> ParserErrorRecord:
        error = ParserErrorRecord(
            parser_run_id=parser_run.id,
            data_source_id=parser_run.data_source_id,
            code=code,
            message=message,
            severity=severity,
            stage=stage,
            retryable=retryable,
            source_url=source_url,
            raw_item=raw_item,
        )
        parser_run.error_count += 1
        self.db.add(error)
        self.db.flush()
        return error

    def save_stage_error(
        self,
        parser_run: ParserRun,
        stage: ParserStage,
        code: str,
        message: str,
        retryable: bool,
        source_url: str | None = None,
    ) -> ParserErrorRecord:
        return self.save_parser_error(
            parser_run=parser_run,
            stage=stage.value,
            code=code,
            message=message,
            retryable=retryable,
            source_url=source_url,
        )

    def save_source_document(
        self,
        data_source: DataSource,
        document: SourceDocument,
        parser_run: ParserRun | None = None,
    ) -> RawSourceSnapshot:
        return self.save_raw_snapshot(
            data_source=data_source,
            parser_run=parser_run,
            source_url=document.final_url,
            requested_url=document.requested_url,
            final_url=document.final_url,
            http_status=document.status_code,
            response_headers=dict(document.headers_subset),
            content_type=document.content_type,
            checksum=document.content_sha256,
            content_sha256=document.content_sha256,
            byte_size=document.byte_size,
            storage_uri=document.storage_uri,
            source_document_date=document.source_document_date,
            raw_payload={
                "storage_only": document.storage_uri is not None,
                "body_persisted": document.storage_uri is not None,
            },
            captured_at=document.captured_at,
        )

    def save_raw_snapshot(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None = None,
        source_url: str | None = None,
        requested_url: str | None = None,
        final_url: str | None = None,
        http_status: int | None = None,
        response_headers: dict[str, str] | None = None,
        content_type: str | None = None,
        checksum: str | None = None,
        content_sha256: str | None = None,
        byte_size: int | None = None,
        storage_uri: str | None = None,
        source_document_date: date | None = None,
        raw_payload: dict[str, Any] | list[Any] | str | None = None,
        captured_at: datetime | None = None,
        retention_days: int = DEFAULT_RAW_RETENTION_DAYS,
    ) -> RawSourceSnapshot:
        captured = captured_at or datetime.now(UTC)
        snapshot = RawSourceSnapshot(
            parser_run_id=parser_run.id if parser_run else None,
            data_source_id=data_source.id,
            source_url=source_url,
            requested_url=requested_url,
            final_url=final_url,
            http_status=http_status,
            response_headers=response_headers,
            content_type=content_type,
            checksum=checksum,
            content_sha256=content_sha256,
            byte_size=byte_size,
            storage_uri=storage_uri,
            source_document_date=source_document_date,
            raw_payload=raw_payload,
            captured_at=captured,
            retention_until=captured + timedelta(days=retention_days),
        )
        if parser_run:
            parser_run.raw_snapshot_count += 1
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def save_raw_row(
        self,
        data_source: DataSource,
        parser_run: ParserRun | None = None,
        snapshot: RawSourceSnapshot | None = None,
        import_batch_id: int | None = None,
        row_index: int | None = None,
        source_url: str | None = None,
        raw_item: dict[str, Any] | list[Any] | str | None = None,
        record_hash: str | None = None,
        extraction_status: str = "extracted",
        validation_status: str = "pending",
        rejection_details: dict[str, Any] | None = None,
        service_id: int | None = None,
        clinic_service_price_id: int | None = None,
        retention_days: int = DEFAULT_RAW_RETENTION_DAYS,
    ) -> RawSourceRow:
        created_at = datetime.now(UTC)
        raw_row = RawSourceRow(
            parser_run_id=parser_run.id if parser_run else None,
            snapshot_id=snapshot.id if snapshot else None,
            import_batch_id=import_batch_id,
            data_source_id=data_source.id,
            row_index=row_index,
            source_url=source_url,
            raw_item=raw_item,
            record_hash=record_hash or self._record_hash(raw_item),
            extraction_status=extraction_status,
            validation_status=validation_status,
            rejection_details=rejection_details,
            service_id=service_id,
            clinic_service_price_id=clinic_service_price_id,
            retention_until=created_at + timedelta(days=retention_days),
        )
        if parser_run:
            parser_run.raw_row_count += 1
        self.db.add(raw_row)
        self.db.flush()
        return raw_row

    @staticmethod
    def _record_hash(raw_item: dict[str, Any] | list[Any] | str | None) -> str:
        canonical = json.dumps(
            raw_item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
