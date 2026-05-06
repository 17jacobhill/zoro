from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.utils import get_project_root
from backend.visualization.paths import get_existing_runtime_path, get_runtime_path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _default_runtime(now_iso: str | None = None) -> dict:
    timestamp = now_iso or _now_iso()
    return {
        "token_count": 0,
        "last_message_index": 0,
        "accumulated_content": "",
        "cleaned_accumulated_content": "",
        "supervision_cleaned_accumulated_content": "",
        "last_analyzed_token_index": 0,
        "last_supervised_token_index": 0,
        "total_clean_tokens": 0,
        "total_supervision_clean_tokens": 0,
        "latest_rule_learning": {
            "rules": [],
            "analyzed_tokens": 0,
            "analyzed_from_token": 0,
            "analyzed_to_token": 0,
            "remaining_tokens": 0,
            "all_analyzed": False,
            "updated_at": timestamp,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def load_runtime_document(chat_id: str, base: Path | None = None) -> dict:
    root = base or get_project_root()
    path = get_existing_runtime_path(chat_id, root)
    now_iso = _now_iso()
    defaults = _default_runtime(now_iso)

    if not path.exists():
        return defaults

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return defaults

    runtime = dict(defaults)
    if isinstance(data, dict):
        runtime.update(data)

    learning = runtime.get("latest_rule_learning")
    if not isinstance(learning, dict):
        runtime["latest_rule_learning"] = dict(defaults["latest_rule_learning"])
    else:
        normalized_learning = dict(defaults["latest_rule_learning"])
        normalized_learning.update(learning)
        rules = normalized_learning.get("rules")
        normalized_learning["rules"] = rules if isinstance(rules, list) else []
        runtime["latest_rule_learning"] = normalized_learning

    runtime["created_at"] = runtime.get("created_at") or now_iso
    runtime["updated_at"] = runtime.get("updated_at") or runtime["created_at"]
    return runtime


def save_runtime_document(chat_id: str, runtime_doc: dict, base: Path | None = None) -> Path:
    root = base or get_project_root()
    path = get_runtime_path(chat_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = _now_iso()
    payload = _default_runtime(now_iso)
    payload.update(dict(runtime_doc or {}))

    learning = payload.get("latest_rule_learning")
    normalized_learning = dict(_default_runtime(now_iso)["latest_rule_learning"])
    if isinstance(learning, dict):
        normalized_learning.update(learning)
    normalized_learning["rules"] = (
        normalized_learning.get("rules")
        if isinstance(normalized_learning.get("rules"), list)
        else []
    )
    payload["latest_rule_learning"] = normalized_learning
    payload["created_at"] = payload.get("created_at") or now_iso
    payload["updated_at"] = now_iso

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return path
