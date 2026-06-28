"""Plain text extractor - handles UTF-8 text files and returns line-based text blocks."""

from __future__ import annotations

from app.ingestion.extractors.base import (
    ExtractionLimits,
    ExtractionOutput,
    GenericTextBlock,
    MIMEMismatch,
    check_timeout,
)


def extract_text(
    content: bytes,
    *,
    source_url: str | None = None,
    limits: ExtractionLimits | None = None,
) -> ExtractionOutput:
    lim = limits or ExtractionLimits()
    start = check_timeout.__code__.co_firstlineno  # just use a marker
    import time
    start_time = time.monotonic()

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MIMEMismatch(
            f"Cannot decode as UTF-8: {exc}",
            stage="text",
        ) from exc

    blocks: list[GenericTextBlock] = []
    block_index = 0
    for line in text.splitlines():
        check_timeout(start_time, lim.max_processing_seconds)
        stripped = line.strip()
        if not stripped:
            continue
        truncated = lim.enforce_cell_length(stripped)
        blocks.append(
            GenericTextBlock(
                text=truncated,
                block_index=block_index,
                page_or_sheet="text",
                block_type="line",
                provenance={"source_url": source_url} if source_url else {},
            )
        )
        block_index += 1

    return ExtractionOutput(
        text_blocks=tuple(blocks),
        metadata={"line_count": len(blocks)},
    )
