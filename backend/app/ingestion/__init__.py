"""Policy-gated, source-independent ingestion contracts."""

from app.ingestion.contracts import (
    ExtractionError,
    ExtractionResult,
    IngestionRunResult,
    ParserStage,
    PriceQualifier,
    RawServiceCandidate,
    RunStatus,
    SourceConfig,
    SourceDocument,
    SourceFormat,
    SourceMode,
    SourcePolicyMetadata,
    contract_schema_fingerprint,
)

__all__ = [
    "ExtractionError",
    "ExtractionResult",
    "IngestionRunResult",
    "ParserStage",
    "PriceQualifier",
    "RawServiceCandidate",
    "RunStatus",
    "SourceConfig",
    "SourceDocument",
    "SourceFormat",
    "SourceMode",
    "SourcePolicyMetadata",
    "contract_schema_fingerprint",
]
