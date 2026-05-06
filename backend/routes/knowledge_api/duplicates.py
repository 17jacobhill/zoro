from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from flask import jsonify, request

from backend.globals.models import get_default_provider
from backend.globals.schemas import get_schema
from backend.knowledge.services.storage import load_knowledge_base, save_knowledge_base
from backend.knowledge.prompts.duplicate_detection import BATCH_DUPLICATE_DETECTION_PROMPT
from backend.utils import get_llm_model_for_feature

from .common import handle_error, logger, knowledge_bp


@knowledge_bp.route("/api/kb/duplicates/detect", methods=["POST"])
def detect_duplicates():
    try:
        data = request.json or {}
        category = data.get("category")

        kb = load_knowledge_base()
        items = [item for item in kb["items"] if item["type"] == "rule"]
        if category:
            items = [item for item in items if item["category"] == category]

        if len(items) < 2:
            return jsonify({"success": True, "duplicates": []})

        items_by_category = defaultdict(list)
        for item in items:
            items_by_category[item["category"]].append(item)

        provider = get_default_provider()
        all_duplicates = []

        for cat_name, cat_items in items_by_category.items():
            if len(cat_items) < 2:
                continue

            prompt_items = []
            for item in cat_items:
                prompt_items.append(
                    {
                        "item_id": item["item_id"],
                        "title": item["title"],
                        "content": item["content"],
                        "confidence": item.get("confidence"),
                        "decay": item.get("decay"),
                    }
                )

            response = provider.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": BATCH_DUPLICATE_DETECTION_PROMPT.format(
                            category=cat_name,
                            items_list=json.dumps(prompt_items, indent=2),
                            items_json=json.dumps(prompt_items, indent=2),
                        ),
                    }
                ],
                model=get_llm_model_for_feature("knowledge_duplicate_detection"),
                response_format=get_schema(
                    {
                        "type": "object",
                        "properties": {
                            "groups": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "item_ids": {"type": "array", "items": {"type": "string"}},
                                        "similarity_score": {"type": ["number", "null"]},
                                        "reasoning": {"type": "string"},
                                        "merged_title": {"type": "string"},
                                        "merged_content": {"type": "string"},
                                        "merged_context": {"type": ["string", "null"]},
                                        "merged_evidence": {"type": ["string", "null"]},
                                        "merged_confidence": {"type": ["number", "null"]},
                                        "merged_decay": {"type": ["number", "null"]},
                                        "scoring_explanation": {"type": ["string", "null"]},
                                        "is_conflict": {"type": ["boolean", "null"]},
                                    },
                                    "required": ["item_ids", "reasoning", "merged_title", "merged_content"],
                                },
                            }
                        },
                        "required": ["groups"],
                    }
                ),
            )

            parsed = json.loads(response)
            groups = parsed.get("groups") or parsed.get("duplicate_groups") or []
            items_by_id = {item["item_id"]: item for item in cat_items}

            for group in groups:
                if len(group["item_ids"]) < 2:
                    continue
                matched_items = [items_by_id[item_id] for item_id in group["item_ids"] if item_id in items_by_id]
                if len(matched_items) < 2:
                    continue

                all_duplicates.append(
                    {
                        "suggestion_id": f"dup-{cat_name}-{'-'.join(group['item_ids'])}",
                        "item_ids": group["item_ids"],
                        "items": matched_items,
                        "similarity_score": float(group.get("similarity_score") or 0),
                        "reasoning": group["reasoning"],
                        "suggested_merged": group["merged_content"],
                        "merged_title": group.get("merged_title"),
                        "merged_context": group.get("merged_context"),
                        "merged_evidence": group.get("merged_evidence"),
                        "is_conflict": bool(group.get("is_conflict", False)),
                        "merged_confidence": group.get("merged_confidence"),
                        "merged_decay": group.get("merged_decay"),
                        "scoring_explanation": group.get("scoring_explanation"),
                        "dismissed": False,
                    }
                )

        return jsonify({"success": True, "duplicates": all_duplicates})
    except Exception as e:
        return handle_error("detect_duplicates", e)


@knowledge_bp.route("/api/kb/duplicates/merge", methods=["POST"])
def merge_duplicates():
    try:
        data = request.json or {}
        item_ids = data.get("item_ids", [])
        merged_content = data.get("merged_content", "")
        merged_title = data.get("merged_title", "")

        if len(item_ids) < 2:
            return jsonify({"success": False, "error": "At least two item_ids are required"}), 400
        if not merged_content or not merged_title:
            return jsonify({"success": False, "error": "merged_content and merged_title are required"}), 400

        kb = load_knowledge_base()
        items = kb["items"]
        items_to_update = [item for item in items if item["item_id"] in item_ids]
        if len(items_to_update) != len(item_ids):
            return jsonify({"success": False, "error": "One or more items not found"}), 404

        primary = items_to_update[0]
        primary["title"] = merged_title
        primary["content"] = merged_content
        primary["confidence"] = data.get("merged_confidence", primary.get("confidence"))
        primary["decay"] = data.get("merged_decay", primary.get("decay"))
        primary["scoring_explanation"] = data.get("scoring_explanation")
        primary["is_conflict"] = bool(data.get("is_conflict", False))
        primary["is_favorite"] = any(i.get("is_favorite", False) for i in items_to_update)
        primary["updated_at"] = datetime.now().isoformat()

        remove_ids = set(item_ids[1:])
        kb["items"] = [item for item in items if item["item_id"] not in remove_ids]
        save_knowledge_base(kb)

        return jsonify({"success": True, "item": primary, "removed_item_ids": list(remove_ids)})
    except Exception as e:
        return handle_error("merge_duplicates", e)
