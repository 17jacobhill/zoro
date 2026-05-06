from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

from backend.globals.models import get_default_provider
from backend.utils import get_project_root, strip_markdown_json, get_llm_model_for_feature
from backend.visualization.prompts.plan_extraction import (
    PLAN_EXTRACTION_PROMPT,
    POPULATE_RULES_PROMPT,
    REFINE_SUBSTEPS_PROMPT,
)
from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.plan_persistence import (
    load_plan_document,
    normalize_plan_document,
    save_plan_document,
)
from backend.visualization.services.rule_learning_agent import _parse_codex_jsonl_messages
from backend.visualization.services.visualization_manager import (
    _delete_item_recursive,
    _find_item_in_tree,
    _recalculate_inherited_rules,
    _renumber_items,
)

from .common import handle_error, logger, visualization_bp


def _load_plan_or_404(chat_id: str):
    plan_data = load_plan_document(chat_id)
    if not plan_data:
        return None, (jsonify({"success": False, "error": "Plan not found"}), 404)
    return plan_data, None


def _load_rule_retrieval_items(rule_retrieval_source: str) -> list[dict]:
    all_rules = []

    if rule_retrieval_source == "structured":
        structured_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
        if structured_path.exists():
            with open(structured_path, "r", encoding="utf-8") as f:
                kb_data = json.load(f)
            all_rules.extend(kb_data.get("items", []))
    elif rule_retrieval_source == "unstructured":
        unstructured_dir = get_project_root() / ".zoro" / "rules" / "unstructured"
        if unstructured_dir.exists():
            processed_dir = unstructured_dir / "processed"
            rule_files = [
                path for path in unstructured_dir.rglob("*.md")
                if path.is_file() and processed_dir not in path.parents
            ]
            for rule_file in sorted(rule_files):
                with open(rule_file, "r", encoding="utf-8") as f:
                    content = f.read()
                source_file = rule_file.relative_to(unstructured_dir).as_posix()
                all_rules.append({"source_file": source_file, "content": content, "rule": content})

    return all_rules


def _format_rules_for_prompt(all_rules: list[dict], rule_retrieval_source: str) -> str:
    formatted_rules = []

    for rule in all_rules:
        if rule_retrieval_source == "structured":
            formatted_rules.append(f"## KB Item ID: {rule.get('item_id', '')}")
            formatted_rules.append(f"## Category: {rule.get('category', 'uncategorized')}")
            formatted_rules.append(f"**Rule:** {rule.get('content') or rule.get('title', '')}")
            if rule.get("context"):
                formatted_rules.append(f"**Context:** {rule['context']}")
            if rule.get("evidence"):
                formatted_rules.append(f"**Evidence:** {rule['evidence']}")
            formatted_rules.append(f"**Favorite:** {str(bool(rule.get('is_favorite', False))).lower()}")
            formatted_rules.append(f"**Strict:** {str(bool(rule.get('is_strict', False))).lower()}")
            if rule.get("confidence") is not None:
                formatted_rules.append(f"**Confidence:** {rule['confidence']}")
            if rule.get("decay") is not None:
                formatted_rules.append(f"**Decay:** {rule['decay']}")
            formatted_rules.append("")
        else:
            formatted_rules.append(rule.get("content", rule.get("rule", "")))

    return "\n".join(formatted_rules)


def _deduplicate_rules_in_hierarchy(items, ancestor_rules=None):
    if ancestor_rules is None:
        ancestor_rules = set()

    for item in items:
        item_rules = item.get("rules", [])
        unique_rules = []

        for rule in item_rules:
            rule_key = (rule.get("category", ""), rule.get("text", ""))
            if rule_key not in ancestor_rules:
                unique_rules.append(rule)

        item["rules"] = unique_rules

        child_ancestor_rules = ancestor_rules.copy()
        for rule in unique_rules:
            rule_key = (rule.get("category", ""), rule.get("text", ""))
            child_ancestor_rules.add(rule_key)

        if item.get("children"):
            _deduplicate_rules_in_hierarchy(item["children"], child_ancestor_rules)


def _populate_inherited_rules(items, parent_rules=None):
    if parent_rules is None:
        parent_rules = []

    for item in items:
        inherited_rules = []
        for rule, source in parent_rules:
            inherited_rules.append({"rule": dict(rule), "source": source})
        item["inherited_rules"] = inherited_rules

        if item.get("children"):
            child_parent_rules = list(parent_rules)
            for rule in item.get("rules", []):
                child_parent_rules.append((rule, item.get("title", "Unknown")))
            _populate_inherited_rules(item["children"], child_parent_rules)


def _normalize_rule_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _find_matching_kb_item(rule, kb_items, kb_dict):
    kb_id = rule.get("kb_item_id")
    if kb_id and kb_id in kb_dict:
        return kb_dict[kb_id]

    rule_text = _normalize_rule_text(rule.get("text", ""))
    if not rule_text:
        return None

    for kb_item in kb_items:
        kb_content = _normalize_rule_text(kb_item.get("content", ""))
        kb_title = _normalize_rule_text(kb_item.get("title", ""))
        if rule_text == kb_content or (kb_title and rule_text == kb_title):
            return kb_item
    return None


def _sync_rule_with_kb(rule, kb_item):
    rule["kb_item_id"] = kb_item.get("item_id")
    rule["category"] = kb_item.get("category", rule.get("category", "uncategorized"))
    rule["text"] = kb_item.get("content") or kb_item.get("title", rule.get("text", ""))
    rule["context"] = kb_item.get("context", "")
    rule["evidence"] = kb_item.get("evidence", "")
    rule["confidence"] = kb_item.get("confidence", 0.5)
    rule["decay"] = kb_item.get("decay", 0.5)
    rule["confidence_reasoning"] = kb_item.get("confidence_reasoning", "")
    rule["decay_reasoning"] = kb_item.get("decay_reasoning", "")
    rule["needs_strict_enforcement"] = kb_item.get("is_strict", False)
    rule["is_testable"] = kb_item.get("is_testable", False)


def _canonicalize_rules_from_kb(items, kb_items, kb_dict):
    for item in items:
        for rule in item.get("rules", []):
            kb_item = _find_matching_kb_item(rule, kb_items, kb_dict)
            if kb_item:
                _sync_rule_with_kb(rule, kb_item)

        if item.get("children"):
            _canonicalize_rules_from_kb(item["children"], kb_items, kb_dict)


def _prune_non_kb_rules(items, kb_items, kb_dict):
    for item in items:
        kept_rules = []
        for rule in item.get("rules", []):
            kb_item = _find_matching_kb_item(rule, kb_items, kb_dict)
            if not kb_item:
                continue
            _sync_rule_with_kb(rule, kb_item)
            kept_rules.append(rule)
        item["rules"] = kept_rules

        if item.get("children"):
            _prune_non_kb_rules(item["children"], kb_items, kb_dict)


def _collect_item_ids(item: dict) -> list[str]:
    ids = [item.get("id")] if item.get("id") else []
    for child in item.get("children", []):
        ids.extend(_collect_item_ids(child))
    return ids


def _find_item_with_siblings(items: list[dict], item_id: str):
    for idx, item in enumerate(items):
        if item.get("id") == item_id:
            return item, items, idx

        children = item.get("children", [])
        if children:
            found_item, found_siblings, found_idx = _find_item_with_siblings(children, item_id)
            if found_item:
                return found_item, found_siblings, found_idx

    return None, None, -1


_ROLE_LINE_RE = re.compile(r"^\s*(user|assistant|system)\s*:\s?(.*)$", re.IGNORECASE)
_PLAN_STRUCTURE_RE = re.compile(
    r"^\s*(#{1,6}\s+\S+|\d+[.)]\s+\S+|-\s+\[[ xX]\]|-\s+\S+|\*\*[^*]+:\*\*)"
)
_PLAN_KEYWORDS = (
    "plan",
    "implementation changes",
    "test plan",
    "assumptions",
    "steps",
    "checklist",
    "summary",
)


def _extract_text_from_message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", ""))
        if block_type in {"text", "input_text", "output_text"}:
            text = str(block.get("text", "")).strip()
            if text:
                parts.append(text)
        elif block_type == "thinking":
            thinking = str(block.get("thinking", "")).strip()
            if thinking:
                parts.append(thinking)
    return "\n".join(parts).strip()


def _load_chat_messages(chat_file_path: str) -> list[dict]:
    if not chat_file_path:
        return []

    path = Path(chat_file_path)
    if not path.exists():
        return []

    try:
        raw_content = path.read_text(encoding="utf-8")
    except OSError:
        return []

    try:
        if path.suffix.lower() == ".jsonl":
            messages = _parse_codex_jsonl_messages(raw_content)
        else:
            payload = json.loads(raw_content)
            if isinstance(payload, list):
                messages = payload
            elif isinstance(payload, dict):
                messages = payload.get("messages", [])
            else:
                messages = []
    except (json.JSONDecodeError, ValueError):
        return []

    normalized = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).lower().strip()
        if role not in {"user", "assistant", "system"}:
            continue
        text = _extract_text_from_message_content(message.get("content", ""))
        if not text:
            continue
        normalized.append({"role": role, "content": text})

    return normalized


def _messages_to_transcript(messages: list[dict]) -> str:
    return "\n\n".join(
        f"{message['role']}: {message['content']}"
        for message in messages
        if message.get("content")
    ).strip()


def _split_role_blocks(content: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_role: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        match = _ROLE_LINE_RE.match(line)
        if match:
            if current_role and current_lines:
                block_text = "\n".join(current_lines).strip()
                if block_text:
                    blocks.append((current_role, block_text))
            current_role = match.group(1).lower()
            current_lines = [match.group(2)]
            continue

        if current_role is None:
            continue
        current_lines.append(line)

    if current_role and current_lines:
        block_text = "\n".join(current_lines).strip()
        if block_text:
            blocks.append((current_role, block_text))

    return blocks


def _looks_like_plan_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 40:
        return False

    lowered = stripped.lower()
    keyword_hits = sum(1 for keyword in _PLAN_KEYWORDS if keyword in lowered)
    structured_lines = sum(
        1 for line in stripped.splitlines() if line.strip() and _PLAN_STRUCTURE_RE.match(line.strip())
    )
    numbered_steps = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S+", stripped))
    checklist_lines = len(re.findall(r"(?m)^\s*-\s+\[[ xX]\]\s+", stripped))

    if numbered_steps >= 2:
        return True
    if checklist_lines >= 3:
        return True
    if keyword_hits >= 1 and structured_lines >= 2:
        return True
    return False


def _select_latest_plan_candidate(content: str) -> tuple[str, bool]:
    blocks = _split_role_blocks(content)
    for role, block_text in reversed(blocks):
        if role == "assistant" and _looks_like_plan_text(block_text):
            return block_text, True

    if _looks_like_plan_text(content):
        return content, True

    return content, False


def _load_content_from_chat_file(metadata: dict) -> str:
    chat_file_path = str((metadata or {}).get("chat_file_path", "")).strip()
    if not chat_file_path:
        return ""

    messages = _load_chat_messages(chat_file_path)
    return _messages_to_transcript(messages)


def _count_attached_rules(items: list[dict]) -> int:
    total = 0
    for item in items or []:
        rules = item.get("rules", [])
        if isinstance(rules, list):
            total += len(rules)
        inherited_rules = item.get("inherited_rules", [])
        if isinstance(inherited_rules, list):
            total += len(inherited_rules)
        children = item.get("children", [])
        if isinstance(children, list) and children:
            total += _count_attached_rules(children)
    return total


def _plan_has_items(plan_data: dict | None) -> bool:
    if not isinstance(plan_data, dict):
        return False
    items = plan_data.get("plan", {}).get("items", [])
    return isinstance(items, list) and len(items) > 0


def _resolve_visualization_content(chat_id: str, data: dict):
    manual_content = (data or {}).get("content")
    metadata = vm.get_visualization(chat_id)
    if not metadata:
        return None, None, jsonify({"error": "Visualization not found"}), 404

    if manual_content:
        return metadata, manual_content, None, None

    content = metadata.get("cleaned_accumulated_content", "")
    if not content:
        content = _load_content_from_chat_file(metadata)
    if not content:
        return metadata, None, jsonify({"error": "No chat content available"}), 400

    return metadata, content, None, None


def _extract_plan_from_content(content: str) -> dict:
    prompt = PLAN_EXTRACTION_PROMPT.format(content=content)
    provider = get_default_provider()
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=get_llm_model_for_feature("plan_extraction"),
    )
    return normalize_plan_document(json.loads(strip_markdown_json(response)))


def _enrich_plan_for_chat(chat_id: str, metadata: dict, plan_data: dict):
    rule_retrieval_source = metadata.get("rule_retrieval_source", "structured")
    all_rules = _load_rule_retrieval_items(rule_retrieval_source)
    if not all_rules:
        return plan_data, False, f"No rules found for source '{rule_retrieval_source}'"

    prompt = POPULATE_RULES_PROMPT.format(
        plan_json=json.dumps(plan_data, indent=2),
        rules_content=_format_rules_for_prompt(all_rules, rule_retrieval_source),
    )

    provider = get_default_provider()
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=get_llm_model_for_feature("plan_enrichment"),
    )
    enhanced_plan = normalize_plan_document(json.loads(strip_markdown_json(response)))

    plan_items = enhanced_plan.get("plan", {}).get("items", [])
    if rule_retrieval_source == "structured":
        kb_dict = {item["item_id"]: item for item in all_rules if item.get("item_id")}
        _prune_non_kb_rules(plan_items, all_rules, kb_dict)
        _canonicalize_rules_from_kb(plan_items, all_rules, kb_dict)

    _deduplicate_rules_in_hierarchy(plan_items)
    _populate_inherited_rules(plan_items)
    return enhanced_plan, True, None


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan", methods=["GET"])
def get_plan(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Started")
        plan = load_plan_document(chat_id)
        if not plan:
            logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Not Found")
            return jsonify({"success": False, "plan": None})

        logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Success")
        return jsonify({"success": True, "plan": plan})
    except Exception as e:
        return handle_error("get_plan", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan", methods=["PUT"])
def update_plan_metadata(chat_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan - Started")
        data = request.json or {}
        title = data.get("title")
        description = data.get("description")

        if title is None and description is None:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        plan_dict = plan_data.get("plan", {})
        if title is not None:
            plan_dict["title"] = str(title).strip()
        if description is not None:
            plan_dict["description"] = str(description)
        plan_data["plan"] = plan_dict

        save_plan_document(chat_id, plan_data)
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan - Success")
        return jsonify({"success": True, "plan": plan_data})
    except Exception as e:
        return handle_error("update_plan_metadata", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/extract-plan", methods=["POST"])
def extract_plan(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/extract-plan - Started")

        data = request.json or {}
        metadata, content, error_response, status_code = _resolve_visualization_content(chat_id, data)
        if error_response:
            return error_response, status_code

        extraction_content, detected = _select_latest_plan_candidate(content)
        logger.info(
            f"Using content ({len(content)} characters) for extraction "
            f"(candidate={len(extraction_content)}, detected={detected})"
        )
        result = _extract_plan_from_content(extraction_content)

        plan_path = save_plan_document(chat_id, result)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/extract-plan - Success")
        return jsonify(
            {
                "success": True,
                "plan": result,
                "file_path": str(plan_path),
                "plan_detected": detected,
            }
        )
    except Exception as e:
        return handle_error("extract_plan", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/retrieve-rules", methods=["POST"])
def retrieve_rules_for_plan(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/retrieve-rules - Started")

        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        enhanced_plan, _, enrich_error = _enrich_plan_for_chat(chat_id, metadata, plan_data)
        if enrich_error:
            return jsonify({"success": False, "error": enrich_error}), 404

        save_plan_document(chat_id, enhanced_plan)
        logger.info(f"POST /api/chat-visualizations/{chat_id}/retrieve-rules - Success")
        return jsonify({"success": True, "plan": enhanced_plan})
    except Exception as e:
        return handle_error("retrieve_rules_for_plan", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/bootstrap-plan", methods=["POST"])
def bootstrap_plan(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/bootstrap-plan - Started")

        data = request.json or {}
        metadata, content, error_response, status_code = _resolve_visualization_content(chat_id, data)
        if error_response:
            return error_response, status_code

        extraction_content, detected = _select_latest_plan_candidate(content)
        logger.info(
            f"Using content ({len(content)} characters) for extraction + enrichment "
            f"(candidate={len(extraction_content)}, detected={detected})"
        )
        extracted_plan = _extract_plan_from_content(extraction_content)
        final_plan, rules_applied, enrich_error = _enrich_plan_for_chat(chat_id, metadata, extracted_plan)

        plan_path = save_plan_document(chat_id, final_plan)
        warnings = [enrich_error] if enrich_error else []
        rules_attached_count = _count_attached_rules(final_plan.get("plan", {}).get("items", []))
        rule_retrieval_source = metadata.get("rule_retrieval_source", "structured")

        logger.info(
            f"POST /api/chat-visualizations/{chat_id}/bootstrap-plan - Success "
            f"(rules_applied={rules_applied}, rules_attached={rules_attached_count})"
        )
        return jsonify(
            {
                "success": True,
                "plan": final_plan,
                "rules_applied": rules_applied,
                "rules_attached_count": rules_attached_count,
                "rule_retrieval_source": rule_retrieval_source,
                "warnings": warnings,
                "file_path": str(plan_path),
                "plan_detected": detected,
            }
        )
    except Exception as e:
        return handle_error("bootstrap_plan", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/prepare-play", methods=["POST"])
def prepare_plan_for_play(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/prepare-play - Started")

        data = request.json or {}
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        existing_plan = load_plan_document(chat_id)
        final_plan = existing_plan
        plan_detected = _plan_has_items(existing_plan)
        play_action = "sync_chat_only"
        enrich_error = None

        if not plan_detected:
            metadata, content, error_response, status_code = _resolve_visualization_content(chat_id, data)
            if error_response:
                return error_response, status_code

            extraction_content, plan_detected = _select_latest_plan_candidate(content)
            logger.info(
                f"prepare-play extracting from {len(content)} characters "
                f"(candidate={len(extraction_content)}, detected={plan_detected})"
            )
            extracted_plan = _extract_plan_from_content(extraction_content)
            final_plan, _, enrich_error = _enrich_plan_for_chat(chat_id, metadata, extracted_plan)
            play_action = "extract_plan"
        else:
            attached_before = _count_attached_rules(existing_plan.get("plan", {}).get("items", []))
            if attached_before == 0:
                final_plan, _, enrich_error = _enrich_plan_for_chat(chat_id, metadata, existing_plan)
                play_action = "enrich_plan"

        if final_plan is None:
            final_plan = normalize_plan_document({"plan": {"items": []}})

        plan_detected = _plan_has_items(final_plan)
        plan_path = save_plan_document(chat_id, final_plan)
        rules_attached_count = _count_attached_rules(final_plan.get("plan", {}).get("items", []))
        rules_applied = rules_attached_count > 0
        warnings = [enrich_error] if enrich_error else []
        rule_retrieval_source = metadata.get("rule_retrieval_source", "structured")

        logger.info(
            f"POST /api/chat-visualizations/{chat_id}/prepare-play - Success "
            f"(action={play_action}, rules_attached={rules_attached_count})"
        )
        return jsonify(
            {
                "success": True,
                "plan": final_plan,
                "play_action": play_action,
                "plan_detected": plan_detected,
                "rules_applied": rules_applied,
                "rules_attached_count": rules_attached_count,
                "rule_retrieval_source": rule_retrieval_source,
                "warnings": warnings,
                "file_path": str(plan_path),
            }
        )
    except Exception as e:
        return handle_error("prepare_plan_for_play", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>/refine-substeps", methods=["POST"])
def refine_substeps(chat_id, item_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/refine-substeps - Started")

        data = request.json or {}
        user_guidance = data.get("guidance", "").strip()
        if not user_guidance:
            return jsonify({"success": False, "error": "Guidance is required"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        phase, _, _ = _find_item_in_tree(items, item_id)
        if not phase:
            return jsonify({"success": False, "error": "Item not found"}), 404

        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        rule_retrieval_source = metadata.get("rule_retrieval_source", "structured")
        all_rules = _load_rule_retrieval_items(rule_retrieval_source)

        prompt = REFINE_SUBSTEPS_PROMPT.format(
            user_guidance=user_guidance,
            phase_json=json.dumps(phase, indent=2),
            kb_rules=_format_rules_for_prompt(all_rules, rule_retrieval_source),
        )

        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_llm_model_for_feature("plan_refine_substeps"),
        )
        enhanced_phase = json.loads(strip_markdown_json(response))

        phase["children"] = enhanced_phase.get("children", [])
        phase["rules"] = enhanced_phase.get("rules", [])

        if rule_retrieval_source == "structured":
            kb_dict = {item["item_id"]: item for item in all_rules if item.get("item_id")}
            children = phase.get("children", [])
            _prune_non_kb_rules([phase] + children, all_rules, kb_dict)
            _canonicalize_rules_from_kb([phase] + children, all_rules, kb_dict)

        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/refine-substeps - Success")
        return jsonify({"success": True, "phase": phase})
    except Exception as e:
        return handle_error("refine_substeps", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/resolve-conflict", methods=["POST"])
def resolve_conflict(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/resolve-conflict - Started")

        data = request.json or {}
        item_id = data.get("item_id")
        conflict_id = data.get("conflict_id")
        chosen_rule_index = data.get("chosen_rule_index")

        if not item_id or not conflict_id or chosen_rule_index is None:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        def find_and_resolve_conflict(items):
            for item in items:
                if item.get("id") == item_id:
                    conflicts = item.get("conflicts", [])
                    conflict = None

                    for candidate in conflicts:
                        if candidate.get("conflict_id") == conflict_id:
                            conflict = candidate
                            break

                    if not conflict:
                        return {"error": "Conflict not found"}

                    conflict["resolved"] = True
                    conflict["chosen_rule_index"] = chosen_rule_index
                    conflict["resolved_at"] = datetime.now().isoformat()

                    rule_indices = conflict.get("rule_indices", {}).get(item_id, [])
                    if chosen_rule_index not in rule_indices:
                        return {"error": f"Chosen rule index {chosen_rule_index} not in conflict"}

                    rules = item.get("rules", [])
                    indices_to_remove = sorted((idx for idx in rule_indices if idx != chosen_rule_index), reverse=True)
                    for idx in indices_to_remove:
                        if idx < len(rules):
                            rules.pop(idx)

                    item["rules"] = rules
                    unresolved_count = sum(1 for c in conflicts if not c.get("resolved", False))
                    item["has_unresolved_conflicts"] = unresolved_count > 0
                    return {
                        "success": True,
                        "remaining_conflicts": unresolved_count,
                        "item_id": item_id,
                        "conflict_id": conflict_id,
                    }

                if item.get("children"):
                    result = find_and_resolve_conflict(item["children"])
                    if result:
                        return result

            return None

        items = plan_data.get("plan", {}).get("items", [])
        result = find_and_resolve_conflict(items)
        if not result:
            return jsonify({"success": False, "error": "Item not found"}), 404
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        save_plan_document(chat_id, plan_data)
        logger.info(f"POST /api/chat-visualizations/{chat_id}/resolve-conflict - Success")
        return jsonify(result)
    except Exception as e:
        return handle_error("resolve_conflict", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>", methods=["DELETE"])
def delete_plan_item(chat_id, item_id):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Started")

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        target_item, _, _ = _find_item_in_tree(items, item_id)
        if not target_item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        removed_ids = _collect_item_ids(target_item)
        if not _delete_item_recursive(items, item_id):
            return jsonify({"success": False, "error": "Item not found"}), 404

        _renumber_items(items)
        _recalculate_inherited_rules(items)

        metadata = vm.get_visualization(chat_id)
        if metadata:
            tracking = metadata.get("plan_tracking", {})
            changed = False
            for removed_id in removed_ids:
                if removed_id in tracking:
                    del tracking[removed_id]
                    changed = True
            if changed:
                metadata["plan_tracking"] = tracking
                vm._save_metadata(chat_id, metadata)

        save_plan_document(chat_id, plan_data)
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Success")
        return jsonify({"success": True})
    except Exception as e:
        return handle_error("delete_plan_item", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>", methods=["PUT"])
def update_plan_item(chat_id, item_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Started")

        data = request.json or {}
        title = data.get("title")
        description = data.get("description")
        if title is None and description is None:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        target_item, _, _ = _find_item_in_tree(items, item_id)
        if not target_item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        if title is not None:
            target_item["title"] = str(title).strip()
        if description is not None:
            target_item["description"] = str(description)

        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Success")
        return jsonify({"success": True, "item": target_item})
    except Exception as e:
        return handle_error("update_plan_item", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items", methods=["POST"])
def add_plan_item(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items - Started")

        data = request.json or {}
        parent_id = data.get("parent_id")
        title = data.get("title", "").strip()
        description = data.get("description", "")
        position = data.get("position")

        if not title:
            return jsonify({"success": False, "error": "Title is required"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        new_item = {
            "id": str(uuid.uuid4())[:8],
            "number": "",
            "title": title,
            "description": description,
            "children": [],
            "rules": [],
            "inherited_rules": [],
        }

        if parent_id:
            parent, _, _ = _find_item_in_tree(items, parent_id)
            if not parent:
                return jsonify({"success": False, "error": "Parent item not found"}), 404

            parent.setdefault("children", [])
            if position is not None and 0 <= position <= len(parent["children"]):
                parent["children"].insert(position, new_item)
            else:
                parent["children"].append(new_item)
        else:
            if position is not None and 0 <= position <= len(items):
                items.insert(position, new_item)
            else:
                items.append(new_item)

        _renumber_items(items)
        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items - Success (new item: {new_item['id']})")
        return jsonify({"success": True, "item": new_item})
    except Exception as e:
        return handle_error("add_plan_item", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>/move", methods=["POST"])
def move_plan_item(chat_id, item_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/move - Started")

        data = request.json or {}
        direction = data.get("direction")
        if direction not in ["up", "down"]:
            return jsonify({"success": False, "error": "Invalid direction"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        target_item, siblings, item_index = _find_item_with_siblings(items, item_id)
        if not target_item:
            return jsonify({"success": False, "error": "Item not found"}), 404
        if not siblings or item_index < 0:
            return jsonify({"success": False, "error": "Unable to resolve item ordering context"}), 500

        destination_index = item_index - 1 if direction == "up" else item_index + 1
        if destination_index < 0 or destination_index >= len(siblings):
            return jsonify({"success": False, "error": f"Cannot move item {direction}"}), 400

        siblings[item_index], siblings[destination_index] = siblings[destination_index], siblings[item_index]

        _renumber_items(items)
        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(
            f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/move - Success "
            f"({item_index} -> {destination_index})"
        )
        return jsonify(
            {
                "success": True,
                "item_id": item_id,
                "from_index": item_index,
                "to_index": destination_index,
            }
        )
    except Exception as e:
        return handle_error("move_plan_item", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>", methods=["DELETE"])
def delete_plan_item_rule(chat_id, item_id, rule_index):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index} - Started")

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        rules = item.get("rules", [])
        if rule_index < 0 or rule_index >= len(rules):
            return jsonify({"success": False, "error": "Rule index out of bounds"}), 400

        rules.pop(rule_index)
        item["rules"] = rules

        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index} - Success")
        return jsonify({"success": True})
    except Exception as e:
        return handle_error("delete_plan_item_rule", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules", methods=["POST"])
def add_plan_item_rule(chat_id, item_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules - Started")

        data = request.json or {}
        kb_item_id = data.get("kb_item_id")

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        if kb_item_id:
            kb_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if not kb_path.exists():
                return jsonify({"success": False, "error": "Knowledge base not found"}), 404

            with open(kb_path, "r", encoding="utf-8") as f:
                kb_data = json.load(f)
            kb_rule = next((candidate for candidate in kb_data.get("items", []) if candidate.get("item_id") == kb_item_id), None)
            if not kb_rule:
                return jsonify({"success": False, "error": "Rule not found in knowledge base"}), 404

            new_rule = {
                "category": kb_rule.get("category", "uncategorized"),
                "text": kb_rule.get("content") or kb_rule.get("title", ""),
                "context": kb_rule.get("context", ""),
                "evidence": kb_rule.get("evidence", ""),
                "confidence": kb_rule.get("confidence"),
                "decay": kb_rule.get("decay"),
                "confidence_reasoning": kb_rule.get("confidence_reasoning", ""),
                "decay_reasoning": kb_rule.get("decay_reasoning", ""),
                "kb_item_id": kb_item_id,
                "needs_strict_enforcement": kb_rule.get("is_strict", False),
                "is_testable": kb_rule.get("is_testable", False),
            }
        else:
            new_rule = {
                "category": data.get("category", "uncategorized"),
                "text": data.get("text", ""),
                "context": data.get("context", ""),
                "evidence": data.get("evidence", ""),
                "confidence": data.get("confidence"),
                "decay": data.get("decay"),
                "confidence_reasoning": data.get("confidence_reasoning", ""),
                "decay_reasoning": data.get("decay_reasoning", ""),
            }
            if not new_rule["text"]:
                return jsonify({"success": False, "error": "Rule text is required"}), 400

        item.setdefault("rules", []).append(new_rule)
        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules - Success")
        return jsonify({"success": True, "rule": new_rule})
    except Exception as e:
        return handle_error("add_plan_item_rule", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/move", methods=["POST"])
def move_plan_item_rule(chat_id, item_id, rule_index):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/move - Started")

        data = request.json or {}
        source_type = data.get("source_type", "own")
        direction = data.get("direction")
        target_item_id = data.get("target_item_id")

        if source_type not in ["own", "inherited"]:
            return jsonify({"success": False, "error": "Invalid source_type"}), 400
        if direction not in ["up", "down", "adopt"]:
            return jsonify({"success": False, "error": "Invalid direction"}), 400

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        item, parent, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        moved_rule = None
        destination_item = None

        if source_type == "own":
            rules = item.get("rules", [])
            if rule_index < 0 or rule_index >= len(rules):
                return jsonify({"success": False, "error": "Rule index out of bounds"}), 400

            moved_rule = rules.pop(rule_index)
            item["rules"] = rules

            if direction == "up":
                if not parent:
                    return jsonify({"success": False, "error": "Cannot move up: item has no parent"}), 400
                parent.setdefault("rules", []).append(moved_rule)
                destination_item = parent
            elif direction == "down":
                children = item.get("children", [])
                if not children:
                    return jsonify({"success": False, "error": "Cannot move down: item has no children"}), 400

                if target_item_id:
                    child = next((c for c in children if c.get("id") == target_item_id), None)
                    if not child:
                        return jsonify(
                            {"success": False, "error": "target_item_id must be a direct child of source item"}
                        ), 400
                    destination_item = child
                else:
                    if len(children) != 1:
                        return jsonify({"success": False, "error": "Multiple children found; target_item_id is required"}), 400
                    destination_item = children[0]

                destination_item.setdefault("rules", []).append(moved_rule)
            else:
                return jsonify({"success": False, "error": "Direction not supported for own rules"}), 400
        else:
            if direction != "adopt":
                return jsonify({"success": False, "error": "Inherited rules only support direction=adopt"}), 400

            inherited_rules = item.get("inherited_rules", [])
            if rule_index < 0 or rule_index >= len(inherited_rules):
                return jsonify({"success": False, "error": "Inherited rule index out of bounds"}), 400

            inherited_entry = inherited_rules[rule_index]
            moved_rule = dict(inherited_entry.get("rule", {}))
            destination_item = item
            item.setdefault("rules", []).append(moved_rule)

        _recalculate_inherited_rules(items)
        save_plan_document(chat_id, plan_data)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/move - Success")
        return jsonify(
            {
                "success": True,
                "moved_rule": moved_rule,
                "from_item_id": item_id,
                "to_item_id": destination_item.get("id") if destination_item else item_id,
            }
        )
    except Exception as e:
        return handle_error("move_plan_item_rule", e)


@visualization_bp.route(
    "/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/strict-enforcement",
    methods=["PUT"],
)
def toggle_rule_strict_enforcement_api(chat_id, item_id, rule_index):
    try:
        logger.info(
            f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - Started"
        )

        data = request.json or {}
        enabled = data.get("enabled", False)

        rule, error = vm.toggle_rule_strict_enforcement(chat_id, item_id, rule_index, enabled)
        if error:
            logger.info(
                f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - "
                f"Error: {error}"
            )
            return jsonify({"success": False, "error": error}), 404

        logger.info(
            f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - Success"
        )
        return jsonify({"success": True, "rule": rule})
    except Exception as e:
        return handle_error("toggle_rule_strict_enforcement", e)


@visualization_bp.route(
    "/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/testable",
    methods=["PUT"],
)
def toggle_rule_testable_api(chat_id, item_id, rule_index):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/testable - Started")

        data = request.json or {}
        enabled = data.get("enabled", False)

        plan_data, error_response = _load_plan_or_404(chat_id)
        if error_response:
            return error_response

        items = plan_data.get("plan", {}).get("items", [])
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        rules = item.get("rules", [])
        if rule_index < 0 or rule_index >= len(rules):
            return jsonify({"success": False, "error": "Rule index out of bounds"}), 400

        rules[rule_index]["is_testable"] = enabled
        save_plan_document(chat_id, plan_data)

        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/testable - Success")
        return jsonify({"success": True, "rule": rules[rule_index]})
    except Exception as e:
        return handle_error("toggle_rule_testable", e)
