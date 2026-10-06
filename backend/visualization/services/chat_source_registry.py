"""Dispatches chat-message PARSING by the configured `chat_history_source`
(cline/codex/claude) instead of sniffing the file's extension.

Fixes a real bug: `visualization_manager.poll_visualization()` and
`routes/visualization_api/plans.py`'s `_load_chat_messages()` both used
to hardcode `if chat_file_path.endswith(".jsonl"): _parse_codex_jsonl_messages(...)`
and import that private function directly — ignoring the configured
source entirely, and with no way to ever reach the Claude parser. Both
call sites now go through `parse_chat_messages()` here, keyed by the
SESSION'S OWN STORED `chat_history_source` (captured once, at
`create_visualization()` time) rather than live config — so a later
global config change can't reinterpret an already-created visualization
with the wrong parser.
"""

from __future__ import annotations

from typing import Optional

from backend.utils import get_chat_history_source_from_config
from backend.visualization.services.claude_chat_source import (
    find_latest_claude_session_path,
    parse_claude_jsonl_messages,
)
from backend.visualization.services.rule_learning_agent import (
    _find_latest_cline_history_path,
    _find_latest_codex_session_path,
    _parse_codex_jsonl_messages,
    _parse_generic_json_messages,
)

_ADAPTERS = {
    "cline": {"find_latest_path": _find_latest_cline_history_path, "parse_messages": _parse_generic_json_messages},
    "codex": {"find_latest_path": _find_latest_codex_session_path, "parse_messages": _parse_codex_jsonl_messages},
    "claude": {"find_latest_path": find_latest_claude_session_path, "parse_messages": parse_claude_jsonl_messages},
}


def get_adapter(source: Optional[str] = None, *, file_path: Optional[str] = None) -> dict:
    if source in _ADAPTERS:
        return _ADAPTERS[source]
    if file_path and str(file_path).lower().endswith(".jsonl"):
        # Legacy fallback for a session with no recorded chat_history_source
        # (a visualization created before this field existed, or a
        # hand-constructed fixture) — ".jsonl" has always meant Codex in
        # this codebase, so preserve that exactly rather than falling
        # through to the live config default, which could silently pick
        # the wrong parser for an old session.
        return _ADAPTERS["codex"]
    resolved = get_chat_history_source_from_config()
    return _ADAPTERS.get(resolved, _ADAPTERS["cline"])


def parse_chat_messages(raw_content: str, source: Optional[str] = None, *, file_path: Optional[str] = None) -> list:
    return get_adapter(source, file_path=file_path)["parse_messages"](raw_content)
