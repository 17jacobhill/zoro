from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.plan_paths import get_plan_markdown_path
from backend.utils import get_project_root
from backend.visualization.paths import get_existing_plan_path, get_plan_path as get_session_plan_path
from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.plan_tracker import plan_to_markdown

REDUNDANT_PLAN_KEYS = {"has_plan", "structure_type"}


def get_plan_path(chat_id: str) -> Path:
    return get_session_plan_path(chat_id, get_project_root())


def _normalize_plan_items(items: list | None) -> list[dict]:
    normalized_items: list[dict] = []

    for item in items or []:
        if not isinstance(item, dict):
            continue

        next_item = dict(item)
        next_item["children"] = _normalize_plan_items(next_item.get("children"))

        if "rules" in next_item and not isinstance(next_item.get("rules"), list):
            next_item["rules"] = []
        if "inherited_rules" in next_item and not isinstance(next_item.get("inherited_rules"), list):
            next_item["inherited_rules"] = []
        if "conflicts" in next_item and not isinstance(next_item.get("conflicts"), list):
            next_item["conflicts"] = []

        normalized_items.append(next_item)

    return normalized_items


def normalize_plan_document(plan_data: dict | None) -> dict | None:
    if not isinstance(plan_data, dict):
        return plan_data

    normalized = json.loads(json.dumps(plan_data))

    plan_root = normalized.get("plan")
    if not isinstance(plan_root, dict):
        plan_root = {}

    if not isinstance(plan_root.get("items"), list):
        top_level_items = normalized.get("items")
        plan_root["items"] = top_level_items if isinstance(top_level_items, list) else []

    plan_root["items"] = _normalize_plan_items(plan_root.get("items"))

    cleaned = {
        key: value
        for key, value in normalized.items()
        if key not in REDUNDANT_PLAN_KEYS and key != "items"
    }
    cleaned["plan"] = plan_root
    return cleaned


def strip_transient_proof_fields(plan_data: dict | None) -> dict | None:
    if not isinstance(plan_data, dict):
        return plan_data

    normalized = normalize_plan_document(plan_data)
    if not isinstance(normalized, dict):
        return normalized

    def walk(items: list[dict]) -> None:
        for item in items or []:
            item.pop("step_verifications", None)
            item.pop("item_verifications", None)

            for rule in item.get("rules", []) or []:
                if isinstance(rule, dict):
                    rule.pop("verifications", None)

            cleaned_inherited = []
            for inherited in item.get("inherited_rules", []) or []:
                if not isinstance(inherited, dict):
                    continue
                next_entry = dict(inherited)
                next_entry.pop("verifications", None)
                rule = next_entry.get("rule")
                if isinstance(rule, dict):
                    next_rule = dict(rule)
                    next_rule.pop("verifications", None)
                    next_entry["rule"] = next_rule
                cleaned_inherited.append(next_entry)
            item["inherited_rules"] = cleaned_inherited

            walk(item.get("children", []) or [])

    walk(normalized.get("plan", {}).get("items", []) or [])
    return normalized


def load_plan_document(chat_id: str) -> Optional[dict]:
    plan_path = get_existing_plan_path(chat_id, get_project_root())
    if not plan_path.exists():
        return None

    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return strip_transient_proof_fields(data)


def refresh_plan_markdown(chat_id: str, plan_data: Optional[dict] = None) -> None:
    metadata = vm.get_visualization(chat_id)
    if not metadata:
        return

    if plan_data is None:
        plan_data = load_plan_document(chat_id)
        if not plan_data:
            return

    tracking = metadata.get("plan_tracking", {})
    chat_name = metadata.get("name", "Unnamed")
    markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)

    plan_md_path = get_plan_markdown_path(get_project_root())
    plan_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_md_path, "w", encoding="utf-8") as f:
        f.write(markdown)


def save_plan_document(chat_id: str, plan_data: dict) -> Path:
    plan_path = get_session_plan_path(chat_id, get_project_root())
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = strip_transient_proof_fields(plan_data) or {}

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)

    refresh_plan_markdown(chat_id, normalized)
    return plan_path
