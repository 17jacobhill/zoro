from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.knowledge.services.storage import increment_rule_usage_count
from backend.utils import get_project_root
from backend.visualization.paths import get_evidence_path, get_existing_evidence_path


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


def _sanitize(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "na"


def _hash_text(value: str) -> str:
    hash_value = 2166136261
    for char in value or "":
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return _base36(hash_value)


def _normalize_code_artifacts(artifacts: Any) -> list[dict]:
    if not isinstance(artifacts, list):
        return []

    normalized = []
    for artifact in artifacts:
        if isinstance(artifact, dict):
            normalized.append(dict(artifact))
    return normalized


def _normalize_rule_identity(rule_kb_item_id: Any, rule_text: Any) -> tuple[str | None, str]:
    kb_item_id = str(rule_kb_item_id).strip() if rule_kb_item_id else None
    text = " ".join(str(rule_text or "").strip().lower().split())
    return kb_item_id or None, text


def build_evidence_record_id(
    *,
    source: str,
    item_id: str | None = None,
    rule_kb_item_id: str | None = None,
    rule_text: str | None = None,
    timestamp: str | None = None,
    index: int | None = 0,
) -> str:
    source_part = _sanitize(source or "rule-verification")
    item_part = _sanitize(item_id or "no-item")
    rule_part = _sanitize(rule_kb_item_id) if rule_kb_item_id else f"txt-{_hash_text(rule_text or '')}"
    timestamp_part = _sanitize(timestamp or "no-ts")
    index_part = str(index or 0)
    return f"ev__{source_part}__{item_part}__{rule_part}__{timestamp_part}__{index_part}"


def normalize_evidence_record(chat_id: str, record: dict, now_iso: str | None = None) -> dict:
    timestamp = now_iso or _now_iso()
    normalized = dict(record or {})
    normalized["record_id"] = str(
        normalized.get("record_id")
        or build_evidence_record_id(
            source=str(normalized.get("source", "rule-verification")),
            item_id=str(normalized.get("item_id") or ""),
            rule_kb_item_id=normalized.get("rule_kb_item_id"),
            rule_text=str(normalized.get("rule_text") or ""),
            timestamp=str(normalized.get("timestamp") or timestamp),
            index=int(normalized.get("record_index") or 0),
        )
    )
    normalized["chat_id"] = chat_id
    normalized["item_id"] = normalized.get("item_id")
    normalized["rule_kb_item_id"] = normalized.get("rule_kb_item_id")
    normalized["rule_category"] = str(normalized.get("rule_category", ""))
    normalized["rule_text"] = str(normalized.get("rule_text", ""))
    normalized["rule_source"] = str(normalized.get("rule_source", "self"))
    normalized["source_title"] = str(normalized.get("source_title", ""))
    normalized["is_inherited"] = bool(normalized.get("is_inherited", False))
    normalized["source"] = str(normalized.get("source", "rule-verification"))
    normalized["explanation"] = str(normalized.get("explanation", ""))
    normalized["detected_evidence"] = str(normalized.get("detected_evidence", ""))
    normalized["item_detected_evidence"] = str(normalized.get("item_detected_evidence", ""))
    normalized["artifacts"] = _normalize_code_artifacts(normalized.get("artifacts"))
    normalized["tests"] = normalized.get("tests") if isinstance(normalized.get("tests"), dict) else None
    normalized["verdict"] = str(normalized.get("verdict", "unclear"))
    normalized["timestamp"] = str(normalized.get("timestamp") or timestamp)
    normalized["record_index"] = int(normalized.get("record_index") or 0)
    raw_rule_result = normalized.get("raw_rule_result")
    normalized["raw_rule_result"] = raw_rule_result if isinstance(raw_rule_result, dict) else None
    return normalized


def _empty_evidence_doc(chat_id: str, now_iso: str | None = None) -> dict:
    timestamp = now_iso or _now_iso()
    return {
        "chat_id": chat_id,
        "records": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def load_evidence_document(chat_id: str, base: Path | None = None) -> dict:
    root = base or get_project_root()
    evidence_path = get_existing_evidence_path(chat_id, root)
    now_iso = _now_iso()

    if not evidence_path.exists():
        return _empty_evidence_doc(chat_id, now_iso)

    try:
        with open(evidence_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return _empty_evidence_doc(chat_id, now_iso)

    raw_records = data.get("records", [])
    return {
        "chat_id": chat_id,
        "records": [normalize_evidence_record(chat_id, record, now_iso) for record in raw_records if isinstance(record, dict)],
        "created_at": data.get("created_at") or now_iso,
        "updated_at": data.get("updated_at") or now_iso,
    }


def save_evidence_document(chat_id: str, evidence_doc: dict, base: Path | None = None) -> Path:
    root = base or get_project_root()
    path = get_evidence_path(chat_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(evidence_doc, f, indent=2, ensure_ascii=False)

    return path


def append_external_verifier_reference(
    chat_id: str,
    *,
    item_id: str,
    rule_ids: list[str],
    verifier_id: str,
    invocation_id: str,
    manifest_path: str,
    status: str | None,
    coverage: str | None,
    decision: str,
    base: Path | None = None,
) -> dict:
    """Appends a COMPACT `source: "external-verifier"` reference into the
    existing per-chat evidence.json, through the existing (unchanged)
    load/save_evidence_document round-trip. The full manifest + imported
    envelope/report already live under the immutable, atomically-written
    `.zoro/visualization/<chat_id>/verifiers/...` directory
    (external_verifier_store.py) — this is only a pointer to it, so
    `update_step.py` can check "is there current accepted evidence" via
    the same evidence_doc it already reads for rule-verification records.

    Deliberately NOT deduped by content (unlike append_rule_verification_evidence,
    which skips re-inserting an identical record): every invocation gets
    its own record, so failed/superseded attempts stay in history
    (handoff ZO-011) rather than being silently merged away.
    """
    now_iso = _now_iso()
    evidence_doc = load_evidence_document(chat_id, base)
    records = evidence_doc.setdefault("records", [])

    record = normalize_evidence_record(
        chat_id,
        {
            "item_id": item_id,
            "rule_text": ", ".join(rule_ids),
            "rule_source": "self",
            "is_inherited": False,
            "source": "external-verifier",
            "explanation": f"{verifier_id} verification: {decision}",
            "verdict": "pass" if decision in ("accept", "review_required") else "fail",
            "timestamp": now_iso,
            "record_index": len(records),
            "raw_rule_result": {
                "verifier_id": verifier_id,
                "invocation_id": invocation_id,
                "manifest_path": manifest_path,
                "status": status,
                "coverage": coverage,
                "decision": decision,
                "rule_ids": rule_ids,
            },
        },
        now_iso,
    )

    records.append(record)
    evidence_doc["chat_id"] = chat_id
    evidence_doc["created_at"] = evidence_doc.get("created_at") or now_iso
    evidence_doc["updated_at"] = now_iso
    save_evidence_document(chat_id, evidence_doc, base)
    return record


def get_external_verifier_records_for_item(
    evidence_doc: dict, item_id: str, verifier_id: str | None = None
) -> list[dict]:
    """Separate sibling of get_rule_verification_records_for_item — that
    function hard-filters `source == "rule-verification"` and structurally
    can never see an external-verifier record. Keeping this as its own
    function (rather than a parameter on the existing one) means
    "prove-rule evidence never satisfies a security gate" is enforced by
    two distinct code paths, not a convention a future caller could
    violate by passing the wrong `source` into a shared lookup."""
    matches = []
    for record in evidence_doc.get("records", []):
        if not isinstance(record, dict):
            continue
        if record.get("source") != "external-verifier":
            continue
        if str(record.get("item_id") or "") != str(item_id):
            continue
        raw = record.get("raw_rule_result") or {}
        if verifier_id and raw.get("verifier_id") != verifier_id:
            continue
        matches.append(record)
    return matches


def get_rule_verification_records_for_item(evidence_doc: dict, item_id: str, rule: dict) -> list[dict]:
    target_identity = _normalize_rule_identity(rule.get("kb_item_id"), rule.get("text"))
    matches = []
    for record in evidence_doc.get("records", []):
        if not isinstance(record, dict):
            continue
        if record.get("source") != "rule-verification":
            continue
        if str(record.get("item_id") or "") != str(item_id):
            continue
        if _normalize_rule_identity(record.get("rule_kb_item_id"), record.get("rule_text")) != target_identity:
            continue
        matches.append(record)
    return matches


def append_rule_verification_evidence(
    chat_id: str,
    *,
    item_id: str,
    rule: dict,
    verification: dict,
    source_title: str,
    is_inherited: bool,
    record_index: int | None = None,
    base: Path | None = None,
) -> dict:
    now_iso = verification.get("timestamp") or _now_iso()
    evidence_doc = load_evidence_document(chat_id, base)
    records = evidence_doc.setdefault("records", [])

    if record_index is None:
        record_index = len(get_rule_verification_records_for_item(evidence_doc, item_id, rule))

    record = normalize_evidence_record(
        chat_id,
        {
            "item_id": item_id,
            "rule_kb_item_id": rule.get("kb_item_id"),
            "rule_category": rule.get("category", ""),
            "rule_text": rule.get("text", ""),
            "rule_source": "parent" if is_inherited else "self",
            "source_title": source_title,
            "is_inherited": is_inherited,
            "source": "rule-verification",
            "explanation": verification.get("explanation", ""),
            "artifacts": verification.get("code_blocks", []),
            "tests": verification.get("test_evidence"),
            "verdict": verification.get("verdict", "unclear"),
            "timestamp": now_iso,
            "record_index": record_index,
        },
        now_iso,
    )

    existing_ids = {existing.get("record_id") for existing in records if isinstance(existing, dict)}
    inserted = False
    if record["record_id"] not in existing_ids:
        records.append(record)
        inserted = True

    evidence_doc["chat_id"] = chat_id
    evidence_doc["created_at"] = evidence_doc.get("created_at") or now_iso
    evidence_doc["updated_at"] = now_iso
    save_evidence_document(chat_id, evidence_doc, base)

    if inserted and str(record.get("verdict", "")).lower() == "pass":
        increment_rule_usage_count(
            kb_item_id=record.get("rule_kb_item_id"),
            rule_text=record.get("rule_text"),
            category=record.get("rule_category"),
            amount=1,
        )
    return record


def _normalize_enforcement_rule(
    chat_id: str,
    item_id: str,
    timestamp: str,
    rule_result: Any,
    item_detected_evidence: str,
    record_index: int,
) -> dict:
    if isinstance(rule_result, dict):
        raw_rule = dict(rule_result)
    else:
        raw_rule = {"rule_text": str(rule_result or "")}

    files_changed = raw_rule.get("files_changed", [])
    code_blocks = raw_rule.get("code_blocks", [])
    artifacts = []
    if isinstance(files_changed, list):
        artifacts.extend(file_change for file_change in files_changed if isinstance(file_change, dict))
    if isinstance(code_blocks, list):
        artifacts.extend(
            {
                "file_path": block.get("file") or block.get("path"),
                "line_range": block.get("lines") or block.get("line_range"),
                "code_snippet": block.get("code") or block.get("code_snippet"),
                "annotation": block.get("annotation"),
            }
            for block in code_blocks
            if isinstance(block, dict)
        )

    return normalize_evidence_record(
        chat_id,
        {
            "item_id": item_id,
            "rule_kb_item_id": raw_rule.get("rule_id"),
            "rule_category": raw_rule.get("category", ""),
            "rule_text": raw_rule.get("rule_text") or raw_rule.get("text") or raw_rule.get("rule") or "",
            "rule_source": "auto-enforcement",
            "source_title": "",
            "is_inherited": False,
            "source": "auto-enforcement",
            "explanation": raw_rule.get("evidence", ""),
            "detected_evidence": raw_rule.get("evidence", ""),
            "item_detected_evidence": item_detected_evidence,
            "artifacts": artifacts,
            "tests": None,
            "verdict": raw_rule.get("verdict", "unclear"),
            "timestamp": timestamp,
            "record_index": record_index,
            "raw_rule_result": raw_rule,
        },
        timestamp,
    )


def append_enforcement_evidence(chat_id: str, item_id: str, result: dict, base: Path | None = None) -> list[dict]:
    completed_items = result.get("completed_items", []) or []
    matched = [
        item_result
        for item_result in completed_items
        if isinstance(item_result, dict) and str(item_result.get("item_id", "")) == str(item_id)
    ]
    if not matched:
        return []

    evidence_doc = load_evidence_document(chat_id, base)
    records = evidence_doc.setdefault("records", [])
    existing_ids = {existing.get("record_id") for existing in records if isinstance(existing, dict)}
    appended = []

    for item_result in matched:
        timestamp = str(result.get("timestamp") or item_result.get("timestamp") or _now_iso())
        item_detected_evidence = str(item_result.get("detected_evidence") or "")
        for record_index, rule_result in enumerate(item_result.get("rules_verified", []) or []):
            record = _normalize_enforcement_rule(
                chat_id,
                item_id,
                timestamp,
                rule_result,
                item_detected_evidence,
                record_index,
            )
            if record["record_id"] in existing_ids:
                continue
            records.append(record)
            existing_ids.add(record["record_id"])
            appended.append(record)

            if str(record.get("verdict", "")).lower() == "pass":
                increment_rule_usage_count(
                    kb_item_id=record.get("rule_kb_item_id"),
                    rule_text=record.get("rule_text"),
                    category=record.get("rule_category"),
                    amount=1,
                )

    if appended:
        evidence_doc["chat_id"] = chat_id
        evidence_doc["created_at"] = evidence_doc.get("created_at") or appended[0]["timestamp"]
        evidence_doc["updated_at"] = appended[-1]["timestamp"]
        save_evidence_document(chat_id, evidence_doc, base)

    return appended


def build_enforcement_history(evidence_doc: dict) -> dict:
    by_item: dict[str, list[dict]] = {}
    for record in evidence_doc.get("records", []):
        if not isinstance(record, dict):
            continue
        if record.get("source") != "auto-enforcement":
            continue
        item_id = str(record.get("item_id") or "").strip()
        if not item_id:
            continue
        by_item.setdefault(item_id, []).append(record)

    items = {}
    for item_id, records in by_item.items():
        latest_timestamp = max(str(record.get("timestamp") or "") for record in records)
        latest_records = [record for record in records if str(record.get("timestamp") or "") == latest_timestamp]
        detected_evidence = next(
            (
                str(record.get("item_detected_evidence") or "")
                for record in latest_records
                if str(record.get("item_detected_evidence") or "").strip()
            ),
            "",
        )
        rules_verified = [
            record.get("raw_rule_result")
            or {
                "rule_id": record.get("rule_kb_item_id"),
                "category": record.get("rule_category"),
                "rule_text": record.get("rule_text"),
                "evidence": record.get("detected_evidence"),
                "verdict": record.get("verdict"),
                "code_blocks": record.get("artifacts", []),
            }
            for record in latest_records
        ]
        items[item_id] = {
            "last_enforced": latest_timestamp,
            "detected_evidence": detected_evidence,
            "rules_verified": rules_verified,
        }

    return {"items": items, "runs": []}
