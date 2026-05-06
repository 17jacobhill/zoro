from backend.cli.utils import detect_active_chat
from backend.plan_paths import (
    get_existing_plan_markdown_path,
    get_plan_markdown_path,
)


def test_existing_plan_markdown_path_is_canonical_current_plan(tmp_path):
    current_path = get_plan_markdown_path(tmp_path)
    assert get_existing_plan_markdown_path(tmp_path) == current_path


def test_detect_active_chat_reads_current_plan(monkeypatch, tmp_path):
    rules_path = get_plan_markdown_path(tmp_path)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text("# Visualization Plan: Demo (chat-xyz)\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert detect_active_chat() == "chat-xyz"


def test_detect_active_chat_returns_none_without_plan(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert detect_active_chat() is None
