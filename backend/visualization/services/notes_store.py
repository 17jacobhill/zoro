from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.utils import get_project_root
from backend.visualization.paths import get_existing_notes_path, get_notes_path


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _base36(number: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"
    out = []
    value = number
    while value:
        value, remainder = divmod(value, 36)
        out.append(alphabet[remainder])
    return "".join(reversed(out))


def sanitize_note_key_part(value: str) -> str:
    normalized = _NON_ALNUM_RE.sub("-", (value or "").strip().lower()).strip("-")
    return normalized or "na"


def hash_note_text(value: str) -> str:
    hash_value = 2166136261
    for char in value or "":
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return _base36(hash_value)


def create_note_key(
    *,
    source: str,
    item_id: str | None = None,
    rule_kb_item_id: str | None = None,
    rule_text: str | None = None,
    evidence_record_id: str | None = None,
    timestamp: str | None = None,
    index: int | None = 0,
) -> str:
    if evidence_record_id:
        return f"rn__evidence__{sanitize_note_key_part(evidence_record_id)}"
    source_part = sanitize_note_key_part(source or "rule-verification")
    item_part = sanitize_note_key_part(item_id or "no-item")
    rule_part = (
        sanitize_note_key_part(rule_kb_item_id)
        if rule_kb_item_id
        else f"txt-{hash_note_text(rule_text or '')}"
    )
    timestamp_part = sanitize_note_key_part(timestamp or "no-ts")
    index_part = str(index or 0)
    return f"rn__{source_part}__{item_part}__{rule_part}__{timestamp_part}__{index_part}"


def normalize_note_record(
    chat_id: str,
    note_key: str,
    note_value: Any,
    now_iso: str | None = None,
    *,
    touch: bool = False,
) -> dict:
    timestamp = now_iso or _now_iso()
    record = dict(note_value) if isinstance(note_value, dict) else {"note_text": str(note_value or "")}

    record["note_key"] = note_key
    record["chat_id"] = chat_id
    record["note_text"] = str(record.get("note_text", ""))
    record["rule_kb_item_id"] = record.get("rule_kb_item_id")
    record["rule_text"] = str(record.get("rule_text", ""))
    record["plan_item_id"] = record.get("plan_item_id")
    record["evidence_record_id"] = record.get("evidence_record_id")
    record["verification_timestamp"] = record.get("verification_timestamp")
    record["verification_index"] = record.get("verification_index")
    record["source"] = str(record.get("source", "rule-verification"))
    record["verdict"] = record.get("verdict")
    record["explanation"] = str(record.get("explanation", ""))
    record["created_at"] = record.get("created_at") or timestamp
    record["updated_at"] = timestamp if touch else (record.get("updated_at") or record["created_at"])
    return record


def _empty_notes_doc(chat_id: str, now_iso: str | None = None) -> dict:
    timestamp = now_iso or _now_iso()
    return {
        "chat_id": chat_id,
        "notes": {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def load_notes_document(chat_id: str, base: Path | None = None) -> dict:
    root = base or get_project_root()
    notes_path = get_existing_notes_path(chat_id, root)
    now_iso = _now_iso()

    if notes_path.exists():
        try:
            with open(notes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes = data.get("notes", {})
            if isinstance(notes, dict):
                normalized_notes = {
                    str(note_key): normalize_note_record(chat_id, str(note_key), note_value, now_iso)
                    for note_key, note_value in notes.items()
                }
                return {
                    "chat_id": chat_id,
                    "notes": normalized_notes,
                    "created_at": data.get("created_at") or now_iso,
                    "updated_at": data.get("updated_at") or now_iso,
                }
        except (json.JSONDecodeError, OSError, ValueError):
            return _empty_notes_doc(chat_id, now_iso)

    return _empty_notes_doc(chat_id, now_iso)


def save_notes_document(chat_id: str, notes_doc: dict, base: Path | None = None) -> Path:
    root = base or get_project_root()
    path = get_notes_path(chat_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes_doc, f, indent=2, ensure_ascii=False)

    return path


def append_note_record(
    chat_id: str,
    *,
    note_text: str,
    source: str,
    plan_item_id: str | None = None,
    rule_kb_item_id: str | None = None,
    rule_text: str | None = None,
    evidence_record_id: str | None = None,
    verification_timestamp: str | None = None,
    verification_index: int | None = None,
    verdict: str | None = None,
    explanation: str | None = None,
    note_key: str | None = None,
    base: Path | None = None,
) -> dict:
    now_iso = _now_iso()
    notes_doc = load_notes_document(chat_id, base)
    notes = notes_doc.setdefault("notes", {})
    resolved_key = note_key or create_note_key(
        source=source,
        item_id=plan_item_id,
        rule_kb_item_id=rule_kb_item_id,
        rule_text=rule_text,
        evidence_record_id=evidence_record_id,
        timestamp=verification_timestamp or now_iso,
        index=verification_index or 0,
    )
    prior = notes.get(resolved_key, {})
    normalized = normalize_note_record(
        chat_id,
        resolved_key,
        {
            "note_text": note_text,
            "rule_kb_item_id": rule_kb_item_id,
            "rule_text": rule_text or "",
            "plan_item_id": plan_item_id,
            "evidence_record_id": evidence_record_id,
            "verification_timestamp": verification_timestamp,
            "verification_index": verification_index,
            "source": source,
            "verdict": verdict,
            "explanation": explanation or "",
            "created_at": prior.get("created_at") if isinstance(prior, dict) else None,
        },
        now_iso,
        touch=True,
    )
    notes[resolved_key] = normalized
    notes_doc["chat_id"] = chat_id
    notes_doc["created_at"] = notes_doc.get("created_at") or normalized["created_at"]
    notes_doc["updated_at"] = now_iso
    save_notes_document(chat_id, notes_doc, base)
    return normalized
