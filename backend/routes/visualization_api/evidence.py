from __future__ import annotations

from flask import jsonify

from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.evidence_store import load_evidence_document

from .common import handle_error, visualization_bp


@visualization_bp.route("/api/chat-visualizations/<chat_id>/evidence", methods=["GET"])
def get_evidence(chat_id):
    try:
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        evidence_doc = load_evidence_document(chat_id)
        return jsonify({"success": True, "evidence": evidence_doc.get("records", [])})
    except Exception as e:
        return handle_error("get_evidence", e)
