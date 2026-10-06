from pathlib import Path
from typing import Optional
import os
import json
from datetime import datetime

from backend.utils import get_chat_history_source_from_config

VS_CODE_CLAUDE_DEV_TASKS_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Code"
    / "User"
    / "globalStorage"
    / "saoudrizwan.claude-dev"
    / "tasks"
)

CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"

def _find_latest_cline_history_path() -> Optional[Path]:
    root = VS_CODE_CLAUDE_DEV_TASKS_DIR
    if not root.exists():
        return None

    candidates = list(root.glob("*/api_conversation_history.json"))
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)

def _find_latest_codex_session_path() -> Optional[Path]:
    root = CODEX_SESSIONS_DIR
    if not root.exists():
        return None

    candidates = list(root.rglob("*.jsonl"))
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)

def find_latest_chat_history_path() -> Optional[Path]:
    source = get_chat_history_source_from_config()
    if source == "codex":
        return _find_latest_codex_session_path()
    if source == "claude":
        # One-way import (claude_chat_source.py never imports this module)
        # — keeps this existing, directly-called function (create_visualization()
        # calls it with no arguments) correct for all three sources without
        # introducing a cycle with chat_source_registry.py.
        from backend.visualization.services.claude_chat_source import find_latest_claude_session_path

        return find_latest_claude_session_path()
    return _find_latest_cline_history_path()

def _parse_codex_jsonl_messages(raw_content: str) -> list[dict]:
    messages: list[dict] = []
    for line in raw_content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("type") != "response_item":
            continue
        payload = data.get("payload", {})
        if payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue
        blocks = []
        for block in payload.get("content", []) or []:
            block_type = block.get("type")
            if block_type == "input_text" and role == "user":
                blocks.append({"type": "text", "text": block.get("text", "")})
            elif block_type == "output_text" and role == "assistant":
                blocks.append({"type": "text", "text": block.get("text", "")})
        if blocks:
            messages.append({"role": role, "content": blocks})
    return messages

def _parse_generic_json_messages(raw_content: str) -> list:
    """The Cline-style fallback shape: either a bare list of messages, or
    an object with a "messages" list. Extracted (not reworded) from the
    inline branch that used to be duplicated verbatim at both of this
    function's two call sites (visualization_manager.poll_visualization()
    and routes/visualization_api/plans.py's _load_chat_messages()) before
    the chat-source registry replaced the extension-sniffing dispatch
    that used to pick between this and _parse_codex_jsonl_messages."""
    data = json.loads(raw_content)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("messages", [])
    return []


def read_new_chat_content(chat_file_path: str, last_polled_at: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    chat_file = Path(chat_file_path)
    if not chat_file.exists():
        return None, None

    modified_at = datetime.fromtimestamp(chat_file.stat().st_mtime).isoformat()

    if last_polled_at and modified_at <= last_polled_at:
        return None, last_polled_at

    with open(chat_file, "r") as f:
        content = f.read()

    return content, modified_at

def format_chat_content(raw_content: str) -> str:
    try:
        if raw_content.lstrip().startswith("{") and '"type":"session_meta"' in raw_content:
            messages = _parse_codex_jsonl_messages(raw_content)
        else:
            data = json.loads(raw_content)
            if not isinstance(data, dict):
                return raw_content
            messages = data.get("messages", [])
        
        markdown = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                text = "\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = content
            markdown += f"**{role}**:\n{text}\n\n"
            
        return markdown
    except json.JSONDecodeError:
        return raw_content
