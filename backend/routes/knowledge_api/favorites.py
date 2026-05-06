from __future__ import annotations

import uuid
from datetime import datetime

from flask import jsonify, request

from backend.knowledge.services.storage import (
    load_knowledge_base,
    load_manual_favorites,
    save_knowledge_base,
    save_manual_favorites,
)

from .common import handle_error, logger, knowledge_bp


@knowledge_bp.route("/api/kb/favorites", methods=["GET"])
def get_favorites():
    try:
        kb = load_knowledge_base()
        manual_favorites = load_manual_favorites().get("favorites", [])
        favorites = [item for item in kb["items"] if item.get("is_favorite", False)]
        favorites.extend(manual_favorites)
        return jsonify({"success": True, "favorites": favorites})
    except Exception as e:
        return handle_error("get_favorites", e)


@knowledge_bp.route("/api/kb/favorites", methods=["POST"])
def add_favorite():
    try:
        data = request.json or {}
        rule_id = (data.get("rule_id") or data.get("item_id") or "").strip()
        if not rule_id:
            return jsonify({"success": False, "error": "Missing rule_id"}), 400

        kb = load_knowledge_base()
        item = next((i for i in kb["items"] if i["item_id"] == rule_id), None)
        if not item:
            return jsonify({"success": False, "error": "Rule not found in knowledge base"}), 404

        item["is_favorite"] = True
        save_knowledge_base(kb)
        return jsonify({"success": True, "item": item})
    except Exception as e:
        return handle_error("add_favorite", e)


@knowledge_bp.route("/api/kb/favorites/manual", methods=["POST"])
def add_manual_favorite():
    try:
        data = request.json or {}

        rule_text = (data.get("rule") or "").strip()
        reasoning = (
            data.get("reasoning")
            or data.get("context")
            or data.get("evidence")
            or ""
        ).strip()
        category = (data.get("category") or "manual").strip() or "manual"
        title = (data.get("title") or "").strip() or rule_text[:80]

        if not rule_text:
            return jsonify({"success": False, "error": "Missing rule text"}), 400
        if not reasoning:
            return jsonify({"success": False, "error": "Missing reasoning"}), 400

        favorites_doc = load_manual_favorites()
        favorites = favorites_doc.setdefault("favorites", [])

        new_rule = {
            "item_id": f"manual-{uuid.uuid4()}",
            "type": "rule",
            "category": category,
            "title": title,
            "content": rule_text,
            "context": data.get("context") if data.get("context") is not None else reasoning,
            "evidence": data.get("evidence"),
            "confidence": data.get("confidence"),
            "decay": data.get("decay"),
            "confidence_reasoning": data.get("confidence_reasoning"),
            "decay_reasoning": data.get("decay_reasoning"),
            "source_file": "manual-favorite",
            "usage_count": 0,
            "is_favorite": True,
            "is_strict": bool(data.get("is_strict", False)),
            "is_testable": bool(data.get("is_testable", False)),
            "created_at": datetime.now().isoformat(),
        }

        favorites.append(new_rule)
        save_manual_favorites(favorites_doc)
        return jsonify({"success": True, "rule": new_rule})
    except Exception as e:
        return handle_error("add_manual_favorite", e)


@knowledge_bp.route("/api/kb/favorites/<rule_id>", methods=["DELETE"])
def remove_favorite(rule_id):
    try:
        kb = load_knowledge_base()
        item = next((i for i in kb["items"] if i["item_id"] == rule_id), None)
        if item:
            item["is_favorite"] = False
            save_knowledge_base(kb)
            return jsonify({"success": True, "rule_id": rule_id})

        favorites_doc = load_manual_favorites()
        favorites = favorites_doc.get("favorites", [])
        filtered = [favorite for favorite in favorites if favorite.get("item_id") != rule_id]
        if len(filtered) == len(favorites):
            return jsonify({"success": False, "error": "Favorite not found"}), 404

        favorites_doc["favorites"] = filtered
        save_manual_favorites(favorites_doc)
        return jsonify({"success": True, "rule_id": rule_id})
    except Exception as e:
        return handle_error("remove_favorite", e)
