"""Source-agnostic document extractors for HTML, PDF, DOCX, XLSX, and plain text."""

from app.ingestion.extractors.base import (
    ExtractionLimits,
    ExtractorError,
    GenericCell,
    GenericRow,
    GenericTable,
    GenericTextBlock,
    ManualReviewRequired,
    UnsupportedFormat,
    MIMEMismatch,
    PasswordProtected,
    MalformedDocument,
    ZipBombDetected,
)

__all__ = [
    "ExtractionLimits",
    "ExtractorError",
    "GenericCell",
    "GenericRow",
    "GenericTable",
    "GenericTextBlock",
    "ManualReviewRequired",
    "UnsupportedFormat",
    "MIMEMismatch",
    "PasswordProtected",
    "MalformedDocument",
    "ZipBombDetected",
]
