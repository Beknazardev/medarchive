import pytest
from pydantic import ValidationError

from app.ingestion.contracts import SourceMode
from app.ingestion.registry import (
    EXPECTED_POLICY_SOURCE_IDS,
    SOURCE_REGISTRY,
    SourceExecutionBlockedError,
    SourceRegistry,
)


def test_registry_contains_every_policy_source():
    assert set(SOURCE_REGISTRY.source_ids) == EXPECTED_POLICY_SOURCE_IDS
    assert len(SOURCE_REGISTRY.source_ids) == len(EXPECTED_POLICY_SOURCE_IDS)


def test_registry_rejects_duplicate_source_ids():
    config = SOURCE_REGISTRY.get("kdl_olymp")

    with pytest.raises(ValueError, match="Duplicate source_id"):
        SourceRegistry((config, config))


@pytest.mark.parametrize(
    "source_id",
    [
        "invitro_kz",
        "invivo_kz",
        "103_kz",
        "helix_kz",
        "city_clinic_document",
        "2gis_enrichment",
        "google_places_enrichment",
    ],
)
def test_non_live_or_disabled_sources_cannot_execute_live(source_id):
    with pytest.raises(SourceExecutionBlockedError):
        SOURCE_REGISTRY.require_live(source_id)


def test_live_source_can_be_selected_without_importing_an_adapter():
    config = SOURCE_REGISTRY.require_live("kdl_olymp")

    assert config.mode is SourceMode.LIVE
    assert config.adapter_module is None


def test_map_enrichment_requires_official_api_and_is_disabled():
    for source_id in ("2gis_enrichment", "google_places_enrichment"):
        config = SOURCE_REGISTRY.get(source_id)
        assert config.mode is SourceMode.OFFICIAL_API_REQUIRED
        assert config.enabled is False
        assert config.formats == ("api",)


def test_registry_mapping_cannot_be_mutated():
    with pytest.raises(TypeError):
        SOURCE_REGISTRY.configs["new-source"] = SOURCE_REGISTRY.get("kdl_olymp")


def test_unknown_source_is_rejected():
    with pytest.raises(KeyError, match="Unknown source_id"):
        SOURCE_REGISTRY.get("user-provided-url")
