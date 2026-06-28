"""HTML extractor - parses tables and text blocks from HTML using lxml."""

from __future__ import annotations

import time
from typing import Any

from lxml import etree, html

from app.ingestion.extractors.base import (
    ExtractionLimits,
    ExtractionOutput,
    GenericCell,
    GenericRow,
    GenericTable,
    GenericTextBlock,
    MalformedDocument,
    ManualReviewRequired,
    check_timeout,
)

MAX_HTML_BYTES = 50_000_000


def extract_html(
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

    if len(content) > MAX_HTML_BYTES:
        raise MalformedDocument(
            f"HTML content exceeds {MAX_HTML_BYTES} bytes",
            stage="html",
        )

    try:
        doc = html.fromstring(content)
    except etree.XMLSyntaxError as exc:
        raise MalformedDocument(
            f"Invalid HTML/XML: {exc}",
            stage="html",
        ) from exc

    table_index = 0
    for table_el in doc.xpath("//table"):
        check_timeout(start, lim.max_processing_seconds)
        rows = _extract_table(table_el, table_index, lim)
        if rows:
            tables.append(
                GenericTable(
                    rows=tuple(rows),
                    table_index=table_index,
                    page_or_sheet="html",
                    provenance={"source_url": source_url} if source_url else {},
                )
            )
            table_index += 1

    block_index = 0
    for p_el in doc.xpath("//p | //h1 | //h2 | //h3 | //h4 | //h5 | //h6"):
        check_timeout(start, lim.max_processing_seconds)
        text = _clean_text(p_el.text_content())
        if not text or len(text) < 5:
            continue
        truncated = lim.enforce_cell_length(text)
        tag = p_el.tag.lower()
        text_blocks.append(
            GenericTextBlock(
                text=truncated,
                block_index=block_index,
                page_or_sheet="html",
                block_type=tag,
                provenance={"source_url": source_url} if source_url else {},
            )
        )
        block_index += 1

    return ExtractionOutput(
        tables=tuple(tables),
        text_blocks=tuple(text_blocks),
        errors=tuple(errors),
        metadata={"table_count": len(tables), "text_block_count": len(text_blocks)},
    )


def _extract_table(
    table_el: Any,
    table_index: int,
    limits: ExtractionLimits,
) -> list[GenericRow]:
    rows: list[GenericRow] = []
    row_els = table_el.xpath(".//tr")
    if not row_els:
        return rows

    occupied: dict[tuple[int, int], bool] = {}
    row_index = 0

    for tr_el in row_els:
        check_timeout(time.monotonic(), limits.max_processing_seconds)
        if row_index >= limits.max_rows_per_table:
            break

        cells: list[GenericCell] = []
        col_index = 0

        for cell_el in tr_el.xpath(".//td | .//th"):
            while occupied.get((row_index, col_index), False):
                col_index += 1
            if col_index >= limits.max_cols_per_table:
                break

            colspan = int(cell_el.get("colspan", "1") or "1")
            rowspan = int(cell_el.get("rowspan", "1") or "1")
            is_header = cell_el.tag.lower() == "th"
            text = _clean_text(cell_el.text_content())
            truncated = limits.enforce_cell_length(text)

            for dr in range(rowspan):
                for dc in range(colspan):
                    occupied[(row_index + dr, col_index + dc)] = True

            cells.append(
                GenericCell(
                    text=truncated,
                    row_index=row_index,
                    col_index=col_index,
                    colspan=colspan,
                    rowspan=rowspan,
                    is_merged=colspan > 1 or rowspan > 1,
                    is_header=is_header,
                )
            )
            col_index += colspan

        if cells:
            rows.append(
                GenericRow(
                    cells=tuple(cells),
                    row_index=row_index,
                    is_header=any(c.is_header for c in cells),
                )
            )
        row_index += 1

    return rows


def _clean_text(text: str) -> str:
    import re
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned
