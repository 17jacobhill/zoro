from __future__ import annotations

import json
from datetime import datetime

import tiktoken
from flask import jsonify, request

from backend.utils import get_project_root
from backend.visualization.paths import (
    get_existing_monitoring_path,
    get_monitoring_path,
)
from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.enforcement_agent import EnforcementAgent
from backend.visualization.services.evidence_store import build_enforcement_history, load_evidence_document
from backend.visualization.services.plan_persistence import load_plan_document
from backend.visualization.services.plan_tracker import build_rules_in_focus_snapshot
from backend.visualization.services.runtime_store import load_runtime_document, save_runtime_document
from backend.visualization.services.supervisor_agent import SupervisorAgent
from backend.visualization.services.supervisor_service import SUPERVISION_TOKEN_INTERVAL

from .common import handle_error, logger, visualization_bp


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


def _with_rules_in_focus(supervision: dict, plan_data: dict | None) -> dict:
    entry = dict(supervision or {})

    if not plan_data:
        entry["rules_in_focus"] = {"current_step": None, "expected_step": None}
        return entry

    current_step = entry.get("current_step")
    expected_step = entry.get("expected_step")
    entry["rules_in_focus"] = {
        "current_step": build_rules_in_focus_snapshot(plan_data, current_step),
        "expected_step": build_rules_in_focus_snapshot(plan_data, expected_step),
    }
    return entry


@visualization_bp.route("/api/visualization/supervision/<chat_id>", methods=["GET"])
def get_supervision(chat_id):
    try:
        logger.info(f"GET /api/visualization/supervision/{chat_id} - Started")

        monitoring_file = get_existing_monitoring_path(chat_id, get_project_root())
        runtime = load_runtime_document(chat_id)
        supervision_cleaned_content = runtime.get("supervision_cleaned_accumulated_content", "")

        current_tokens = _count_tokens(supervision_cleaned_content)
        last_supervised_tokens = int(runtime.get("last_supervised_token_index", 0))

        tokens_since_last = max(current_tokens - last_supervised_tokens, 0)
        threshold = SUPERVISION_TOKEN_INTERVAL
        progress_percent = min((tokens_since_last / threshold) * 100, 100) if threshold > 0 else 0

        token_stats = {
            "current_tokens": current_tokens,
            "last_supervised_tokens": last_supervised_tokens,
            "tokens_since_last": tokens_since_last,
            "threshold": threshold,
            "progress_percent": progress_percent,
        }

        history = []
        if monitoring_file.exists():
            with open(monitoring_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                history = data
            elif isinstance(data, dict):
                history = [data]

        plan_data = load_plan_document(chat_id)
        history_with_focus = [_with_rules_in_focus(entry, plan_data) for entry in history]

        logger.info(f"GET /api/visualization/supervision/{chat_id} - Success (history: {len(history_with_focus)} entries)")
        return jsonify({"success": True, "supervision_history": history_with_focus, "token_stats": token_stats})
    except Exception as e:
        return handle_error("get_supervision", e)


@visualization_bp.route("/api/visualization/supervision/<chat_id>/resolve", methods=["POST"])
def resolve_supervision(chat_id):
    try:
        logger.info(f"POST /api/visualization/supervision/{chat_id}/resolve - Started")

        data = request.json or {}
        timestamp = data.get("timestamp")
        if not timestamp:
            return jsonify({"success": False, "error": "Missing timestamp"}), 400

        existing_monitoring_file = get_existing_monitoring_path(chat_id, get_project_root())
        if not existing_monitoring_file.exists():
            return jsonify({"success": False, "error": "No monitoring data found"}), 404

        with open(existing_monitoring_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, list):
            history = raw
        elif isinstance(raw, dict):
            history = [raw]
        else:
            return jsonify({"success": False, "error": "Invalid monitoring data"}), 500

        found = False
        for entry in history:
            if entry.get("timestamp") == timestamp:
                entry["resolved"] = True
                found = True
                break

        if not found:
            return jsonify({"success": False, "error": "Supervision entry not found"}), 404

        monitoring_file = get_monitoring_path(chat_id, get_project_root())
        monitoring_file.parent.mkdir(parents=True, exist_ok=True)
        with open(monitoring_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        logger.info(f"POST /api/visualization/supervision/{chat_id}/resolve - Success")
        return jsonify({"success": True})
    except Exception as e:
        return handle_error("resolve_supervision", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/supervise", methods=["POST"])
def supervise_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/supervise - Started")

        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"error": "Visualization not found"}), 404

        runtime = load_runtime_document(chat_id)
        supervision_cleaned_content = runtime.get("supervision_cleaned_accumulated_content", "")
        if not supervision_cleaned_content:
            return jsonify({"error": "No content to supervise"}), 400

        try:
            enc = tiktoken.get_encoding("cl100k_base")
            all_tokens = enc.encode(supervision_cleaned_content)
            total_tokens = len(all_tokens)
        except Exception:
            all_tokens = supervision_cleaned_content.split()
            total_tokens = len(all_tokens)

        last_supervised_index = int(runtime.get("last_supervised_token_index", 0))
        if last_supervised_index >= total_tokens:
            return jsonify(
                {
                    "supervision": None,
                    "total_tokens": total_tokens,
                    "supervised_tokens": last_supervised_index,
                    "remaining_tokens": 0,
                    "all_supervised": True,
                }
            )

        max_tokens = 200000
        start_index = last_supervised_index
        end_index = min(start_index + max_tokens, total_tokens)

        try:
            window_tokens = all_tokens[start_index:end_index]
            content_window = enc.decode(window_tokens)
        except Exception:
            content_window = supervision_cleaned_content[start_index:end_index]

        logger.info(f"Supervising tokens {start_index}-{end_index} of {total_tokens}")

        supervisor = SupervisorAgent()
        result = supervisor.supervise(chat_id, content_window)
        plan_data = load_plan_document(chat_id)
        result_with_focus = _with_rules_in_focus(result, plan_data)

        monitoring_file = get_monitoring_path(chat_id, get_project_root())
        monitoring_file.parent.mkdir(parents=True, exist_ok=True)

        history = []
        if monitoring_file.exists():
            try:
                with open(monitoring_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    history = raw
                elif isinstance(raw, dict):
                    history = [raw]
            except Exception:
                history = []

        history.append({**result_with_focus, "saved_at": datetime.now().isoformat()})
        history = history[-20:]

        with open(monitoring_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        runtime["last_supervised_token_index"] = end_index
        runtime["total_supervision_clean_tokens"] = total_tokens
        save_runtime_document(chat_id, runtime)

        response_data = {
            "supervision": result_with_focus,
            "total_tokens": total_tokens,
            "supervised_tokens": end_index,
            "remaining_tokens": total_tokens - end_index,
            "all_supervised": end_index >= total_tokens,
        }
        logger.info(f"POST /api/chat-visualizations/{chat_id}/supervise - Success ({end_index}/{total_tokens} tokens)")
        return jsonify(response_data)
    except Exception as e:
        return handle_error("supervise_chat_visualization", e)


@visualization_bp.route("/api/visualization/<chat_id>/enforce-item/<item_id>", methods=["POST"])
def enforce_single_item_api(chat_id, item_id):
    try:
        logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Started")

        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({"success": False, "error": "Visualization not found"}), 404

        runtime = load_runtime_document(chat_id)
        supervision_cleaned_content = runtime.get("supervision_cleaned_accumulated_content", "")
        if not supervision_cleaned_content:
            return jsonify({"success": False, "error": "No content to enforce"}), 400

        try:
            enc = tiktoken.get_encoding("cl100k_base")
            all_tokens = enc.encode(supervision_cleaned_content)
            total_tokens = len(all_tokens)
        except Exception:
            all_tokens = supervision_cleaned_content.split()
            total_tokens = len(all_tokens)

        enforcement_window = 75000
        window_start = max(0, total_tokens - enforcement_window)

        try:
            window_tokens = all_tokens[window_start:]
            content_window = enc.decode(window_tokens)
            visible_token_count = len(window_tokens)
        except Exception:
            content_window = supervision_cleaned_content[window_start:]
            visible_token_count = len(all_tokens[window_start:])

        logger.info(f"Enforcing item {item_id}: sliding window with last {visible_token_count} tokens")

        agent = EnforcementAgent()
        result = agent.enforce_single_item(chat_id, item_id, content_window)

        if result.get("error"):
            logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Error: {result['error']}")
            return jsonify({"success": False, "error": result["error"]}), 400

        logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Success")
        return jsonify({"success": True, "enforcement": result})
    except Exception as e:
        return handle_error("enforce_single_item", e)


@visualization_bp.route("/api/visualization/enforcement-history/<chat_id>", methods=["GET"])
def get_enforcement_history_api(chat_id):
    try:
        logger.info(f"GET /api/visualization/enforcement-history/{chat_id} - Started")
        history = build_enforcement_history(load_evidence_document(chat_id))
        logger.info(
            f"GET /api/visualization/enforcement-history/{chat_id} - Success "
            f"({len(history.get('items', {}))} items)"
        )
        return jsonify({"success": True, "enforcement_history": history})
    except Exception as e:
        return handle_error("get_enforcement_history", e)
