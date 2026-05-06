from __future__ import annotations

from pathlib import Path

from backend.utils import get_project_root


def _root(base: Path | None = None) -> Path:
    return base or get_project_root()


def get_rules_root(base: Path | None = None) -> Path:
    return _root(base) / ".zoro" / "rules"


def get_structured_rules_dir(base: Path | None = None) -> Path:
    return get_rules_root(base) / "structured"


def get_unstructured_rules_dir(base: Path | None = None) -> Path:
    return get_rules_root(base) / "unstructured"


def get_processed_unstructured_dir(base: Path | None = None) -> Path:
    return get_unstructured_rules_dir(base) / "processed"


def get_knowledge_base_path(base: Path | None = None) -> Path:
    return get_structured_rules_dir(base) / "knowledge_base.json"


def get_manual_favorites_path(base: Path | None = None) -> Path:
    return get_structured_rules_dir(base) / "manual_favorites.json"


def get_processing_log_path(base: Path | None = None) -> Path:
    return get_structured_rules_dir(base) / "processing_log.json"
