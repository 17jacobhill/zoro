"""Path helpers for per-visualization artifacts.

Each chat visualization gets a session directory under:
`.zoro/visualization/<chat_id>/`

This module centralizes file paths for session-scoped JSON documents:
- `session.json`, `runtime.json`, `plan.json`, `notes.json`, `evidence.json`,
  `monitoring.json`, and visualization `index.json`.

The project-level shared markdown path (`.zoro/CURRENT_PLAN.md`) is handled by:
- `backend/plan_paths.py`
"""

from __future__ import annotations

from pathlib import Path

from backend.utils import get_project_root


PRIMARY_VISUALIZATION_DIR = Path(".zoro") / "visualization"


def _root(base: Path | None = None) -> Path:
    return base or get_project_root()


def get_visualization_root(base: Path | None = None) -> Path:
    return _root(base) / PRIMARY_VISUALIZATION_DIR


def get_visualization_index_path(base: Path | None = None) -> Path:
    return get_visualization_root(base) / "index.json"


def get_existing_visualization_index_path(base: Path | None = None) -> Path:
    return get_visualization_index_path(base)


def get_session_dir(chat_id: str, base: Path | None = None) -> Path:
    return get_visualization_root(base) / chat_id


def get_session_file_path(chat_id: str, filename: str, base: Path | None = None) -> Path:
    return get_session_dir(chat_id, base) / filename


def get_session_metadata_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "session.json", base)


def get_existing_session_metadata_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_metadata_path(chat_id, base)


def get_runtime_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "runtime.json", base)


def get_existing_runtime_path(chat_id: str, base: Path | None = None) -> Path:
    return get_runtime_path(chat_id, base)


def get_plan_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "plan.json", base)


def get_existing_plan_path(chat_id: str, base: Path | None = None) -> Path:
    return get_plan_path(chat_id, base)


def get_notes_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "notes.json", base)


def get_existing_notes_path(chat_id: str, base: Path | None = None) -> Path:
    return get_notes_path(chat_id, base)


def get_rule_notes_path(chat_id: str, base: Path | None = None) -> Path:
    return get_notes_path(chat_id, base)


def get_existing_rule_notes_path(chat_id: str, base: Path | None = None) -> Path:
    return get_notes_path(chat_id, base)


def get_evidence_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "evidence.json", base)


def get_existing_evidence_path(chat_id: str, base: Path | None = None) -> Path:
    return get_evidence_path(chat_id, base)


def get_monitoring_path(chat_id: str, base: Path | None = None) -> Path:
    return get_session_file_path(chat_id, "monitoring.json", base)


def get_existing_monitoring_path(chat_id: str, base: Path | None = None) -> Path:
    return get_monitoring_path(chat_id, base)
