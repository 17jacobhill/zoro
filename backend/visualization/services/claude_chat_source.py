"""Claude Code session discovery/parsing — the third chat-history source
alongside Cline and Codex (backend/visualization/services/rule_learning_agent.py).

Structure validated directly against real `~/.claude/projects/**/*.jsonl`
files on this machine (not guessed): directory name is the absolute cwd
with "/" replaced by "-"; each line is a JSON object; conversational
turns have `type` in {"user", "assistant"} (the file also contains many
other record types — custom-title, file-history-snapshot, attachment,
etc. — which have no `message.role` and are correctly skipped by this
same type filter); `isSidechain: true` marks a sub-agent/side-conversation
turn to exclude; `message: {role, content}` is native Anthropic Messages
shape, where `content` is either a plain string or a list of blocks
(`text`, `thinking`, `tool_use`, `tool_result`, `image`, ...) — this
parser keeps only `text`/`thinking`, the same transcript view
`backend.routes.visualization_api.plans._extract_text_from_message_content`
already consumes.

Per CL-006: this discovery path was verified locally, not asserted as a
stable upstream contract — if the on-disk Claude Code session format
changes, this file is where that would need revisiting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _project_slug(cwd: Path) -> str:
    return str(cwd.resolve()).replace("/", "-")


def find_latest_claude_session_path(cwd: Optional[Path] = None) -> Optional[Path]:
    project_dir = CLAUDE_PROJECTS_DIR / _project_slug(cwd or Path.cwd())
    if not project_dir.exists():
        return None

    candidates = list(project_dir.glob("*.jsonl"))
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_claude_jsonl_messages(raw_content: str) -> list[dict]:
    messages: list[dict] = []
    for line in raw_content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("isSidechain"):
            continue
        if obj.get("type") not in {"user", "assistant"}:
            continue

        message = obj.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = message.get("content")
        if isinstance(content, str):
            blocks = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            blocks = [b for b in content if isinstance(b, dict) and b.get("type") in {"text", "thinking"}]
        else:
            continue

        if blocks:
            messages.append({"role": role, "content": blocks})

    return messages
