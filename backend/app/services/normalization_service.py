"""Enhanced normalization service with multilingual support and safe fuzzy matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


# Curated city aliases (any input → canonical lowercase Russian)
CITY_ALIASES: dict[str, str] = {
    # Астана
    "нур-султан": "астана",
    "нурсултан": "астана",
    "astana": "астана",
    "астана": "астана",
    # Алматы
    "almaty": "алматы",
    "almata": "алматы",
    "алматы": "алматы",
    # Шымкент
    "shymkent": "шымкент",
    "shimkent": "шымкент",
    "чимкент": "шымкент",
    "шымкент": "шымкент",
    # Караганда
    "karaganda": "караганда",
    "karagandy": "караганда",
    "караганда": "караганда",
    # Актобе
    "aktobe": "актобе",
    "aktubinsk": "актобе",
    "актобе": "актобе",
    # Павлодар
    "pavlodar": "павлодар",
    "павлодар": "павлодар",
    # Костанай
    "kostanay": "костанай",
    "kustanay": "костанай",
    "костанай": "костанай",
    # Уральск
    "uralsk": "уральск",
    "oral": "уральск",
    "уральск": "уральск",
    # Темиртау
    "temirtau": "темиртау",
    "темиртау": "темиртау",
    # Экибастуз
    "ekibastuz": "экibастуз",
    "экibastуз": "экibастуз",
    # Петропавловск
    "petropavlovsk": "петропавловск",
    "petropavl": "петропавловск",
    "петропавловск": "петропавловск",
    # Актау
    "aktau": "актау",
    "актау": "актау",
    # Туркестан
    "turkestan": "туркестан",
    "туркестан": "туркестан",
    # Тараз
    "taraz": "тараз",
    "jambyl": "тараз",
    "тараз": "тараз",
    # Семей
    "semey": "семей",
    "семей": "семей",
    # Усть-Каменогорск
    "ust-kamenogorsk": "уст-каменогорск",
    "uskamenogorsk": "уст-каменогорск",
    "уст-каменогорск": "уст-каменогорск",
    # Кызылорда
    "kyzylorda": "кызылорда",
    "кызылорда": "кызылорда",
    # Талдыкорган
    "taldykorgan": "талдыкорган",
    "талдыкорган": "талдыкорган",
    # Жезказган
    "zhezkazgan": "жезказган",
    "жезказган": "жезказган",
    # Экибастуз (alternate)
    "ekibastuz": "экibастуз",
    # Балхаш
    "balqash": "балхаш",
    "балхаш": "балхаш",
    # Кокшетау
    "kokshetau": "кокшетау",
    "кокшетау": "кокшетау",
    # ТУРКЕСТАН (область)
    "turkestan region": "туркестан",
}


# Curated service abbreviations and synonyms (RU/KZ/EN)
SERVICE_SYNONYMS: dict[str, list[str]] = {
    # ОАК / CBC
    "общий анализ крови": ["оак", "cbc", "клинический анализ крови", "общий клинический анализ крови"],
    # ОАМ / Urinalysis
    "общий анализ мочи": ["оам", "urinalysis", "общий клинический анализ мочи"],
    # ЭхоКГ / Echocardiography
    "узи сердца": ["эхокг", "echocg", "echocardiography", "узи сердца (эхокг)"],
    # МРТ / MRI
    "мрт головы": ["мрт головного мозга", "mri brain", "mrt головного мозга", "магнитно-резонансная томография головного мозга"],
    # КТ / CT
    "компьютерная томография": ["кт", "ct", "кэ-тэ"],
    "кт головного мозга": ["кт головы", "ct brain"],
    "кт органов грудной клетки": ["кт огк", "ct chest", "кт грудной клетки"],
    # УЗИ / Ultrasound
    "ультразвуковое исследование": ["узи", "ultrasound", "уси"],
    "узи органов брюшной полости": ["узи брюшной полости", "ultrasound abdomen", "узи оebp"],
    "узи почек": ["ультразвуковое исследование почек", "ultrasound kidneys"],
    "узи щитовидной железы": ["узи щитовидки", "ultrasound thyroid"],
    # ЭКГ / ECG
    "электрокардиография": ["экг", "ecg", "экс"],
    "экг": ["электрокардиография", "ecg"],
    # Анализы крови
    "холестерин общий": ["холестерин", "cholesterol", "холестерин крови"],
    "глюкоза": ["глюкоза крови", "glucose", "сахар крови"],
    "креатинин": ["creatinine", "креатинин крови"],
    "мочевина": ["urea", "мочевина крови"],
    "билирубин общий": ["билирубин", "bilirubin", "билирубин крови"],
    "алт": ["аланинаминотрансфераза", "alt", "алат"],
    "аст": ["аспартатаминотрансфераза", "ast", "асат"],
    "ттг": ["тиреотропный гормон", "tsh", "тиреотропин"],
    "т3 свободный": ["трийодтиронин свободный", "free t3", "т3св"],
    "т4 свободный": ["тироксин свободный", "free t4", "т4св"],
    "ферритин": ["ferritin"],
    "витамин д": ["vitamin d", "25-oh vitamin d", "кальцидиол"],
    "с-реактивный белок": ["срб", "crp", "c-reactive protein", "с-reactive белок"],
    # Коагулограмма
    "коагулограмма": ["коагулограмма крови", "коагулограмма", "коагул"],
    # Микробиология
    "посев": ["бак посев", "bacterial culture", "microbiology"],
    # Консультации
    "консультация терапевта": ["прием терапевта", "терапевт", "терапия"],
    "консультация хирурга": ["прием хирурга", "хирург", "хирургия"],
    "консультация кардиолога": ["прием кардиолога", "кардиолог", "кардиология"],
    "консультация невролога": ["прием невролога", "невролог", "невропатолог", "неврология"],
    "консультация гинеколога": ["прием гинеколога", "гинеколог", "гинекология"],
    "консультация уролога": ["прием уролога", "уролог", "урология"],
    "консультация эндокринолога": ["прием эндокринолога", "эндокринолог", "эндокринология"],
    "консультация гастроэнтеролога": ["прием гастроэнтеролога", "гастроэнтеролог", "гастроэнтерология"],
    "консультация дерматолога": ["прием дерматолога", "дерматолог", "дерматология"],
    "консультация офтальмолога": ["прием офтальмолога", "офтальмолог", "офтальмология", "консультация глазного врача"],
    "консультация отоларинголога": ["прием лора", "лор", "отоларинголог", "otorhinolaryngology"],
    "консультация стоматолога": ["прием стоматолога", "стоматолог", "стоматология", "dentist"],
    "консультация педиатра": ["прием педиатра", "педиатр", "pediatrics"],
    "консультация аллерголога": ["прием аллерголога", "аллерголог", "аллергология"],
    "консультация онколога": ["прием онколога", "онколог", "онкология"],
    "консультация психиатра": ["прием психиатра", "психиатр", "психиатрия"],
    "консультация невропатолога": ["прием невропатолога", "невропатолог"],
    # Процедуры
    "внутримышечная инъекция": ["в/м инъекция", "внутримышечно", "im injection"],
    "внутривенная инъекция": ["в/в инъекция", "внутривенно", "iv injection"],
    "капельница": ["внутривенное вливание", "infusion", "drop"],
    "перевязка": ["bandage", "перевязка раны"],
    "снятие швов": ["remove stitches", "снятие швов"],
    # Визуализация
    "рентген": ["рентгенография", "x-ray", "рентген снимок"],
    "рентген грудной клетки": ["рентген огк", "x-ray chest", "рентген легких"],
    "флюорография": ["фг", "fluorography", "флюорографический снимок"],
    # Функциональная диагностика
    "суточное мониторирование артериального давления": ["суточное мониторирование ад", "смад", "holter bp"],
    "суточное мониторирование электрокардиограммы": ["суточное мониторирование экг", "holter ecg", "холтер"],
    "эхокардиография": ["эхокг", "echo", "узи сердца"],
    # Стоматология
    "профессиональная чистка зубов": ["профчистка", "professional cleaning", "ультразвуковая чистка"],
    "лечение кариеса": ["кариес", "caries treatment", "пломба"],
    "протезирование": ["prosthetics", "протез зуба"],
    "имплантация": ["implantation", "имплант", "dental implant"],
    # Хирургия
    "удаление аппендицита": ["аппендэктомия", "appendectomy"],
    "удаление желчного пузыря": ["холецистэктомия", "cholecystectomy"],
    "грыжесечение": ["герниопластика", "hernia repair"],
}


# Qualifiers that indicate clinical differences
QUALIFIER_PATTERNS = {
    "contrast": ["с контрастом", "с контрастированием", "с контрастным веществом", "with contrast", "контраст"],
    "laterality": ["правый", "левый", "правая", "левая", "правого", "левого", "right", "left", "оба", "both"],
    "specimen": ["венозная кровь", "капиллярная кровь", "вен", "кап", "venous", "capillary", "моча", "кала", "мазок"],
    "method": ["пцр", "pcr", "посев", "culture", "иммуноферментный", "ифа", "elisa", "хемилюминесцентный"],
    "age": ["детский", "взрослый", "child", "adult", "pediatric"],
    "urgency": ["срочно", "срочный", "экстренно", "urgent", "cito", "быстрый"],
    "body_part": ["головы", "грудной клетки", "брюшной полости", "позвоночника", "сустава", "конечности", "organs"],
    "package": ["комплекс", "панель", "package", "panel", "чек-ап", "check-up", "скрининг", "screening"],
}


@dataclass(frozen=True)
class NormalizationResult:
    """Result of normalizing a service name."""

    raw: str
    normalized: str
    canonical: str


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a service name to the catalog."""

    service_id: int | None = None
    service_name: str | None = None
    match_type: str = "unmatched"
    confidence: float = 0.0
    qualifiers_detected: tuple[str, ...] = ()
    raw_input: str = ""


class EnhancedNormalizationService:
    """Enhanced normalization service with multilingual support and safe fuzzy matching."""

    def __init__(self, auto_match_threshold: float = 0.95) -> None:
        self.auto_match_threshold = auto_match_threshold
        self._synonym_index: dict[str, str] = {}
        self._build_synonym_index()

    def _build_synonym_index(self) -> None:
        """Build reverse index from synonym to canonical name."""
        for canonical, synonyms in SERVICE_SYNONYMS.items():
            normalized_canonical = self.normalize_service_name(canonical)
            # Map canonical name to itself
            self._synonym_index[normalized_canonical] = normalized_canonical
            # Map each synonym to the canonical name
            for synonym in synonyms:
                normalized_synonym = self.normalize_service_name(synonym)
                if normalized_synonym not in self._synonym_index:
                    self._synonym_index[normalized_synonym] = normalized_canonical

    def normalize_text(self, value: str | None) -> str:
        """Basic text normalization: lowercase, trim, collapse whitespace, ё -> е."""
        if not value:
            return ""
        normalized = value.lower().strip()
        normalized = normalized.replace("ё", "е").replace("Ё", "Е")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def normalize_service_name(self, name: str) -> str:
        """Enhanced service name normalization with punctuation and dash handling."""
        normalized = self.normalize_text(name)

        # Normalize punctuation and dashes
        normalized = re.sub(r"[–—]", "-", normalized)
        normalized = re.sub(r"[^\w\s\-/()]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Common replacements
        replacements = {
            "приём": "прием",
            "магнитно резонансная": "магнитно-резонансная",
            "компьютерная томография": "кт",
            "ультразвуковое исследование": "узи",
            "электрокардиография": "экг",
            "рентгенография": "рентген",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)

        return normalized.strip()

    def normalize_city(self, city: str | None) -> str:
        """Normalize city name using aliases."""
        if not city:
            return ""
        normalized = self.normalize_text(city)
        return CITY_ALIASES.get(normalized, normalized)

    def resolve_city(self, raw_city: str | None) -> str | None:
        """Resolve user input to canonical Russian city name.

        Returns the canonical lowercase Russian city name or None if not recognized.
        Supports: Russian, English, Kazakh inputs.
        """
        if not raw_city or not raw_city.strip():
            return None
        normalized = self.normalize_text(raw_city.strip())
        if not normalized:
            return None
        # Direct alias lookup
        resolved = CITY_ALIASES.get(normalized)
        if resolved:
            return resolved
        # Try to find by partial match (e.g. "астан" → "астана")
        for alias, canonical in CITY_ALIASES.items():
            if normalized in alias or alias in normalized:
                return canonical
        return None

    def detect_qualifiers(self, name: str) -> tuple[str, ...]:
        """Detect clinical qualifiers in service name."""
        normalized = self.normalize_text(name)
        detected: list[str] = []
        for qualifier, patterns in QUALIFIER_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    detected.append(qualifier)
                    break
        return tuple(sorted(set(detected)))

    def find_exact_synonym_match(self, name: str) -> str | None:
        """Find exact synonym match and return canonical name."""
        normalized = self.normalize_service_name(name)
        return self._synonym_index.get(normalized)

    def calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two normalized names."""
        n1 = self.normalize_service_name(name1)
        n2 = self.normalize_service_name(name2)
        return SequenceMatcher(None, n1, n2).ratio()

    def find_fuzzy_candidates(
        self,
        name: str,
        candidates: list[dict[str, Any]],
        threshold: float | None = None,
        max_candidates: int = 5,
    ) -> list[dict[str, Any]]:
        """Find fuzzy matching candidates above threshold."""
        if threshold is None:
            threshold = self.auto_match_threshold

        normalized_name = self.normalize_service_name(name)
        name_qualifiers = self.detect_qualifiers(name)

        scored_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            candidate_name = candidate.get("name", "")
            candidate_qualifiers = self.detect_qualifiers(candidate_name)

            # Check for qualifier conflicts
            if name_qualifiers and candidate_qualifiers:
                if name_qualifiers != candidate_qualifiers:
                    continue

            similarity = self.calculate_similarity(name, candidate_name)
            if similarity >= threshold:
                scored_candidates.append(
                    {
                        **candidate,
                        "similarity": similarity,
                        "qualifiers": candidate_qualifiers,
                    }
                )

        scored_candidates.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_candidates[:max_candidates]

    def match_service(
        self,
        name: str,
        category: str | None = None,
        catalog_services: list[dict[str, Any]] | None = None,
    ) -> MatchResult:
        """Match a service name against the catalog with multiple strategies."""
        qualifiers = self.detect_qualifiers(name)

        # Strategy 1: Exact synonym match
        canonical = self.find_exact_synonym_match(name)
        if canonical:
            return MatchResult(
                service_name=canonical,
                match_type="synonym_matched",
                confidence=1.0,
                qualifiers_detected=qualifiers,
                raw_input=name,
            )

        # Strategy 2: Exact canonical match (already normalized)
        normalized = self.normalize_service_name(name)
        if catalog_services:
            for service in catalog_services:
                service_name = service.get("name", "")
                if self.normalize_service_name(service_name) == normalized:
                    return MatchResult(
                        service_id=service.get("id"),
                        service_name=service_name,
                        match_type="exact_matched",
                        confidence=1.0,
                        qualifiers_detected=qualifiers,
                        raw_input=name,
                    )

        # Strategy 3: Fuzzy matching (only if no qualifiers conflict)
        if catalog_services and not qualifiers:
            candidates = self.find_fuzzy_candidates(
                name,
                catalog_services,
                threshold=self.auto_match_threshold,
            )
            if candidates:
                best = candidates[0]
                return MatchResult(
                    service_id=best.get("id"),
                    service_name=best.get("name"),
                    match_type="fuzzy_matched",
                    confidence=best["similarity"],
                    qualifiers_detected=qualifiers,
                    raw_input=name,
                )

        return MatchResult(
            match_type="unmatched",
            confidence=0.0,
            qualifiers_detected=qualifiers,
            raw_input=name,
        )

    def slugify(self, value: str) -> str:
        """Create ASCII slug from text."""
        return slugify(value)


def slugify(value: str) -> str:
    """Create ASCII slug from text."""
    normalized = value.lower().strip()
    normalized = normalized.replace("ё", "е")
    ascii_value = unicodedata.normalize("NFKD", normalized)
    ascii_value = "".join(ch for ch in ascii_value if not unicodedata.combining(ch))
    ascii_value = re.sub(r"[^a-z0-9а-я]+", "-", ascii_value)
    return ascii_value.strip("-") or "item"


# Backward compatibility alias
NormalizationService = EnhancedNormalizationService
