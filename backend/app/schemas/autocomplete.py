"""Schemas for autocomplete API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AutocompleteItem(BaseModel):
    """Single autocomplete suggestion."""

    text: str
    type: str
    category: str | None = None
    confidence: float = 0.0
    occurrence_count: int = 0


class AutocompleteResponse(BaseModel):
    """Autocomplete search response."""

    suggestions: list[AutocompleteItem]
    query: str
