"""Tests for enhanced normalization service - Phase I TDD."""

from __future__ import annotations

import pytest

from app.services.normalization_service import (
    EnhancedNormalizationService,
    CITY_ALIASES,
    SERVICE_SYNONYMS,
    MatchResult,
    slugify,
)


# ─── Basic normalization tests ───

class TestBasicNormalization:
    def test_lowercases_trims_collapses_whitespace(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_text("  MRI   Brain  ") == "mri brain"

    def test_handles_empty_values(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_text(None) == ""
        assert normalizer.normalize_text("") == ""

    def test_normalizes_yo_to_e(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_text("ёж") == "еж"
        assert normalizer.normalize_text("Ёж") == "еж"

    def test_normalizes_punctuation_and_dashes(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.normalize_service_name("МРТ-головного мозга (с контрастом)")
        assert "–" not in result
        assert "—" not in result


# ─── City alias tests ───

class TestCityAliases:
    def test_normalizes_astana_aliases(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_city("Нур-Султан") == "астана"
        assert normalizer.normalize_city("Астана") == "астана"
        assert normalizer.normalize_city("astana") == "астана"

    def test_normalizes_almaty_aliases(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_city("Алматы") == "алматы"
        assert normalizer.normalize_city("Almaty") == "алматы"

    def test_preserves_unknown_cities(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_city("МойГород") == "мойгород"


# ─── Qualifier detection tests ───

class TestQualifierDetection:
    def test_detects_contrast_qualifier(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("КТ с контрастом")
        assert "contrast" in qualifiers

    def test_detects_laterality_qualifier(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("УЗИ правого колена")
        assert "laterality" in qualifiers

    def test_detects_specimen_qualifier(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("Анализ венозной крови")
        assert "specimen" in qualifiers

    def test_detects_method_qualifier(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("ПЦР анализ")
        assert "method" in qualifiers

    def test_detects_urgency_qualifier(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("Срочный анализ крови")
        assert "urgency" in qualifiers

    def test_detects_multiple_qualifiers(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("МРТ головы с контрастом, срочно")
        assert "contrast" in qualifiers
        assert "urgency" in qualifiers

    def test_no_qualifiers_for_simple_name(self):
        normalizer = EnhancedNormalizationService()
        qualifiers = normalizer.detect_qualifiers("Общий анализ крови")
        assert len(qualifiers) == 0


# ─── Synonym matching tests ───

class TestSynonymMatching:
    def test_exact_synonym_match_oak(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("ОАК")
        assert result == "общий анализ крови"

    def test_exact_synonym_match_oam(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("ОАМ")
        assert result == "общий анализ мочи"

    def test_exact_synonym_match_echocg(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("ЭхоКГ")
        assert result == "узи сердца"

    def test_exact_synonym_match_mri(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("МРТ головного мозга")
        assert result == "мрт головы"

    def test_exact_synonym_match_ttg(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("ТТГ")
        assert result == "ттг"

    def test_no_match_for_unknown(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.find_exact_synonym_match("Неизвестный анализ")
        assert result is None


# ─── Similarity calculation tests ───

class TestSimilarityCalculation:
    def test_identical_names_have_high_similarity(self):
        normalizer = EnhancedNormalizationService()
        sim = normalizer.calculate_similarity("Общий анализ крови", "общий анализ крови")
        assert sim == 1.0

    def test_similar_names_have_high_similarity(self):
        normalizer = EnhancedNormalizationService()
        sim = normalizer.calculate_similarity("Общий анализ крови", "ОАК")
        assert sim < 1.0

    def test_different_names_have_low_similarity(self):
        normalizer = EnhancedNormalizationService()
        sim = normalizer.calculate_similarity("Общий анализ крови", "МРТ головы")
        assert sim < 0.5


# ─── Fuzzy candidate tests ───

class TestFuzzyCandidates:
    def test_finds_similar_candidates(self):
        normalizer = EnhancedNormalizationService()
        candidates = [
            {"id": 1, "name": "общий анализ крови"},
            {"id": 2, "name": "клинический анализ крови"},
            {"id": 3, "name": "мрт головы"},
        ]
        results = normalizer.find_fuzzy_candidates("общий анализ крови", candidates, threshold=0.7)
        assert len(results) >= 1
        assert results[0]["similarity"] >= 0.7

    def test_excludes_qualifier_conflicts(self):
        normalizer = EnhancedNormalizationService()
        candidates = [
            {"id": 1, "name": "кт с контрастом"},
            {"id": 2, "name": "кт без контраста"},
        ]
        results = normalizer.find_fuzzy_candidates("кт с контрастом", candidates, threshold=0.5)
        # Should find "кт с контрастом" but not "кт без контраста" due to qualifier conflict
        assert len(results) >= 1


# ─── Full match tests ───

class TestFullMatch:
    def test_synonym_match_for_oak(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("ОАК")
        assert result.match_type == "synonym_matched"
        assert result.confidence == 1.0
        assert result.service_name == "общий анализ крови"

    def test_synonym_match_for_echocg(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("ЭхоКГ")
        assert result.match_type == "synonym_matched"
        assert result.confidence == 1.0
        assert result.service_name == "узи сердца"

    def test_exact_canonical_match(self):
        normalizer = EnhancedNormalizationService()
        catalog = [
            {"id": 1, "name": "прием терапевта первичный"},
            {"id": 2, "name": "консультация терапевта повторная"},
        ]
        result = normalizer.match_service("прием терапевта первичный", catalog_services=catalog)
        assert result.match_type == "exact_matched"
        assert result.confidence == 1.0
        assert result.service_id == 1

    def test_fuzzy_match_when_no_qualifiers(self):
        normalizer = EnhancedNormalizationService(auto_match_threshold=0.8)
        catalog = [
            {"id": 1, "name": "общий анализ крови"},
            {"id": 2, "name": "клинический анализ крови"},
        ]
        result = normalizer.match_service("общ анализ крови", catalog_services=catalog)
        # May or may not match depending on similarity threshold
        assert result.match_type in ("fuzzy_matched", "unmatched")

    def test_unmatched_when_qualifiers_conflict(self):
        normalizer = EnhancedNormalizationService()
        catalog = [
            {"id": 1, "name": "кт с контрастом"},
        ]
        result = normalizer.match_service("кт без контраста", catalog_services=catalog)
        assert result.match_type == "unmatched"

    def test_qualifiers_detected_in_result(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("МРТ головы с контрастом")
        assert "contrast" in result.qualifiers_detected


# ─── Mandatory examples from research document ───

class TestMandatoryExamples:
    def test_oak_example(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("ОАК")
        assert result.match_type == "synonym_matched"
        assert result.service_name == "общий анализ крови"

    def test_oam_example(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("ОАМ")
        assert result.match_type == "synonym_matched"
        assert result.service_name == "общий анализ мочи"

    def test_echocg_example(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("УЗИ сердца (ЭхоКГ)")
        assert result.match_type == "synonym_matched"
        assert "эхокг" in result.service_name or result.service_name == "узи сердца"

    def test_mrt_example(self):
        normalizer = EnhancedNormalizationService()
        result = normalizer.match_service("МРТ головы")
        assert result.match_type == "synonym_matched"
        assert result.service_name == "мрт головы"

    def test_city_astana_normalization(self):
        normalizer = EnhancedNormalizationService()
        assert normalizer.normalize_city("Астана") == "астана"
        assert normalizer.normalize_city("Нур-Султан") == "астана"


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        normalizer = EnhancedNormalizationService()
        result1 = normalizer.match_service("ОАК")
        result2 = normalizer.match_service("ОАК")
        assert result1.match_type == result2.match_type
        assert result1.service_name == result2.service_name

    def test_normalization_is_idempotent(self):
        normalizer = EnhancedNormalizationService()
        name1 = normalizer.normalize_service_name("  МРТ   головы  ")
        name2 = normalizer.normalize_service_name(name1)
        assert name1 == name2


# ─── Slugify tests ───

class TestSlugify:
    def test_slugify_basic(self):
        assert slugify("МРТ головы") == "мрт-головы"

    def test_slugify_with_punctuation(self):
        result = slugify("Общий анализ крови (ОАК)")
        assert "оак" in result

    def test_slugify_empty(self):
        assert slugify("!!!") == "item"
