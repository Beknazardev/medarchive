"""PDF extractor - uses pdfplumber for tables and PyMuPDF for text/metadata/scanned detection."""

from __future__ import annotations

import time
from typing import Any

import pdfplumber

from app.ingestion.extractors.base import (
    ExtractionLimits,
    ExtractionOutput,
    GenericCell,
    GenericRow,
    GenericTable,
    GenericTextBlock,
    MalformedDocument,
    ManualReviewRequired,
    PasswordProtected,
    UnsupportedFormat,
    check_timeout,
)

MIN_CHARS_FOR_TEXT_PDF = 50
SCANNED_TEXT_THRESHOLD = 200


def extract_pdf(
    content: bytes,
    *,
    source_url: str | None = None,
    limits: ExtractionLimits | None = None,
) -> ExtractionOutput:
    lim = limits or ExtractionLimits()
    start = time.monotonic()
    errors: list[Any] = []
    tables: list[GenericTable] = []
    text_blocks: list[GenericTextBlock] = []
    manual_review = False

    if len(content) < 100:
        raise MalformedDocument("PDF content too small", stage="pdf")

    try:
        _check_with_pymupdf(content, lim)
    except PasswordProtected:
        raise
    except Exception:
        pass

    from io import BytesIO
    try:
        pdf = pdfplumber.open(BytesIO(content))
    except Exception as exc:
        raise MalformedDocument(f"Cannot open PDF: {exc}", stage="pdf") from exc

    try:
        total_text = ""
        table_index = 0

        for page_idx, page in enumerate(pdf.pages):
            check_timeout(start, lim.max_processing_seconds)
            if page_idx >= lim.max_pages:
                errors.append(
                    ManualReviewRequired(
                        f"Page limit {lim.max_pages} reached; remaining pages skipped",
                        stage="pdf",
                    )
                )
                break

            page_label = f"page_{page_idx + 1}"

            page_tables = page.extract_tables()
            if page_tables:
                for tbl in page_tables:
                    if not tbl:
                        continue
                    rows = _build_rows(tbl, table_index, page_label, lim)
                    if rows:
                        tables.append(
                            GenericTable(
                                rows=tuple(rows),
                                table_index=table_index,
                                page_or_sheet=page_label,
                                provenance={
                                    "source_url": source_url,
                                    "page_index": page_idx,
                                }
                                if source_url
                                else {"page_index": page_idx},
                            )
                        )
                        table_index += 1

            page_text = page.extract_text() or ""
            total_text += page_text

            if page_text.strip():
                for para in page_text.split("\n"):
                    stripped = para.strip()
                    if not stripped or len(stripped) < 5:
                        continue
                    truncated = lim.enforce_cell_length(stripped)
                    text_blocks.append(
                        GenericTextBlock(
                            text=truncated,
                            block_index=len(text_blocks),
                            page_or_sheet=page_label,
                            block_type="paragraph",
                            provenance={"page_index": page_idx},
                        )
                    )
    finally:
        pdf.close()

    if len(total_text.strip()) < MIN_CHARS_FOR_TEXT_PDF and not tables:
        manual_review = True
        errors.append(
            ManualReviewRequired(
                "PDF has very little text content and no tables; likely scanned",
                stage="pdf",
            )
        )

    return ExtractionOutput(
        tables=tuple(tables),
        text_blocks=tuple(text_blocks),
        errors=tuple(errors),
        manual_review_required=manual_review,
        metadata={
            "table_count": len(tables),
            "text_block_count": len(text_blocks),
            "total_text_length": len(total_text),
        },
    )


def _check_with_pymupdf(content: bytes, limits: ExtractionLimits) -> None:
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            if doc.is_encrypted:
                try:
                    if not doc.authenticate(""):
                        raise PasswordProtected(
                            "PDF is password-protected",
                            stage="pdf",
                        )
                except Exception:
                    raise PasswordProtected(
                        "PDF is password-protected",
                        stage="pdf",
                    )
        finally:
            doc.close()
    except PasswordProtected:
        raise
    except Exception:
        pass


def _build_rows(
    raw_rows: list[list[str | None]],
    table_index: int,
    page_label: str,
    limits: ExtractionLimits,
) -> list[GenericRow]:
    rows: list[GenericRow] = []
    for row_idx, raw_row in enumerate(raw_rows):
        if row_idx >= limits.max_rows_per_table:
            break
        cells: list[GenericCell] = []
        for col_idx, cell_text in enumerate(raw_row):
            if col_idx >= limits.max_cols_per_table:
                break
            text = (cell_text or "").strip()
            truncated = limits.enforce_cell_length(text)
            cells.append(
                GenericCell(
                    text=truncated,
                    row_index=row_idx,
                    col_index=col_idx,
                    is_header=(row_idx == 0),
                )
            )
        if cells:
            rows.append(
                GenericRow(
                    cells=tuple(cells),
                    row_index=row_idx,
                    is_header=(row_idx == 0),
                )
            )
    return rows
