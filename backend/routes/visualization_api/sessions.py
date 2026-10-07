from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import tiktoken
from flask import jsonify, request

from backend.globals.models import get_default_provider
from backend.utils import get_project_root, strip_markdown_json, get_llm_model_for_feature
from backend.visualization.prompts.rule_learning import RULE_LEARNING_PROMPT
from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.runtime_store import load_runtime_document, save_runtime_document

from .common import handle_error, logger, visualization_bp


def _count_clean_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


@visualization_bp.route("/api/config", methods=["GET"])
def get_config():
    try:
        logger.info("GET /api/config - Started")
        config_path = get_project_root() / ".zoro" / "config.json"

        if not config_path.exists():
            logger.warning("Config file not found")
            return jsonify({"success": False, "error": "Config file not found"}), 404

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        logger.info("GET /api/config - Success")
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return handle_error("get_config", e)


@visualization_bp.route("/api/project-root", methods=["GET"])
def get_project_root_endpoint():
    try:
        logger.info("GET /api/project-root - Started")
        return jsonify({"success": True, "path": str(get_project_root())})
    except Exception as e:
        return handle_error("get_project_root_endpoint", e)


@visualization_bp.route("/api/browse-directory", methods=["GET"])
def browse_directory():
    """Server-side directory listing for the project-picker UI. A browser
    can't hand JavaScript a real absolute filesystem path (even the native
    file picker only exposes relative names, for sandboxing reasons), so
    the picker walks the tree through this endpoint instead — the server
    already has real filesystem access, and the path it reports back for
    the directory being browsed is exactly what POST /api/project-root needs.
    """
    try:
        logger.info("GET /api/browse-directory - Started")
        raw_path = request.args.get("path", "").strip()
        candidate = Path(raw_path).expanduser() if raw_path else Path.home()
        candidate = candidate.resolve()

        if not candidate.exists():
            return jsonify({"success": False, "error": f"Directory does not exist: {candidate}"}), 404
        if not candidate.is_dir():
            return jsonify({"success": False, "error": f"Not a directory: {candidate}"}), 400

        directories = []
        try:
            for entry in candidate.iterdir():
                try:
                    if entry.is_dir():
                        directories.append(entry.name)
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            return jsonify({"success": False, "error": f"Permission denied: {candidate}"}), 403

        directories.sort(key=str.lower)
        parent = str(candidate.parent) if candidate.parent != candidate else None

        logger.info(f"GET /api/browse-directory - Success ({len(directories)} subdirectories)")
        return jsonify(
            {"success": True, "path": str(candidate), "parent": parent, "directories": directories}
        )
    except Exception as e:
        return handle_error("browse_directory", e)


@visualization_bp.route("/api/project-root", methods=["POST"])
def set_project_root():
    """Switches which project ZORO operates on by changing this process's
    cwd — get_project_root() (backend/utils.py) is just Path.cwd(), read
    fresh on every call, so no restart is needed for this to take effect.
    """
    try:
        logger.info("POST /api/project-root - Started")
        data = request.json or {}
        raw_path = str(data.get("path", "")).strip()
        if not raw_path:
            return jsonify({"success": False, "error": "path is required"}), 400

        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            return jsonify({"success": False, "error": "path must be absolute"}), 400
        if not candidate.exists():
            return jsonify({"success": False, "error": f"Directory does not exist: {candidate}"}), 404
        if not candidate.is_dir():
            return jsonify({"success": False, "error": f"Not a directory: {candidate}"}), 400

        os.chdir(candidate)
        logger.info(f"POST /api/project-root - Success (now {candidate})")
        return jsonify({"success": True, "path": str(get_project_root())})
    except Exception as e:
        return handle_error("set_project_root", e)


@visualization_bp.route("/api/chat-visualizations", methods=["GET"])
def get_chat_visualizations():
    try:
        logger.info("GET /api/chat-visualizations - Started")
        visualizations = vm.list_visualizations()
        logger.info(f"GET /api/chat-visualizations - Success ({len(visualizations)} found)")
        return jsonify(visualizations)
    except Exception as e:
        return handle_error("get_chat_visualizations", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>", methods=["GET"])
def get_chat_visualization(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id} - Started")
        visualization = vm.get_visualization(chat_id)

        if not visualization:
            logger.info(f"GET /api/chat-visualizations/{chat_id} - Not Found")
            return jsonify({"error": "Visualization not found"}), 404

        logger.info(f"GET /api/chat-visualizations/{chat_id} - Success")
        return jsonify(visualization)
    except Exception as e:
        return handle_error("get_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations", methods=["POST"])
def create_chat_visualization():
    try:
        logger.info("POST /api/chat-visualizations - Started")
        metadata, error = vm.create_visualization()

        if error:
            logger.info(f"POST /api/chat-visualizations - Error: {error}")
            return jsonify({"error": error}), 400

        logger.info(f"POST /api/chat-visualizations - Success (chat_id: {metadata['chat_id']})")
        return jsonify(metadata), 201
    except Exception as e:
        return handle_error("create_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>", methods=["DELETE"])
def delete_chat_visualization(chat_id):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Started")
        success, error = vm.delete_visualization(chat_id)

        if not success:
            logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Error: {error}")
            return jsonify({"error": error}), 404

        logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Success")
        return "", 204
    except Exception as e:
        return handle_error("delete_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>", methods=["PUT"])
def update_chat_visualization(chat_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id} - Started")
        data = request.json or {}
        name = data.get("name", "").strip()

        if not name:
            return jsonify({"error": "Missing name"}), 400

        metadata, error = vm.update_visualization_name(chat_id, name)

        if error:
            logger.info(f"PUT /api/chat-visualizations/{chat_id} - Error: {error}")
            return jsonify({"error": error}), 404

        logger.info(f"PUT /api/chat-visualizations/{chat_id} - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error("update_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/start", methods=["POST"])
def start_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Started")
        metadata, error = vm.start_visualization(chat_id)

        if error:
            logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Error: {error}")
            return jsonify({"error": error}), 404

        logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error("start_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/pause", methods=["POST"])
def pause_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Started")
        metadata, error = vm.pause_visualization(chat_id)

        if error:
            logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Error: {error}")
            return jsonify({"error": error}), 404

        logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error("pause_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/poll", methods=["GET"])
def poll_chat_visualization(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Started")
        content, status, error = vm.poll_visualization(chat_id)

        if error:
            logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Error: {error}")
            return jsonify({"status": status, "content": None, "error": error}), 400

        logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Success (has_content: {content is not None})")
        return jsonify({"status": status, "content": content})
    except Exception as e:
        return handle_error("poll_chat_visualization", e)


@visualization_bp.route("/api/chat-visualizations/<chat_id>/analyze", methods=["POST"])
def analyze_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/analyze - Started")

        visualization = vm.get_visualization(chat_id)
        if not visualization:
            return jsonify({"error": "Visualization not found"}), 404

        runtime = load_runtime_document(chat_id)
        cleaned_content = runtime.get("cleaned_accumulated_content", "")
        if not cleaned_content:
            return jsonify({"error": "No content to analyze"}), 400

        try:
            enc = tiktoken.get_encoding("cl100k_base")
            clean_tokens = enc.encode(cleaned_content)
            total_clean_tokens = len(clean_tokens)
        except Exception:
            clean_tokens = cleaned_content.split()
            total_clean_tokens = len(clean_tokens)

        last_analyzed_index = int(runtime.get("last_analyzed_token_index", 0))

        if last_analyzed_index >= total_clean_tokens:
            latest = dict(runtime.get("latest_rule_learning", {}) or {})
            latest.setdefault("rules", [])
            latest["total_clean_tokens"] = total_clean_tokens
            latest["analyzed_tokens"] = last_analyzed_index
            latest["analyzed_from_token"] = last_analyzed_index
            latest["analyzed_to_token"] = last_analyzed_index
            latest["remaining_tokens"] = 0
            latest["all_analyzed"] = True
            latest["success"] = True
            return jsonify(latest)

        max_tokens = 150000
        start_index = last_analyzed_index
        end_index = min(start_index + max_tokens, total_clean_tokens)

        try:
            window_tokens = clean_tokens[start_index:end_index]
            content_to_analyze = enc.decode(window_tokens)
        except Exception:
            content_to_analyze = cleaned_content[start_index:end_index]

        logger.info(f"Analyzing tokens {start_index}-{end_index} of {total_clean_tokens}")

        existing_rules_text = "No existing rules provided."
        try:
            kb_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if kb_path.exists():
                with open(kb_path, "r", encoding="utf-8") as f:
                    kb_data = json.load(f)
                kb_items = kb_data.get("items", []) if isinstance(kb_data, dict) else []
                preview_items = kb_items[:120]
                if preview_items:
                    lines = []
                    for item in preview_items:
                        category = str(item.get("category", "uncategorized"))
                        title = str(item.get("title", "Rule")).strip()
                        content = str(item.get("content", "")).strip().replace("\n", " ")
                        if len(content) > 180:
                            content = content[:177] + "..."
                        lines.append(f"- [{category}] {title}: {content}")
                    existing_rules_text = "\n".join(lines)
        except Exception as kb_error:
            logger.warning(f"Could not load existing KB rules for analyze prompt: {kb_error}")

        prompt = RULE_LEARNING_PROMPT.format(
            content=content_to_analyze,
            existing_rules=existing_rules_text,
            analyzed_from_token=start_index,
            analyzed_to_token=end_index,
        )

        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_llm_model_for_feature("rule_learning"),
        )
        result = json.loads(strip_markdown_json(response))

        response_data = {
            "success": True,
            "rules": result.get("rules", []),
            "total_clean_tokens": total_clean_tokens,
            "analyzed_tokens": end_index,
            "analyzed_from_token": start_index,
            "analyzed_to_token": end_index,
            "remaining_tokens": total_clean_tokens - end_index,
            "all_analyzed": end_index >= total_clean_tokens,
        }
        runtime["last_analyzed_token_index"] = end_index
        runtime["total_clean_tokens"] = total_clean_tokens
        runtime["latest_rule_learning"] = {
            **response_data,
            "updated_at": datetime.utcnow().isoformat(),
        }
        save_runtime_document(chat_id, runtime)
        runtime = load_runtime_document(chat_id)
        runtime_learning = dict(runtime.get("latest_rule_learning", {}) or {})
        runtime_learning.setdefault("success", True)

        logger.info(
            f"POST /api/chat-visualizations/{chat_id}/analyze - Success "
            f"({len(result.get('rules', []))} rules, {end_index}/{total_clean_tokens} tokens)"
        )
        return jsonify(runtime_learning)
    except Exception as e:
        return handle_error("analyze_chat_visualization", e)


@visualization_bp.route("/api/visualization/rule-learning/<chat_id>", methods=["GET"])
def get_rule_learning(chat_id):
    try:
        logger.info(f"GET /api/visualization/rule-learning/{chat_id} - Started")

        visualization = vm.get_visualization(chat_id)
        if not visualization:
            return jsonify({"error": "Visualization not found"}), 404

        runtime = load_runtime_document(chat_id)
        cleaned_content = runtime.get("cleaned_accumulated_content", "")
        total_clean_tokens = _count_clean_tokens(cleaned_content)
        latest = dict(runtime.get("latest_rule_learning", {}) or {})
        analyzed_tokens = int(runtime.get("last_analyzed_token_index", latest.get("analyzed_tokens", 0) or 0))
        latest.setdefault("rules", [])
        latest.setdefault("success", True)
        latest["analyzed_tokens"] = analyzed_tokens
        latest.setdefault("analyzed_from_token", 0)
        latest.setdefault("analyzed_to_token", analyzed_tokens)
        latest["remaining_tokens"] = max(total_clean_tokens - analyzed_tokens, 0)
        latest["all_analyzed"] = total_clean_tokens > 0 and analyzed_tokens >= total_clean_tokens
        latest["total_clean_tokens"] = total_clean_tokens
        latest["can_analyze_more"] = analyzed_tokens < total_clean_tokens

        logger.info(
            f"GET /api/visualization/rule-learning/{chat_id} - Success "
            f"(rules: {len(latest.get('rules', []))}, analyzed: {latest.get('analyzed_tokens', 0)})"
        )
        return jsonify(latest)
    except Exception as e:
        return handle_error("get_rule_learning", e)
