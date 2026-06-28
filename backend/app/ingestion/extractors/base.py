"""Shared types, limits, and errors for all document extractors."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParserStage(str, Enum):
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    EXCEL = "excel"
    TEXT = "text"


class ExtractorError(Exception):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        code: str,
        recoverable: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.recoverable = recoverable
        self.context = context or {}


class ManualReviewRequired(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="MANUAL_REVIEW_REQUIRED", **kwargs)


class UnsupportedFormat(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="UNSUPPORTED_FORMAT", **kwargs)


class MIMEMismatch(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="MIME_MISMATCH", **kwargs)


class PasswordProtected(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="PASSWORD_PROTECTED", **kwargs)


class MalformedDocument(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="MALFORMED_DOCUMENT", **kwargs)


class ZipBombDetected(ExtractorError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, stage=kwargs.pop("stage", "unknown"), code="ZIP_BOMB_DETECTED", **kwargs)


@dataclass(frozen=True)
class GenericCell:
    text: str
    row_index: int
    col_index: int
    colspan: int = 1
    rowspan: int = 1
    is_merged: bool = False
    is_header: bool = False


@dataclass(frozen=True)
class GenericRow:
    cells: tuple[GenericCell, ...]
    row_index: int
    is_header: bool = False


@dataclass(frozen=True)
class GenericTable:
    rows: tuple[GenericRow, ...]
    table_index: int
    page_or_sheet: str | None = None
    row_count: int = 0
    col_count: int = 0
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.row_count == 0:
            object.__setattr__(self, "row_count", len(self.rows))
        if self.col_count == 0 and self.rows:
            object.__setattr__(
                self,
                "col_count",
                max((cell.col_index + cell.colspan for row in self.rows for cell in row.cells), default=0),
            )


@dataclass(frozen=True)
class GenericTextBlock:
    text: str
    block_index: int
    page_or_sheet: str | None = None
    block_type: str = "paragraph"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionLimits:
    max_pages: int = 50
    max_sheets: int = 50
    max_rows_per_table: int = 10_000
    max_cols_per_table: int = 100
    max_cell_length: int = 10_000
    max_decompressed_bytes: int = 100_000_000
    max_processing_seconds: float = 60.0
    min_text_length_for_scan: int = 100

    def enforce_cell_length(self, text: str) -> str:
        if len(text) > self.max_cell_length:
            return text[: self.max_cell_length]
        return text


@dataclass(frozen=True)
class ExtractionOutput:
    tables: tuple[GenericTable, ...] = ()
    text_blocks: tuple[GenericTextBlock, ...] = ()
    errors: tuple[ExtractorError, ...] = ()
    manual_review_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _now() -> float:
    return time.monotonic()


def check_timeout(start: float, limit: float) -> None:
    if _now() - start > limit:
        raise ExtractorError(
            "Processing time limit exceeded",
            stage="timeout",
            code="TIMEOUT_EXCEEDED",
        )
