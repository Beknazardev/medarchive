from __future__ import annotations

from typing import Any

from app.data.service_catalog_excel import load_official_service_catalog


def get_default_service_catalog() -> list[dict[str, Any]]:
    return load_official_service_catalog()
