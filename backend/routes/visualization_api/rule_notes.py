from __future__ import annotations

from flask import jsonify, request

from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.notes_store import (
    load_notes_document,
    normalize_note_record,
    save_notes_document,
)

from .common import handle_error, visualization_bp


def load_rule_notes(chat_id: str) -> dict:
    return load_notes_document(chat_id)


def save_rule_notes(chat_id: str, notes_doc: dict) -> None:
    save_notes_document(chat_id, notes_doc)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/rule-notes", methods=["GET"])
def get_rule_notes(chat_id):
    try:
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        notes_doc = load_rule_notes(chat_id)
        notes = notes_doc.get("notes", {}) or {}
        return jsonify({"success": True, "notes": notes})
    except Exception as e:
        return handle_error("get_rule_notes", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/rule-notes", methods=["PUT"])
def update_rule_notes(chat_id):
    try:
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        data = request.json or {}
        notes = data.get("notes", {})
        if not isinstance(notes, dict):
            return jsonify({"success": False, "error": "notes must be an object"}), 400

        existing_doc = load_rule_notes(chat_id)
        existing_notes = existing_doc.get("notes", {}) or {}
        normalized_notes = {}
        for note_key, note_value in notes.items():
            key = str(note_key)
            normalized = normalize_note_record(chat_id, key, note_value, touch=True)
            prior = existing_notes.get(key, {})
            if isinstance(prior, dict) and prior.get("created_at"):
                normalized["created_at"] = prior.get("created_at")
            normalized_notes[key] = normalized

        notes_doc = {
            "chat_id": chat_id,
            "notes": normalized_notes,
            "created_at": existing_doc.get("created_at") or next(iter(normalized_notes.values()), {}).get("created_at"),
            "updated_at": next(iter(normalized_notes.values()), {}).get("updated_at")
            or existing_doc.get("updated_at")
            or existing_doc.get("created_at"),
        }
        save_rule_notes(chat_id, notes_doc)

        return jsonify({"success": True, "notes": normalized_notes})
    except Exception as e:
        return handle_error("update_rule_notes", e)
