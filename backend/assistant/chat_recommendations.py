from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.assistant.plan_manager import load_plan
from backend.assistant.prompts.chat_recommendations import (
    CHAT_RECS_SYSTEM_PROMPT,
    CHAT_RECS_SYSTEM_PROMPT_STRICT_RETRY,
    build_chat_recs_user_prompt,
)
from backend.globals.models import get_default_provider
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


@dataclass(frozen=True)
class ChatRecommendationsSource:
    path: str
    mtime: str
    message_count: int
    truncated: bool


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
    return _find_latest_cline_history_path()

def _read_codex_jsonl_messages(path: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
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


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "Failed to parse chat history JSON (file may be mid-write). Please try again."
        ) from e


def _normalize_content_to_text(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt)
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p.strip()])

    return str(content)


def extract_messages(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]

    if isinstance(data, dict):
        if isinstance(data.get("messages"), list):
            return [m for m in data["messages"] if isinstance(m, dict)]

        conversations = data.get("conversations")
        if isinstance(conversations, list) and conversations:
            last_conv = conversations[-1]
            if isinstance(last_conv, dict) and isinstance(last_conv.get("messages"), list):
                return [m for m in last_conv["messages"] if isinstance(m, dict)]

    return []


def apply_context_caps(
    messages: list[dict[str, Any]],
    limit_messages: int,
    max_chars: int,
) -> tuple[list[dict[str, Any]], bool]:
    truncated = False

    if limit_messages > 0 and len(messages) > limit_messages:
        messages = messages[-limit_messages:]
        truncated = True

    texts = [_normalize_content_to_text(m.get("content")) for m in messages]
    total_chars = sum(len(t) for t in texts)

    if max_chars > 0 and total_chars > max_chars:
        truncated = True
        kept: list[dict[str, Any]] = []
        running = 0
        for msg, txt in zip(reversed(messages), reversed(texts)):
            if running + len(txt) > max_chars:
                break
            kept.append(msg)
            running += len(txt)
        kept.reverse()
        messages = kept

    return messages, truncated


def recommend_next_actions(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    raise RuntimeError(
        "recommend_next_actions is deprecated. GPT-based recommendations should be used instead."
    )


def _strip_code_fences(text: str) -> str:
    s = (text or "").lstrip("\ufeff").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        s = "\n".join(lines).strip()
    return s


def _parse_recommendations_json(text: str) -> list[dict[str, str]]:
    cleaned = _strip_code_fences(text)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("schema_error: root is not an object")

    recs = data.get("recommendations")
    if not isinstance(recs, list) or not (1 <= len(recs) <= 2):
        raise ValueError("schema_error: recommendations must be a list of length 1-2")

    out: list[dict[str, str]] = []
    for item in recs:
        if not isinstance(item, dict):
            raise ValueError("schema_error: each recommendation must be an object")
        text_val = item.get("text")
        reason_val = item.get("reason")
        if not isinstance(text_val, str) or not text_val.strip():
            raise ValueError("schema_error: recommendation.text must be a non-empty string")
        if not isinstance(reason_val, str) or not reason_val.strip():
            raise ValueError("schema_error: recommendation.reason must be a non-empty string")
        out.append({"text": text_val.strip(), "reason": reason_val.strip()})

    return out


def _messages_to_transcript(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = str(m.get("role") or "").strip() or "unknown"
        content = _normalize_content_to_text(m.get("content")).strip()
        if not content:
            continue
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def _gpt_recommendations(
    messages: list[dict[str, Any]],
    selected_plan_json: str,
    debug_prompt: bool = False,
) -> list[dict[str, str]]:
    provider = get_default_provider()
    transcript = _messages_to_transcript(messages)
    user_prompt = build_chat_recs_user_prompt(transcript, selected_plan_json)

    llm_messages_default = [
        {"role": "system", "content": CHAT_RECS_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    llm_messages_retry = [
        {"role": "system", "content": CHAT_RECS_SYSTEM_PROMPT_STRICT_RETRY},
        {"role": "user", "content": user_prompt},
    ]

    if debug_prompt:
        print("\n=== chat-recs LLM prompt (default) ===")
        print(json.dumps(llm_messages_default, indent=2, ensure_ascii=False))
        print("=== end prompt ===\n")

    def call(llm_messages: list[dict[str, str]]) -> str:
        return provider.chat_completion(
            messages=llm_messages,
            model="gpt-5",
            temperature=0,
            top_p=1,
        )

    last_error: Optional[Exception] = None
    attempts = [llm_messages_default, llm_messages_retry]
    for attempt, llm_messages in enumerate(attempts, start=1):
        try:
            if debug_prompt and attempt == 2:
                print("\n=== chat-recs LLM prompt (strict retry) ===")
                print(json.dumps(llm_messages_retry, indent=2, ensure_ascii=False))
                print("=== end prompt ===\n")

            raw = call(llm_messages)
            return _parse_recommendations_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt == 1:
                continue
            raise
        except Exception as e:
            last_error = e
            raise

    if last_error:
        raise last_error

    raise RuntimeError("provider_error")


def get_chat_recommendations(
    chat_id: Optional[str] = None,
    path: Optional[str] = None,
    limit_messages: int = 100,
    max_chars: int = 120_000,
    debug_prompt: bool = False,
) -> dict[str, Any]:
    resolved = Path(path).expanduser() if path else find_latest_chat_history_path()
    if not resolved:
        source = get_chat_history_source_from_config()
        expected = VS_CODE_CLAUDE_DEV_TASKS_DIR if source == "cline" else CODEX_SESSIONS_DIR
        return {
            "recommendations": [
                {
                    "text": "No chat history file found.",
                    "reason": f"Expected {source} history under: {expected}",
                }
            ],
            "source": None,
        }

    if resolved.suffix == ".jsonl":
        messages = _read_codex_jsonl_messages(resolved)
    else:
        text = resolved.read_text(encoding="utf-8", errors="replace")
        data = _safe_json_loads(text)
        messages = extract_messages(data)
    capped, truncated = apply_context_caps(messages, limit_messages=limit_messages, max_chars=max_chars)

    plan_json_str = "{}"
    if chat_id:
        plan = load_plan(chat_id)
        if plan:
            plan_json_str = json.dumps(plan.model_dump(by_alias=True), indent=2, ensure_ascii=False)

    try:
        recs = _gpt_recommendations(capped, plan_json_str, debug_prompt=debug_prompt)
    except json.JSONDecodeError:
        return {"success": False, "error": "invalid_json"}
    except ValueError as e:
        msg = str(e)
        if msg.startswith("schema_error"):
            return {"success": False, "error": "schema_error"}
        return {"success": False, "error": "invalid_json"}
    except Exception:
        return {"success": False, "error": "provider_error"}

    st = resolved.stat()
    source = ChatRecommendationsSource(
        path=str(resolved),
        mtime=datetime.fromtimestamp(st.st_mtime).isoformat(),
        message_count=len(capped),
        truncated=truncated,
    )

    return {
        "success": True,
        "recommendations": recs,
        "source": {
            "path": source.path,
            "mtime": source.mtime,
            "message_count": source.message_count,
            "truncated": source.truncated,
        },
    }
