from __future__ import annotations

import json
import uuid
from datetime import datetime

from flask import jsonify, request

from backend.globals.models import get_default_provider
from backend.globals.schemas import get_schema
from backend.knowledge.prompts.category_suggestions import CATEGORY_MERGE_PROMPT
from backend.knowledge.prompts.refine_manual_rule import REFINE_MANUAL_RULE_PROMPT
from backend.utils import get_llm_model_for_feature

from backend.knowledge.services.storage import extract_unique_categories, load_knowledge_base, save_knowledge_base

from .common import handle_error, logger, knowledge_bp


@knowledge_bp.route("/api/kb/categories/suggest-merges", methods=["GET"])
def suggest_category_merges():
    try:
        kb = load_knowledge_base()
        categories = extract_unique_categories(kb)
        if len(categories) < 2:
            return jsonify({"success": True, "suggestions": []})

        category_details = []
        for cat_name, count in sorted(categories.items(), key=lambda x: -x[1]):
            items_in_cat = [i for i in kb["items"] if i["category"] == cat_name]
            samples = items_in_cat[:10]
            category_details.append(f"\n## {cat_name} ({count} items)")
            for item in samples:
                category_details.append(f"  - [{item['type']}] {item['title']}")
                content_preview = item["content"][:150] + "..." if len(item["content"]) > 150 else item["content"]
                category_details.append(f"    Content: {content_preview}")

        provider = get_default_provider()
        prompt = CATEGORY_MERGE_PROMPT.format(category_details="\n".join(category_details))
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_llm_model_for_feature("knowledge_category_merge"),
            response_format=get_schema(
                {
                    "type": "object",
                    "properties": {
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "merge_from": {"type": "array", "items": {"type": "string"}},
                                    "merge_to": {"type": "string"},
                                    "reasoning": {"type": "string"},
                                },
                                "required": ["merge_from", "merge_to", "reasoning"],
                            },
                        }
                    },
                    "required": ["suggestions"],
                }
            ),
        )

        parsed = json.loads(response)
        suggestions = []
        for suggestion in parsed["suggestions"]:
            suggestions.append(
                {
                    "suggestion_id": str(uuid.uuid4()),
                    "merge_from": suggestion["merge_from"],
                    "merge_to": suggestion["merge_to"],
                    "reasoning": suggestion["reasoning"],
                    "dismissed": False,
                }
            )

        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        return handle_error("suggest_category_merges", e)


@knowledge_bp.route("/api/kb/categories/accept", methods=["POST"])
def accept_category_merge():
    try:
        data = request.json
        merge_from = data.get("merge_from", [])
        merge_to = data.get("merge_to", "")
        if not merge_from or not merge_to:
            return jsonify({"success": False, "error": "Missing merge parameters"}), 400

        kb = load_knowledge_base()
        updated_count = 0
        for item in kb["items"]:
            if item["category"] in merge_from:
                item["category"] = merge_to
                updated_count += 1

        save_knowledge_base(kb)
        return jsonify(
            {
                "success": True,
                "updated_items": updated_count,
                "merge_from": merge_from,
                "merge_to": merge_to,
            }
        )
    except Exception as e:
        return handle_error("accept_category_merge", e)


@knowledge_bp.route("/api/kb/categories/dismiss", methods=["POST"])
def dismiss_category_merge():
    try:
        data = request.json
        suggestion_id = data.get("suggestion_id", "")
        return jsonify({"success": True, "suggestion_id": suggestion_id})
    except Exception as e:
        return handle_error("dismiss_category_merge", e)


@knowledge_bp.route("/api/kb/items", methods=["GET"])
def list_items():
    try:
        category = request.args.get("category")
        item_type = request.args.get("type")
        favorites_only = request.args.get("favorites") == "true"
        search = request.args.get("search", "").lower()

        kb = load_knowledge_base()
        items = kb["items"]

        if category:
            items = [i for i in items if i["category"] == category]
        if item_type:
            items = [i for i in items if i["type"] == item_type]
        if favorites_only:
            items = [i for i in items if i["is_favorite"]]
        if search:
            items = [i for i in items if search in i["title"].lower() or search in i["content"].lower()]

        return jsonify({"success": True, "items": items, "count": len(items)})
    except Exception as e:
        return handle_error("list_items", e)


@knowledge_bp.route("/api/kb/items/refine", methods=["POST"])
def refine_manual_rule():
    try:
        data = request.json
        required_fields = ["rule_type", "category", "title", "content"]
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing field: {field}"}), 400

        provider = get_default_provider()
        prompt = REFINE_MANUAL_RULE_PROMPT.format(
            rule_type=data["rule_type"],
            category=data["category"],
            title=data["title"],
            content=data["content"],
            context=data.get("context") or "",
            evidence=data.get("evidence") or "",
        )

        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_llm_model_for_feature("knowledge_rule_refinement"),
            response_format=get_schema(
                {
                    "type": "object",
                    "properties": {
                        "refined": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                                "confidence": {"type": "number"},
                                "decay": {"type": "number"},
                                "confidence_reasoning": {"type": "string"},
                                "decay_reasoning": {"type": "string"},
                                "context": {"type": ["string", "null"]},
                                "evidence": {"type": ["string", "null"]},
                            },
                            "required": [
                                "title",
                                "content",
                                "confidence",
                                "decay",
                                "confidence_reasoning",
                                "decay_reasoning",
                                "context",
                                "evidence",
                            ],
                        }
                    },
                    "required": ["refined"],
                }
            ),
        )

        parsed = json.loads(response)
        return jsonify({"success": True, "refined": parsed["refined"]})
    except Exception as e:
        return handle_error("refine_manual_rule", e)


@knowledge_bp.route("/api/kb/items", methods=["POST"])
def create_item():
    try:
        data = request.json
        required_fields = ["type", "category", "title", "content"]
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing field: {field}"}), 400

        new_item = {
            "item_id": str(uuid.uuid4()),
            "type": data["type"],
            "category": data["category"],
            "title": data["title"],
            "content": data["content"],
            "context": data.get("context"),
            "evidence": data.get("evidence"),
            "confidence": data.get("confidence", 0.5),
            "decay": data.get("decay", 0.5),
            "confidence_reasoning": data.get("confidence_reasoning"),
            "decay_reasoning": data.get("decay_reasoning"),
            "source_file": data.get("source_file", "manual"),
            "usage_count": data.get("usage_count", 0),
            "is_favorite": data.get("is_favorite", False),
            "is_strict": data.get("is_strict", False),
            "is_testable": data.get("is_testable", False),
            "created_at": datetime.now().isoformat(),
        }

        kb = load_knowledge_base()
        kb["items"].append(new_item)
        save_knowledge_base(kb)
        return jsonify({"success": True, "item": new_item}), 201
    except Exception as e:
        return handle_error("create_item", e)


@knowledge_bp.route("/api/kb/items/<item_id>", methods=["PATCH"])
def update_item(item_id):
    try:
        data = request.json
        kb = load_knowledge_base()
        item = next((i for i in kb["items"] if i["item_id"] == item_id), None)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        allowed_fields = [
            "type",
            "category",
            "title",
            "content",
            "context",
            "evidence",
            "confidence",
            "decay",
            "confidence_reasoning",
            "decay_reasoning",
            "usage_count",
            "is_favorite",
            "is_strict",
            "is_testable",
        ]
        for field in allowed_fields:
            if field in data:
                item[field] = data[field]

        save_knowledge_base(kb)
        return jsonify({"success": True, "item": item})
    except Exception as e:
        return handle_error("update_item", e)


@knowledge_bp.route("/api/kb/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    try:
        kb = load_knowledge_base()
        items = kb["items"]
        item = next((i for i in items if i["item_id"] == item_id), None)
        if not item:
            return jsonify({"success": False, "error": "Item not found"}), 404

        kb["items"] = [i for i in items if i["item_id"] != item_id]
        save_knowledge_base(kb)
        return jsonify({"success": True})
    except Exception as e:
        return handle_error("delete_item", e)


@knowledge_bp.route("/api/kb/categories", methods=["GET"])
def list_categories():
    try:
        kb = load_knowledge_base()
        categories = sorted(set(item["category"] for item in kb["items"]))
        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        return handle_error("list_categories", e)
