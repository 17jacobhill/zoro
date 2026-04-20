from pathlib import Path

from backend.cli.utils import detect_active_chat
from backend.plan_paths import (
    get_existing_plan_markdown_path,
    get_legacy_plan_markdown_path,
    get_plan_markdown_path,
)


def test_existing_plan_markdown_path_prefers_rules(tmp_path):
    rules_path = get_plan_markdown_path(tmp_path)
    legacy_path = get_legacy_plan_markdown_path(tmp_path)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)

    legacy_path.write_text("# Visualization Plan: Legacy (legacy-chat)\n", encoding="utf-8")
    rules_path.write_text("# Visualization Plan: Primary (rules-chat)\n", encoding="utf-8")

    assert get_existing_plan_markdown_path(tmp_path) == rules_path


def test_existing_plan_markdown_path_falls_back_to_clinerules(tmp_path):
    legacy_path = get_legacy_plan_markdown_path(tmp_path)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("# Visualization Plan: Legacy (legacy-chat)\n", encoding="utf-8")

    assert get_existing_plan_markdown_path(tmp_path) == legacy_path


def test_detect_active_chat_reads_rules_file_first(monkeypatch, tmp_path):
    rules_path = get_plan_markdown_path(tmp_path)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text("# Visualization Plan: Demo (chat-xyz)\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert detect_active_chat() == "chat-xyz"
