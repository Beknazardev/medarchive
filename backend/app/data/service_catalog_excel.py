from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile


DEFAULT_SERVICE_CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "service_catalog.xlsx"
)
OFFICIAL_SERVICE_CATALOG_SHEET = "Справочник услуг"
CATEGORY_COLUMN = "Специальность"
NAME_COLUMN = "Name_ru"

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def load_official_service_catalog(
    path: Path | str = DEFAULT_SERVICE_CATALOG_PATH,
) -> list[dict[str, Any]]:
    workbook_path = Path(path)
    rows = _read_sheet_rows(workbook_path, OFFICIAL_SERVICE_CATALOG_SHEET)
    if not rows:
        return []

    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    try:
        category_index = headers.index(CATEGORY_COLUMN)
        name_index = headers.index(NAME_COLUMN)
    except ValueError as exc:
        raise ValueError(
            f"Service catalog must contain {CATEGORY_COLUMN!r} and {NAME_COLUMN!r} columns"
        ) from exc

    catalog: list[dict[str, Any]] = []
    for row in rows[1:]:
        category = _cell_text(row, category_index)
        name = _cell_text(row, name_index)
        if not category and not name:
            continue
        if not category or not name:
            continue
        if category.startswith("#") or name.startswith("#"):
            continue
        catalog.append({"category": category, "name": name, "aliases": []})
    return catalog


def _read_sheet_rows(path: Path, sheet_name: str) -> list[list[Any]]:
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _resolve_sheet_path(archive, sheet_name)
        root = ElementTree.fromstring(archive.read(sheet_path))

    rows: list[list[Any]] = []
    for row_element in root.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
        values: list[Any] = []
        for cell in row_element.findall(f"{{{_MAIN_NS}}}c"):
            column_index = _column_index(cell.attrib.get("r", ""))
            while len(values) <= column_index:
                values.append(None)
            values[column_index] = _cell_value(cell, shared_strings)
        rows.append(values)
    return rows


def _read_shared_strings(archive: ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ElementTree.fromstring(xml)
    strings: list[str] = []
    for item in root.findall(f"{{{_MAIN_NS}}}si"):
        parts = [text.text or "" for text in item.findall(f".//{{{_MAIN_NS}}}t")]
        strings.append("".join(parts))
    return strings


def _resolve_sheet_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{_PACKAGE_REL_NS}}}Relationship")
    }

    fallback_relationship_id: str | None = None
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        relationship_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
        if fallback_relationship_id is None:
            fallback_relationship_id = relationship_id
        if sheet.attrib.get("name") == sheet_name and relationship_id:
            return _workbook_target_to_path(relationship_targets[relationship_id])

    if fallback_relationship_id:
        return _workbook_target_to_path(relationship_targets[fallback_relationship_id])
    raise ValueError("Service catalog workbook has no sheets")


def _workbook_target_to_path(target: str) -> str:
    normalized = target.lstrip("/")
    if normalized.startswith("xl/"):
        return normalized
    return f"xl/{normalized}"


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text.text or "" for text in cell.findall(f".//{{{_MAIN_NS}}}t")
        )

    value = cell.find(f"{{{_MAIN_NS}}}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        return shared_strings[int(value.text)]
    return value.text


def _column_index(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - ord("A") + 1)
    return max(index - 1, 0)


def _cell_text(row: list[Any], index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()
