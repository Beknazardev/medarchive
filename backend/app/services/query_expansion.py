from __future__ import annotations

from app.services.normalization_service import NormalizationService


SERVICE_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("pcr", "пцр", "птр", "polymerase chain reaction"),
    (
        "ultrasound",
        "ultrasonography",
        "sonography",
        "узи",
        "удз",
        "ультразвук",
        "ультразвуковое исследование",
    ),
    ("mri", "мрт", "magnetic resonance imaging", "магнитно-резонансная томография"),
    ("ct", "кт", "computed tomography", "компьютерная томография"),
    (
        "blood test",
        "анализ крови",
        "қан талдауы",
        "общий анализ крови",
        "жалпы қан талдауы",
        "cbc",
    ),
    (
        "therapist",
        "physician",
        "gp",
        "терапевт",
        "прием терапевта",
        "консультация терапевта",
        "терапевт қабылдауы",
        "дәрігер қабылдауы",
    ),
    ("ecg", "ekg", "экг", "электрокардиограмма"),
    ("x-ray", "xray", "radiography", "рентген"),
)


def expand_service_query(
    query: str,
    normalizer: NormalizationService,
) -> tuple[str, ...]:
    normalized_query = normalizer.normalize_service_name(query)
    for group in SERVICE_ALIAS_GROUPS:
        normalized_group = tuple(
            dict.fromkeys(normalizer.normalize_service_name(alias) for alias in group)
        )
        if normalized_query in normalized_group:
            return normalized_group
    return (normalized_query,)
