from __future__ import annotations

import json
import re
from pathlib import Path

from backend.knowledge.paths import (
    get_knowledge_base_path,
    get_manual_favorites_path,
    get_processing_log_path,
)


def manual_favorites_path() -> Path:
    return get_manual_favorites_path()


def load_knowledge_base() -> dict:
    kb_path = get_knowledge_base_path()
    if not kb_path.exists():
        return {"items": [], "categories": []}

    with open(kb_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_knowledge_base(kb: dict):
    kb_path = get_knowledge_base_path()
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)


def load_manual_favorites() -> dict:
    path = manual_favorites_path()
    if not path.exists():
        return {"favorites": []}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manual_favorites(data: dict):
    path = manual_favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_processing_log() -> dict:
    log_path = get_processing_log_path()
    if not log_path.exists():
        return {"files": {}}

    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_processing_log(log: dict):
    log_path = get_processing_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


_EXPLICIT_CATEGORY_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*category\s*:\s*(.+?)\s*$", re.IGNORECASE)
_GENERIC_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _has_meaningful_content(lines: list[str]) -> bool:
    return any(str(line).strip() for line in lines)


def _append_section(sections: list[dict], current_section: dict | None):
    if not current_section:
        return
    if not _has_meaningful_content(current_section.get("content", [])):
        return
    category = str(current_section.get("category", "")).strip() or "uncategorized"
    sections.append({"category": category, "content": current_section.get("content", [])})


def _split_paragraph_sections(content: str) -> list[dict]:
    lines = content.splitlines()
    paragraphs: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append(current)
            current = []

    if current:
        paragraphs.append(current)

    return [{"category": "uncategorized", "content": para} for para in paragraphs if _has_meaningful_content(para)]


def parse_markdown_sections(content: str) -> list:
    sections = []
    current_section = None
    if not content or not str(content).strip():
        return sections

    in_code_fence = False
    for line in content.splitlines():
        if _CODE_FENCE_RE.match(line):
            in_code_fence = not in_code_fence
            if current_section:
                current_section["content"].append(line)
            else:
                current_section = {"category": "uncategorized", "content": [line]}
            continue

        if not in_code_fence:
            explicit_match = _EXPLICIT_CATEGORY_HEADER_RE.match(line)
            if explicit_match:
                _append_section(sections, current_section)
                current_section = {
                    "category": explicit_match.group(1).strip() or "uncategorized",
                    "content": [],
                }
                continue

            heading_match = _GENERIC_HEADING_RE.match(line)
            if heading_match:
                _append_section(sections, current_section)
                current_section = {"category": "uncategorized", "content": [line]}
                continue

        if current_section:
            current_section["content"].append(line)
        elif line.strip():
            current_section = {"category": "uncategorized", "content": [line]}

    _append_section(sections, current_section)

    if sections:
        return sections

    # Free-form fallback: split into paragraph-level chunks so we can still parse loosely structured notes.
    paragraph_sections = _split_paragraph_sections(content)
    if paragraph_sections:
        return paragraph_sections

    # Last-resort single section for non-empty content.
    if str(content).strip():
        return [{"category": "uncategorized", "content": content.splitlines()}]

    return sections


def format_sections_for_llm(sections: list) -> str:
    formatted = []
    for idx, sec in enumerate(sections, start=1):
        formatted.append(f"## Section: {idx}")
        formatted.append(f"## Category: {sec['category']}")
        formatted.append("\n".join(sec["content"]))
        formatted.append("\n---\n")
    return "\n".join(formatted)


def extract_unique_categories(kb: dict) -> dict:
    categories = {}
    for item in kb["items"]:
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1
    return categories


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def increment_rule_usage_count(
    *,
    kb_item_id: str | None = None,
    rule_text: str | None = None,
    category: str | None = None,
    amount: int = 1,
) -> bool:
    if amount <= 0:
        return False

    kb = load_knowledge_base()
    items = kb.get("items", [])
    if not isinstance(items, list) or not items:
        return False

    target = None
    if kb_item_id:
        target = next((item for item in items if item.get("item_id") == kb_item_id), None)

    if target is None and rule_text:
        normalized_text = _normalize_text(rule_text)
        normalized_category = _normalize_text(category)
        exact_candidates = []
        loose_candidates = []
        for item in items:
            if item.get("type") != "rule":
                continue
            item_text = _normalize_text(item.get("content", ""))
            if item_text != normalized_text:
                continue
            if normalized_category and _normalize_text(item.get("category", "")) == normalized_category:
                exact_candidates.append(item)
            else:
                loose_candidates.append(item)
        if exact_candidates:
            target = exact_candidates[0]
        elif loose_candidates:
            target = loose_candidates[0]

    if target is None:
        return False

    current = int(target.get("usage_count", 0) or 0)
    target["usage_count"] = max(0, current + amount)
    save_knowledge_base(kb)
    return True
