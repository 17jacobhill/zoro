from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

from backend.globals.models import get_default_provider
from backend.globals.schemas import get_schema
from backend.knowledge.services.storage import (
    load_knowledge_base,
    load_processing_log,
    save_knowledge_base,
    save_processing_log,
)
from backend.knowledge.prompts.parse_unstructured import PARSE_UNSTRUCTURED_PROMPT
from backend.knowledge.prompts.parse_repo_instructions import PARSE_REPO_INSTRUCTIONS_PROMPT
from backend.utils import get_llm_model_for_feature
from backend.utils import get_project_root

from .common import handle_error, logger, knowledge_bp

FULL_FILE_MAX_CHARS = 24_000
CHUNK_TARGET_CHARS = 9_000
MIN_CHUNK_CHARS = 1_200
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _iter_unstructured_markdown_files(unstructured_dir: Path) -> list[Path]:
    processed_dir = unstructured_dir / "processed"
    candidates = [
        path
        for path in unstructured_dir.rglob("*.md")
        if path.is_file() and processed_dir not in path.parents
    ]
    return sorted(candidates)


def _resolve_unstructured_file(unstructured_dir: Path, filename: str) -> Path | None:
    normalized = str(filename or "").strip().replace("\\", "/")
    if not normalized:
        return None

    candidate = (unstructured_dir / normalized).resolve()
    try:
        candidate.relative_to(unstructured_dir.resolve())
    except ValueError:
        return None
    return candidate


def _relative_unstructured_filename(unstructured_dir: Path, file_path: Path) -> str:
    return file_path.relative_to(unstructured_dir).as_posix()


def _processed_snapshot_name(filename: str, timestamp_str: str) -> str:
    stem = filename[:-3] if filename.lower().endswith(".md") else filename
    safe_stem = stem.replace("/", "__")
    return f"{safe_stem}_{timestamp_str}.md"


def _make_chunk(start_line: int, end_line: int, chunk_text: str) -> dict:
    chunk_hash_input = f"{start_line}:{end_line}:{chunk_text}".encode("utf-8")
    return {
        "chunk_id": hashlib.sha256(chunk_hash_input).hexdigest(),
        "start_line": start_line,
        "end_line": end_line,
        "text": chunk_text,
        "char_count": len(chunk_text),
    }


def _split_oversized_block(text: str, start_line: int, end_line: int, target_chars: int) -> list[dict]:
    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[dict] = []
    current_lines: list[str] = []
    current_chars = 0
    current_start = start_line
    line_no = start_line - 1

    for line in lines:
        line_no += 1
        line_chars = len(line) + 1
        if current_lines and current_chars + line_chars > target_chars:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append(_make_chunk(current_start, line_no - 1, chunk_text))
            current_lines = [line]
            current_chars = line_chars
            current_start = line_no
        else:
            current_lines.append(line)
            current_chars += line_chars

    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text:
            chunks.append(_make_chunk(current_start, end_line, chunk_text))

    return chunks


def _sectionize_markdown(content: str) -> list[dict]:
    lines = content.splitlines()
    if not lines:
        return []

    sections: list[dict] = []
    current_lines: list[str] = []
    current_start = 1
    in_code_fence = False

    for idx, line in enumerate(lines, start=1):
        if CODE_FENCE_RE.match(line):
            in_code_fence = not in_code_fence
            if not current_lines:
                current_start = idx
            current_lines.append(line)
            continue

        is_heading = bool(HEADING_RE.match(line))
        if is_heading and not in_code_fence and current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append({"start_line": current_start, "end_line": idx - 1, "text": section_text})
            current_lines = [line]
            current_start = idx
            continue

        if not current_lines:
            current_start = idx
        current_lines.append(line)

    if current_lines:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append({"start_line": current_start, "end_line": len(lines), "text": section_text})

    if sections:
        return sections

    # Fallback for plain text with no markdown headings.
    raw = content.strip()
    if not raw:
        return []
    return [{"start_line": 1, "end_line": max(1, len(lines)), "text": raw}]


def _build_content_chunks(content: str, target_chars: int = CHUNK_TARGET_CHARS) -> list[dict]:
    sections = _sectionize_markdown(content)
    if not sections:
        return []

    chunks: list[dict] = []
    current_sections: list[dict] = []
    current_chars = 0

    def flush_current():
        nonlocal current_sections, current_chars
        if not current_sections:
            return
        start_line = current_sections[0]["start_line"]
        end_line = current_sections[-1]["end_line"]
        chunk_text = "\n\n".join(section["text"] for section in current_sections).strip()
        if chunk_text:
            chunks.append(_make_chunk(start_line, end_line, chunk_text))
        current_sections = []
        current_chars = 0

    for section in sections:
        text = section["text"]
        section_len = len(text)

        if section_len > target_chars * 1.25:
            flush_current()
            chunks.extend(
                _split_oversized_block(
                    text,
                    start_line=section["start_line"],
                    end_line=section["end_line"],
                    target_chars=max(MIN_CHUNK_CHARS, target_chars),
                )
            )
            continue

        projected = current_chars + section_len + (2 if current_sections else 0)
        if current_sections and projected > target_chars:
            flush_current()

        current_sections.append(section)
        current_chars += section_len + (2 if len(current_sections) > 1 else 0)

    flush_current()

    if not chunks and content.strip():
        chunks.append(_make_chunk(1, max(1, len(content.splitlines())), content.strip()))

    return chunks


def _resolve_processed_chunk_hashes(log_entry: dict, content_hash: str, chunks: list[dict]) -> set[str]:
    if not chunks:
        return set()

    valid_chunk_ids = {chunk["chunk_id"] for chunk in chunks}

    if log_entry.get("content_hash") == content_hash:
        hashes = log_entry.get("processed_chunk_hashes", [])
        if isinstance(hashes, list):
            return {str(chunk_hash) for chunk_hash in hashes if str(chunk_hash) in valid_chunk_ids}
        return set()

    # Legacy fallback: older logs tracked processed section count as `items_processed`.
    legacy_count = _coerce_optional_int(log_entry.get("items_processed")) or 0
    if legacy_count <= 0:
        return set()
    if log_entry.get("content_hash") and log_entry.get("content_hash") != content_hash:
        return set()

    return {chunk["chunk_id"] for chunk in chunks[: min(legacy_count, len(chunks))]}


def _compute_progress(content: str, chunks: list[dict], processed_chunk_hashes: set[str]) -> dict:
    total_chars = len(content)
    total_chunks = len(chunks)
    processed_chunks = sum(1 for chunk in chunks if chunk["chunk_id"] in processed_chunk_hashes)
    pending_chunks = max(0, total_chunks - processed_chunks)

    if total_chunks > 0 and processed_chunks >= total_chunks:
        processed_chars = total_chars
    else:
        processed_chars = sum(
            int(chunk.get("char_count", len(chunk.get("text", ""))))
            for chunk in chunks
            if chunk["chunk_id"] in processed_chunk_hashes
        )
    processed_chars = min(processed_chars, total_chars)
    unprocessed_chars = max(0, total_chars - processed_chars)

    processed_percent = round((processed_chars / total_chars * 100) if total_chars else 100.0, 2)
    unprocessed_percent = round(max(0.0, 100.0 - processed_percent), 2)

    return {
        "total_chunks": total_chunks,
        "processed_chunks": processed_chunks,
        "pending_chunks": pending_chunks,
        "total_chars": total_chars,
        "processed_chars": processed_chars,
        "unprocessed_chars": unprocessed_chars,
        "processed_percent": processed_percent,
        "unprocessed_percent": unprocessed_percent,
    }


def _coerce_optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_text_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _sanitize_extracted_items(items: list[dict], *, source_chunk_id: str, fallback_start_line: int, fallback_end_line: int) -> list[dict]:
    sanitized: list[dict] = []

    for raw in items or []:
        if not isinstance(raw, dict):
            continue

        item_type = str(raw.get("type", "")).strip().lower()
        if item_type not in {"rule", "doc"}:
            continue

        category = str(raw.get("category", "")).strip()
        title = str(raw.get("title", "")).strip()
        content = str(raw.get("content", "")).strip()
        if not category or not title or not content:
            continue

        source_quote = str(raw.get("source_quote") or "").strip() or content
        source_start_line = _coerce_optional_int(raw.get("source_start_line")) or fallback_start_line
        source_end_line = _coerce_optional_int(raw.get("source_end_line")) or source_start_line
        if source_end_line < source_start_line:
            source_end_line = source_start_line

        sanitized.append(
            {
                "type": item_type,
                "category": category,
                "title": title,
                "content": content,
                "context": raw.get("context"),
                "evidence": raw.get("evidence"),
                "confidence": _coerce_optional_float(raw.get("confidence")),
                "decay": _coerce_optional_float(raw.get("decay")),
                "confidence_reasoning": raw.get("confidence_reasoning"),
                "decay_reasoning": raw.get("decay_reasoning"),
                "source_quote": source_quote,
                "source_start_line": source_start_line,
                "source_end_line": source_end_line,
                "source_chunk_id": source_chunk_id,
            }
        )

    return sanitized


def _dedupe_extracted_items(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple] = set()
    for item in items:
        key = (
            item.get("type", "rule"),
            _normalize_text_key(item.get("category", "")),
            _normalize_text_key(item.get("title", "")),
            _normalize_text_key(item.get("content", "")),
            item.get("source_start_line"),
            item.get("source_end_line"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_items_with_llm(provider, content: str, expected_count: int) -> list[dict]:
    prompt = PARSE_UNSTRUCTURED_PROMPT.format(content=content, expected_count=max(1, expected_count))
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=get_llm_model_for_feature("knowledge_parse_unstructured"),
        response_format=get_schema(_knowledge_item_schema()),
    )

    if not response:
        raise ValueError("LLM returned empty response")

    parsed = json.loads(response)
    items = parsed.get("items", [])
    if not isinstance(items, list):
        raise ValueError("LLM response did not include an items list")
    return items


def _metadata_key(item: dict) -> tuple:
    return (
        _normalize_text_key(item.get("type", "")),
        _normalize_text_key(item.get("category", "")),
        _normalize_text_key(item.get("title", "")),
        _normalize_text_key(item.get("content", "")),
    )


def _knowledge_item_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["rule", "doc"]},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "context": {"type": ["string", "null"]},
                        "evidence": {"type": ["string", "null"]},
                        "confidence": {"type": ["number", "null"]},
                        "decay": {"type": ["number", "null"]},
                        "confidence_reasoning": {"type": ["string", "null"]},
                        "decay_reasoning": {"type": ["string", "null"]},
                        "source_quote": {"type": ["string", "null"]},
                        "source_start_line": {"type": ["integer", "null"]},
                        "source_end_line": {"type": ["integer", "null"]},
                    },
                    "required": ["type", "category", "title", "content"],
                },
            }
        },
        "required": ["items"],
    }


def _normalize_items(
    items: list[dict],
    *,
    source_file: str,
    timestamp: str,
    preserved_metadata: dict[tuple, dict] | None = None,
) -> tuple[list[dict], list[str]]:
    normalized_items = []
    newly_added_ids = []

    for item in items:
        normalized = dict(item)
        existing_meta = (preserved_metadata or {}).get(_metadata_key(normalized), {})
        normalized["item_id"] = str(uuid.uuid4())
        normalized["source_file"] = source_file
        normalized["usage_count"] = int(existing_meta.get("usage_count", normalized.get("usage_count", 0) or 0))
        normalized["is_favorite"] = bool(existing_meta.get("is_favorite", normalized.get("is_favorite", False)))
        normalized["is_strict"] = bool(existing_meta.get("is_strict", normalized.get("is_strict", False)))
        normalized["is_testable"] = bool(existing_meta.get("is_testable", normalized.get("is_testable", False)))
        normalized["created_at"] = existing_meta.get("created_at") or timestamp
        confidence = _coerce_optional_float(normalized.get("confidence"))
        decay = _coerce_optional_float(normalized.get("decay"))
        if confidence is not None:
            normalized["confidence"] = confidence
        else:
            normalized.pop("confidence", None)
        if decay is not None:
            normalized["decay"] = decay
        else:
            normalized.pop("decay", None)
        normalized["source_quote"] = str(normalized.get("source_quote") or normalized.get("content") or "").strip()
        normalized["source_start_line"] = _coerce_optional_int(normalized.get("source_start_line"))
        normalized["source_end_line"] = _coerce_optional_int(normalized.get("source_end_line"))
        if normalized["source_start_line"] is None and normalized["source_end_line"] is not None:
            normalized["source_start_line"] = normalized["source_end_line"]
        if normalized["source_end_line"] is None and normalized["source_start_line"] is not None:
            normalized["source_end_line"] = normalized["source_start_line"]
        if (
            normalized["source_start_line"] is not None
            and normalized["source_end_line"] is not None
            and normalized["source_end_line"] < normalized["source_start_line"]
        ):
            normalized["source_end_line"] = normalized["source_start_line"]
        if normalized["source_start_line"] is None:
            normalized.pop("source_start_line", None)
        if normalized["source_end_line"] is None:
            normalized.pop("source_end_line", None)
        normalized_items.append(normalized)
        newly_added_ids.append(normalized["item_id"])

    return normalized_items, newly_added_ids


def _replace_items_for_source(kb: dict, source_file: str, new_items: list[dict]) -> int:
    existing_items = kb.get("items", [])
    replaced_count = sum(1 for item in existing_items if item.get("source_file") == source_file)
    kb["items"] = [item for item in existing_items if item.get("source_file") != source_file]
    kb["items"].extend(new_items)
    return replaced_count


def _preservation_index_for_source(kb: dict, source_file: str) -> dict[tuple, dict]:
    index: dict[tuple, dict] = {}
    for item in kb.get("items", []):
        if item.get("source_file") != source_file:
            continue
        index[_metadata_key(item)] = {
            "usage_count": item.get("usage_count", 0),
            "is_favorite": item.get("is_favorite", False),
            "is_strict": item.get("is_strict", False),
            "is_testable": item.get("is_testable", False),
            "created_at": item.get("created_at"),
        }
    return index


@knowledge_bp.route("/api/kb/files/unstructured/count", methods=["GET"])
def count_unstructured_files():
    try:
        root = get_project_root()
        unstructured_dir = root / ".zoro" / "rules" / "unstructured"

        if not unstructured_dir.exists():
            return jsonify(
                {
                    "success": True,
                    "files": [],
                    "total_pending": 0,
                    "total_pending_files": 0,
                    "total_pending_chunks": 0,
                    "total_unprocessed_percent": 0.0,
                }
            )

        processing_log = load_processing_log()
        processing_files = processing_log.get("files", {})
        files_info = []
        total_chars_all = 0
        total_unprocessed_chars = 0
        total_pending_chunks = 0

        for file_path in _iter_unstructured_markdown_files(unstructured_dir):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_name = _relative_unstructured_filename(unstructured_dir, file_path)
            log_entry = processing_files.get(file_name, {})
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunks = _build_content_chunks(content)
            processed_chunk_hashes = _resolve_processed_chunk_hashes(log_entry, content_hash, chunks)
            progress = _compute_progress(content, chunks, processed_chunk_hashes)

            total_chars_all += progress["total_chars"]
            total_unprocessed_chars += progress["unprocessed_chars"]
            total_pending_chunks += progress["pending_chunks"]

            files_info.append(
                {
                    "filename": file_name,
                    "total_items": progress["total_chunks"],  # backward-compatible alias
                    "processed": progress["processed_chunks"],  # backward-compatible alias
                    "pending": progress["pending_chunks"],  # backward-compatible alias
                    "total_chunks": progress["total_chunks"],
                    "processed_chunks": progress["processed_chunks"],
                    "pending_chunks": progress["pending_chunks"],
                    "total_chars": progress["total_chars"],
                    "processed_chars": progress["processed_chars"],
                    "unprocessed_chars": progress["unprocessed_chars"],
                    "processed_percent": progress["processed_percent"],
                    "unprocessed_percent": progress["unprocessed_percent"],
                    "is_processed": progress["pending_chunks"] == 0 and progress["total_chars"] > 0,
                    "path": str(file_path.relative_to(root).as_posix()),
                }
            )

        files_info.sort(key=lambda entry: entry["filename"])
        total_pending_files = sum(1 for file_info in files_info if file_info["pending_chunks"] > 0)
        total_unprocessed_percent = round(
            (total_unprocessed_chars / total_chars_all * 100) if total_chars_all else 0.0,
            2,
        )
        return jsonify(
            {
                "success": True,
                "files": files_info,
                "total_pending": total_pending_files,
                "total_pending_files": total_pending_files,
                "total_pending_chunks": total_pending_chunks,
                "total_unprocessed_percent": total_unprocessed_percent,
            }
        )
    except Exception as e:
        return handle_error("count_unstructured_files", e)


@knowledge_bp.route("/api/kb/process", methods=["POST"])
def process_unstructured():
    try:
        data = request.json or {}
        filenames = data.get("files", [])
        if not filenames:
            return jsonify({"success": False, "error": "No files specified"}), 400

        root = get_project_root()
        unstructured_dir = root / ".zoro" / "rules" / "unstructured"
        processed_dir = unstructured_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        provider = get_default_provider()
        kb = load_knowledge_base()
        processing_log = load_processing_log()
        processing_files = processing_log.setdefault("files", {})
        results = []

        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        for raw_filename in filenames:
            requested_name = str(raw_filename or "").strip().replace("\\", "/")
            file_path = _resolve_unstructured_file(unstructured_dir, requested_name)
            if not file_path:
                results.append({"filename": requested_name, "success": False, "error": "Invalid file path"})
                continue

            if not file_path.exists() or not file_path.is_file():
                results.append({"filename": requested_name, "success": False, "error": "File not found"})
                continue

            if processed_dir in file_path.parents:
                results.append({"filename": requested_name, "success": False, "error": "Files under processed/ are not eligible"})
                continue

            filename = _relative_unstructured_filename(unstructured_dir, file_path)
            if not filename.lower().endswith(".md"):
                results.append({"filename": filename, "success": False, "error": "Only .md files are supported"})
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunks = _build_content_chunks(content)
            total_chunks = len(chunks)
            log_entry = processing_files.get(filename, {})

            if total_chunks == 0:
                processing_files[filename] = {
                    "last_processed": datetime.now().isoformat(),
                    "content_hash": content_hash,
                    "source_path": str(file_path.relative_to(root)),
                    "items_processed": 0,
                    "total_chunks": 0,
                    "processed_chunk_hashes": [],
                    "processed_chunks": 0,
                    "pending_chunks": 0,
                    "total_chars": len(content),
                    "processed_chars": len(content),
                    "unprocessed_chars": 0,
                    "processed_percent": 100.0,
                    "unprocessed_percent": 0.0,
                    "runs": log_entry.get("runs", []),
                }
                results.append(
                    {
                        "filename": filename,
                        "success": True,
                        "items_added": 0,
                        "newly_added_ids": [],
                        "pre_count": 0,
                        "post_count": 0,
                        "parse_mode": "none",
                        "message": "File is empty",
                    }
                )
                continue

            prior_processed_hashes = _resolve_processed_chunk_hashes(log_entry, content_hash, chunks)
            pending_chunks = [chunk for chunk in chunks if chunk["chunk_id"] not in prior_processed_hashes]

            if not pending_chunks:
                progress = _compute_progress(content, chunks, prior_processed_hashes)
                results.append(
                    {
                        "filename": filename,
                        "success": True,
                        "items_added": 0,
                        "newly_added_ids": [],
                        "pre_count": 0,
                        "post_count": 0,
                        "parse_mode": "cached",
                        "message": "No new chunks to process",
                        "processed_percent": progress["processed_percent"],
                        "unprocessed_percent": progress["unprocessed_percent"],
                    }
                )
                continue

            try:
                parse_mode = "full_file" if len(content) <= FULL_FILE_MAX_CHARS else "chunked"
                logger.info(
                    "KB processing %s using %s mode (%s chunks pending of %s)",
                    filename,
                    parse_mode,
                    len(pending_chunks),
                    total_chunks,
                )

                extracted_items: list[dict] = []
                newly_extracted_count = 0
                processed_chunk_hashes = set(prior_processed_hashes)

                if parse_mode == "full_file":
                    raw_items = _extract_items_with_llm(provider, content, expected_count=total_chunks)
                    extracted_items = _sanitize_extracted_items(
                        raw_items,
                        source_chunk_id=f"full-file:{content_hash[:12]}",
                        fallback_start_line=1,
                        fallback_end_line=max(1, len(content.splitlines())),
                    )
                    newly_extracted_count = len(extracted_items)
                    processed_chunk_hashes = {chunk["chunk_id"] for chunk in chunks}
                else:
                    for chunk in pending_chunks:
                        raw_items = _extract_items_with_llm(provider, chunk["text"], expected_count=1)
                        chunk_items = _sanitize_extracted_items(
                            raw_items,
                            source_chunk_id=chunk["chunk_id"],
                            fallback_start_line=chunk["start_line"],
                            fallback_end_line=chunk["end_line"],
                        )
                        extracted_items.extend(chunk_items)
                        newly_extracted_count += len(chunk_items)
                        processed_chunk_hashes.add(chunk["chunk_id"])

                    if log_entry.get("content_hash") == content_hash and prior_processed_hashes:
                        retained_items = [
                            dict(item)
                            for item in kb.get("items", [])
                            if item.get("source_file") == filename
                            and str(item.get("source_chunk_id", "")) in prior_processed_hashes
                        ]
                        retained_items.extend(
                            dict(item)
                            for item in kb.get("items", [])
                            if item.get("source_file") == filename and not item.get("source_chunk_id")
                        )
                        extracted_items = retained_items + extracted_items

                extracted_items = _dedupe_extracted_items(extracted_items)
                timestamp = datetime.now().isoformat()
                preserved_metadata = _preservation_index_for_source(kb, filename)
                normalized_items, newly_added_ids = _normalize_items(
                    extracted_items,
                    source_file=filename,
                    timestamp=timestamp,
                    preserved_metadata=preserved_metadata,
                )
                replaced_previous_count = _replace_items_for_source(kb, filename, normalized_items)

                progress = _compute_progress(content, chunks, processed_chunk_hashes)
                processing_files[filename] = {
                    "last_processed": timestamp,
                    "content_hash": content_hash,
                    "source_path": str(file_path.relative_to(root)),
                    "items_processed": progress["processed_chunks"],  # backward-compatible alias
                    "total_chunks": progress["total_chunks"],
                    "processed_chunk_hashes": sorted(processed_chunk_hashes),
                    "processed_chunks": progress["processed_chunks"],
                    "pending_chunks": progress["pending_chunks"],
                    "total_chars": progress["total_chars"],
                    "processed_chars": progress["processed_chars"],
                    "unprocessed_chars": progress["unprocessed_chars"],
                    "processed_percent": progress["processed_percent"],
                    "unprocessed_percent": progress["unprocessed_percent"],
                    "runs": log_entry.get("runs", [])
                    + [
                        {
                            "timestamp": timestamp,
                            "parse_mode": parse_mode,
                            "chunks_processed": len(pending_chunks) if parse_mode == "chunked" else total_chunks,
                            "items_added": newly_extracted_count,
                            "replaced_previous_count": replaced_previous_count,
                        }
                    ],
                }

                processed_filename = _processed_snapshot_name(filename, timestamp_str)
                processed_path = processed_dir / processed_filename
                shutil.copy(file_path, processed_path)

                results.append(
                    {
                        "filename": filename,
                        "success": True,
                        "items_added": newly_extracted_count,
                        "newly_added_ids": newly_added_ids,
                        "pre_count": len(pending_chunks) if parse_mode == "chunked" else total_chunks,
                        "post_count": len(normalized_items),
                        "parse_mode": parse_mode,
                        "replaced_previous_count": replaced_previous_count,
                        "processed_percent": progress["processed_percent"],
                        "unprocessed_percent": progress["unprocessed_percent"],
                        "processed_path": str(processed_path.relative_to(root)),
                    }
                )
            except Exception as file_error:
                logger.warning("Failed to process %s: %s", filename, file_error, exc_info=True)
                results.append({"filename": filename, "success": False, "error": str(file_error)})

        save_knowledge_base(kb)
        save_processing_log(processing_log)

        all_newly_added_ids = []
        for result in results:
            if result.get("success") and "newly_added_ids" in result:
                all_newly_added_ids.extend(result["newly_added_ids"])

        return jsonify(
            {
                "success": True,
                "results": results,
                "total_added": sum(r.get("items_added", 0) for r in results),
                "newly_added_ids": all_newly_added_ids,
            }
        )
    except Exception as e:
        return handle_error("process_unstructured", e)


@knowledge_bp.route("/api/kb/files/import-agents", methods=["POST"])
def import_repo_agents():
    try:
        data = request.json or {}
        filename = (data.get("filename") or "AGENTS.md").strip() or "AGENTS.md"

        root = get_project_root()
        source_path = root / filename
        if not source_path.exists():
            return jsonify({"success": False, "error": f"{filename} not found at repository root"}), 404

        content = source_path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        source_key = f"repo:{filename}"

        processing_log = load_processing_log()
        log_entry = processing_log["files"].get(source_key, {})
        if log_entry.get("content_hash") == content_hash:
            return jsonify(
                {
                    "success": True,
                    "filename": filename,
                    "items_added": 0,
                    "newly_added_ids": [],
                    "message": f"{filename} is already up to date in Rules Management",
                }
            )

        provider = get_default_provider()
        prompt = PARSE_REPO_INSTRUCTIONS_PROMPT.format(content=content)
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_llm_model_for_feature("knowledge_parse_repo_instructions"),
            response_format=get_schema(_knowledge_item_schema()),
        )

        if not response:
            return jsonify({"success": False, "error": f"LLM returned empty response for {filename}"}), 500

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as e:
            return jsonify({"success": False, "error": f"Invalid JSON from LLM: {str(e)}"}), 500

        raw_items = parsed.get("items", [])
        if not isinstance(raw_items, list):
            return jsonify({"success": False, "error": "LLM response did not include an items array"}), 500

        sanitized_items = _sanitize_extracted_items(
            raw_items,
            source_chunk_id=f"repo-file:{source_key}",
            fallback_start_line=1,
            fallback_end_line=max(1, len(content.splitlines())),
        )
        deduped_items = _dedupe_extracted_items(sanitized_items)

        kb = load_knowledge_base()
        preserved_metadata = _preservation_index_for_source(kb, source_key)
        timestamp = datetime.now().isoformat()
        items, newly_added_ids = _normalize_items(
            deduped_items,
            source_file=source_key,
            timestamp=timestamp,
            preserved_metadata=preserved_metadata,
        )
        replaced_count = _replace_items_for_source(kb, source_key, items)
        save_knowledge_base(kb)

        processed_dir = root / ".zoro" / "rules" / "unstructured" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        processed_filename = f"repo_{source_path.stem}_{timestamp_str}.md"
        processed_path = processed_dir / processed_filename
        processed_path.write_text(content, encoding="utf-8")

        repo_progress = {
            "total_chunks": 1,
            "processed_chunks": 1,
            "pending_chunks": 0,
            "total_chars": len(content),
            "processed_chars": len(content),
            "unprocessed_chars": 0,
            "processed_percent": 100.0,
            "unprocessed_percent": 0.0,
        }

        processing_log["files"][source_key] = {
            "last_processed": timestamp,
            "content_hash": content_hash,
            "source_path": str(source_path.relative_to(root)),
            "items_processed": repo_progress["processed_chunks"],  # backward-compatible alias
            "total_chunks": repo_progress["total_chunks"],
            "processed_chunk_hashes": [f"repo-file:{source_key}"],
            "processed_chunks": repo_progress["processed_chunks"],
            "pending_chunks": repo_progress["pending_chunks"],
            "total_chars": repo_progress["total_chars"],
            "processed_chars": repo_progress["processed_chars"],
            "unprocessed_chars": repo_progress["unprocessed_chars"],
            "processed_percent": repo_progress["processed_percent"],
            "unprocessed_percent": repo_progress["unprocessed_percent"],
            "runs": log_entry.get("runs", [])
            + [
                {
                    "timestamp": timestamp,
                    "parse_mode": "repo_file",
                    "chunks_processed": 1,
                    "items_added": len(items),
                    "replaced_previous_count": replaced_count,
                }
            ],
        }
        save_processing_log(processing_log)

        return jsonify(
            {
                "success": True,
                "filename": filename,
                "items_added": len(items),
                "newly_added_ids": newly_added_ids,
                "replaced_previous_count": replaced_count,
                "processed_path": str(processed_path.relative_to(root)),
                "message": f"Structured {filename} directly from the repository root",
            }
        )
    except Exception as e:
        return handle_error("import_repo_agents", e)
