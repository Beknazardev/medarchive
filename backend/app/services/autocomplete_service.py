"""Autocomplete service for canonical names and approved synonyms."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import NormalizedService, ServiceCategory, UnmatchedServiceRecord
from app.services.normalization_service import EnhancedNormalizationService


class AutocompleteItem(BaseModel):
    """Single autocomplete suggestion."""

    text: str
    type: str  # "canonical", "synonym", "unmatched"
    category: str | None = None
    confidence: float = 0.0
    occurrence_count: int = 0


class AutocompleteResponse(BaseModel):
    """Autocomplete search response."""

    suggestions: list[AutocompleteItem]
    query: str


class AutocompleteService:
    """Service for autocomplete suggestions from canonical names and synonyms."""

    def __init__(self, db: Session, normalizer: EnhancedNormalizationService | None = None) -> None:
        self.db = db
        self.normalizer = normalizer or EnhancedNormalizationService()

    def autocomplete(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions for a query."""
        if not query or len(query.strip()) < 2:
            return AutocompleteResponse(suggestions=[], query=query)

        normalized_query = self.normalizer.normalize_text(query.strip())
        suggestions: list[AutocompleteItem] = []

        canonical_matches = self._find_canonical_matches(normalized_query, limit)
        suggestions.extend(canonical_matches)

        synonym_matches = self._find_synonym_matches(normalized_query, limit - len(suggestions))
        suggestions.extend(synonym_matches)

        unmatched_matches = self._find_unmatched_matches(normalized_query, limit - len(suggestions))
        suggestions.extend(unmatched_matches)

        seen = set()
        unique_suggestions: list[AutocompleteItem] = []
        for item in suggestions:
            if item.text not in seen:
                seen.add(item.text)
                unique_suggestions.append(item)

        return AutocompleteResponse(
            suggestions=unique_suggestions[:limit],
            query=query,
        )

    def _find_canonical_matches(
        self,
        normalized_query: str,
        limit: int,
    ) -> list[AutocompleteItem]:
        """Find canonical service name matches."""
        query = (
            select(NormalizedService, ServiceCategory)
            .join(ServiceCategory, ServiceCategory.id == NormalizedService.category_id)
            .where(
                func.lower(NormalizedService.name).like(f"%{normalized_query}%")
            )
            .limit(limit)
        )

        results = self.db.execute(query).all()
        return [
            AutocompleteItem(
                text=service.name,
                type="canonical",
                category=category.name,
                confidence=1.0,
            )
            for service, category in results
        ]

    def _find_synonym_matches(
        self,
        normalized_query: str,
        limit: int,
    ) -> list[AutocompleteItem]:
        """Find synonym matches from the synonym index."""
        suggestions: list[AutocompleteItem] = []

        for canonical, synonyms in self.normalizer._synonym_index.items():
            if normalized_query in canonical or any(normalized_query in s for s in synonyms):
                suggestions.append(
                    AutocompleteItem(
                        text=canonical,
                        type="synonym",
                        confidence=0.9,
                    )
                )
                if len(suggestions) >= limit:
                    break

        return suggestions

    def _find_unmatched_matches(
        self,
        normalized_query: str,
        limit: int,
    ) -> list[AutocompleteItem]:
        """Find unmatched service record matches."""
        query = (
            select(UnmatchedServiceRecord)
            .where(
                func.lower(UnmatchedServiceRecord.normalized_raw_name).like(f"%{normalized_query}%"),
                UnmatchedServiceRecord.status == "open",
            )
            .order_by(UnmatchedServiceRecord.occurrence_count.desc())
            .limit(limit)
        )

        results = self.db.scalars(query).all()
        return [
            AutocompleteItem(
                text=record.raw_name,
                type="unmatched",
                category=record.raw_category,
                confidence=0.5,
                occurrence_count=record.occurrence_count,
            )
            for record in results
        ]
