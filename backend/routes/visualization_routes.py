from flask import Blueprint, request, jsonify
import logging
import json
import tiktoken
from datetime import datetime
from pathlib import Path
from shutil import copy2

from backend.plan_paths import get_plan_markdown_path
from backend.visualization.services import visualization_manager as vm
from backend.visualization.services.visualization_manager import (
    _delete_item_recursive,
    _renumber_items,
    _recalculate_inherited_rules,
    _find_item_in_tree
)
from backend.learner.chat_parser import ChatParser
from backend.visualization.prompts.rule_learning import RULE_LEARNING_PROMPT
from backend.visualization.prompts.plan_extraction import PLAN_EXTRACTION_PROMPT, POPULATE_RULES_PROMPT, REFINE_SUBSTEPS_PROMPT
from backend.globals.models import get_default_provider
from backend.utils import get_project_root, strip_markdown_json, get_enforcement_mode
from backend.visualization.services.plan_tracker import plan_to_markdown
from backend.visualization.services.supervisor_service import ChatWatcher

visualization_bp = Blueprint('visualization', __name__)
logger = logging.getLogger(__name__)

_watcher = ChatWatcher()


def _rule_notes_path(chat_id: str) -> Path:
    return get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "rule_notes.json"


def _normalize_note_record(chat_id: str, note_key: str, note_value, now_iso: str) -> dict:
    if isinstance(note_value, dict):
        record = dict(note_value)
    else:
        record = {"note_text": str(note_value or "")}

    record["note_key"] = note_key
    record["chat_id"] = chat_id
    record["note_text"] = str(record.get("note_text", ""))
    record["rule_kb_item_id"] = record.get("rule_kb_item_id")
    record["rule_text"] = str(record.get("rule_text", ""))
    record["plan_item_id"] = record.get("plan_item_id")
    record["verification_timestamp"] = record.get("verification_timestamp")
    record["verification_index"] = record.get("verification_index")
    record["source"] = str(record.get("source", "rule-verification"))
    record["verdict"] = record.get("verdict")
    record["explanation"] = str(record.get("explanation", ""))
    record["created_at"] = record.get("created_at") or now_iso
    record["updated_at"] = now_iso
    return record


def _load_rule_notes(chat_id: str) -> dict:
    notes_path = _rule_notes_path(chat_id)
    if notes_path.exists():
        with open(notes_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            notes = data.get("notes", {})
            if isinstance(notes, dict):
                return data

    # Backward compatibility: migrate any legacy favorite_rule_notes metadata
    metadata = vm.get_visualization(chat_id) or {}
    legacy_notes = metadata.get("favorite_rule_notes", {}) or {}
    now_iso = datetime.now().isoformat()
    migrated_notes = {}
    if isinstance(legacy_notes, dict):
        for note_key, note_value in legacy_notes.items():
            migrated_notes[str(note_key)] = _normalize_note_record(chat_id, str(note_key), note_value, now_iso)

    return {
        "chat_id": chat_id,
        "notes": migrated_notes,
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def _save_rule_notes(chat_id: str, notes_doc: dict) -> None:
    path = _rule_notes_path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes_doc, f, indent=2, ensure_ascii=False)

def handle_error(endpoint_name, error, status_code=500):
    logger.error(f"Error in {endpoint_name}: {str(error)}", exc_info=True)
    return jsonify({'success': False, 'error': str(error)}), status_code

@visualization_bp.route('/api/config', methods=['GET'])
def get_config():
    try:
        logger.info("GET /api/config - Started")
        config_path = get_project_root() / ".zoro" / "config.json"
        
        if not config_path.exists():
            logger.warning("Config file not found")
            return jsonify({'success': False, 'error': 'Config file not found'}), 404
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        logger.info("GET /api/config - Success")
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return handle_error('get_config', e)

@visualization_bp.route('/api/chat-visualizations', methods=['GET'])
def get_chat_visualizations():
    try:
        logger.info("GET /api/chat-visualizations - Started")
        visualizations = vm.list_visualizations()
        logger.info(f"GET /api/chat-visualizations - Success ({len(visualizations)} found)")
        return jsonify(visualizations)
    except Exception as e:
        return handle_error('get_chat_visualizations', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>', methods=['GET'])
def get_chat_visualization(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id} - Started")
        visualization = vm.get_visualization(chat_id)
        
        if not visualization:
            logger.info(f"GET /api/chat-visualizations/{chat_id} - Not Found")
            return jsonify({'error': 'Visualization not found'}), 404
        
        logger.info(f"GET /api/chat-visualizations/{chat_id} - Success")
        return jsonify(visualization)
    except Exception as e:
        return handle_error('get_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations', methods=['POST'])
def create_chat_visualization():
    try:
        logger.info("POST /api/chat-visualizations - Started")
        metadata, error = vm.create_visualization()
        
        if error:
            logger.info(f"POST /api/chat-visualizations - Error: {error}")
            return jsonify({'error': error}), 400
        
        logger.info(f"POST /api/chat-visualizations - Success (chat_id: {metadata['chat_id']})")
        return jsonify(metadata), 201
    except Exception as e:
        return handle_error('create_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>', methods=['DELETE'])
def delete_chat_visualization(chat_id):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Started")
        success, error = vm.delete_visualization(chat_id)
        
        if not success:
            logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Error: {error}")
            return jsonify({'error': error}), 404
        
        logger.info(f"DELETE /api/chat-visualizations/{chat_id} - Success")
        return '', 204
    except Exception as e:
        return handle_error('delete_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>', methods=['PUT'])
def update_chat_visualization(chat_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id} - Started")
        data = request.json or {}
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Missing name'}), 400
        
        metadata, error = vm.update_visualization_name(chat_id, name)
        
        if error:
            logger.info(f"PUT /api/chat-visualizations/{chat_id} - Error: {error}")
            return jsonify({'error': error}), 404
        
        logger.info(f"PUT /api/chat-visualizations/{chat_id} - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error('update_chat_visualization', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan', methods=['PUT'])
def update_plan_metadata(chat_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan - Started")
        data = request.json or {}
        title = data.get('title')
        description = data.get('description')

        if title is None and description is None:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)

        plan_dict = plan_data.get('plan', {})
        if title is not None:
            plan_dict['title'] = str(title).strip()
        if description is not None:
            plan_dict['description'] = str(description)
        plan_data['plan'] = plan_dict

        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)

        metadata = vm.get_visualization(chat_id)
        if metadata:
            tracking = metadata.get("plan_tracking", {})
            chat_name = metadata.get("name", "Unnamed")
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan - Success")
        return jsonify({'success': True, 'plan': plan_data})
    except Exception as e:
        return handle_error('update_plan_metadata', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/start', methods=['POST'])
def start_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Started")
        metadata, error = vm.start_visualization(chat_id)
        
        if error:
            logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Error: {error}")
            return jsonify({'error': error}), 404
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/start - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error('start_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/pause', methods=['POST'])
def pause_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Started")
        metadata, error = vm.pause_visualization(chat_id)
        
        if error:
            logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Error: {error}")
            return jsonify({'error': error}), 404
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/pause - Success")
        return jsonify(metadata)
    except Exception as e:
        return handle_error('pause_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/poll', methods=['GET'])
def poll_chat_visualization(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Started")
        content, status, error = vm.poll_visualization(chat_id)
        
        if error:
            logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Error: {error}")
            return jsonify({'status': status, 'content': None, 'error': error}), 400
        
        logger.info(f"GET /api/chat-visualizations/{chat_id}/poll - Success (has_content: {content is not None})")
        return jsonify({
            'status': status,
            'content': content
        })
    except Exception as e:
        return handle_error('poll_chat_visualization', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/analyze', methods=['POST'])
def analyze_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/analyze - Started")
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'error': 'Visualization not found'}), 404
        
        cleaned_content = metadata.get('cleaned_accumulated_content', '')
        if not cleaned_content:
            return jsonify({'error': 'No content to analyze'}), 400
        
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            clean_tokens = enc.encode(cleaned_content)
            total_clean_tokens = len(clean_tokens)
        except Exception:
            clean_tokens = cleaned_content.split()
            total_clean_tokens = len(clean_tokens)
        
        last_analyzed_index = metadata.get('last_analyzed_token_index', 0)
        
        if last_analyzed_index >= total_clean_tokens:
            return jsonify({
                'rules': [],
                'total_clean_tokens': total_clean_tokens,
                'analyzed_tokens': last_analyzed_index,
                'analyzed_from_token': last_analyzed_index,
                'analyzed_to_token': last_analyzed_index,
                'remaining_tokens': 0,
                'all_analyzed': True
            })
        
        max_tokens = 150000
        start_index = last_analyzed_index
        end_index = min(start_index + max_tokens, total_clean_tokens)
        
        try:
            window_tokens = clean_tokens[start_index:end_index]
            content_to_analyze = enc.decode(window_tokens)
        except Exception:
            content_to_analyze = cleaned_content[start_index:end_index]
        
        logger.info(f"Analyzing tokens {start_index}-{end_index} of {total_clean_tokens}")
        
        # Provide existing KB context so rule learning avoids duplicates and focuses on net-new value.
        existing_rules_text = "No existing rules provided."
        try:
            kb_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if kb_path.exists():
                with open(kb_path, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
                kb_items = kb_data.get("items", []) if isinstance(kb_data, dict) else []
                # Keep prompt bounded for latency and model focus.
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
            analyzed_to_token=end_index
        )
        
        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5"
        )
        
        result = json.loads(strip_markdown_json(response))
        
        metadata['last_analyzed_token_index'] = end_index
        vm._save_metadata(chat_id, metadata)
        
        response_data = {
            'rules': result.get('rules', []),
            'total_clean_tokens': total_clean_tokens,
            'analyzed_tokens': end_index,
            'analyzed_from_token': start_index,
            'analyzed_to_token': end_index,
            'remaining_tokens': total_clean_tokens - end_index,
            'all_analyzed': end_index >= total_clean_tokens
        }
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/analyze - Success ({len(result.get('rules', []))} rules, {end_index}/{total_clean_tokens} tokens)")
        return jsonify(response_data)
        
    except Exception as e:
        return handle_error('analyze_chat_visualization', e)

@visualization_bp.route('/api/rules/save', methods=['POST'])
def save_rules():
    try:
        logger.info("POST /api/rules/save - Started")
        
        data = request.json or {}
        rules = data.get('rules', [])
        chat_id = data.get('chat_id', 'unknown')
        
        if not rules:
            return jsonify({'error': 'No rules provided'}), 400
        
        rules_dir = get_project_root() / ".zoro" / "rules" / "unstructured"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rules_file = rules_dir / "dynamic_reflection.md"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        markdown_content = f"\n\n---\n## Extracted Rules from Dynamic Reflection\n"
        markdown_content += f"**Date:** {timestamp}\n"
        markdown_content += f"**Source:** {chat_id}\n"
        markdown_content += f"**Rules Count:** {len(rules)}\n"
        markdown_content += "---\n\n"
        
        for rule in rules:
            category = rule.get('category', 'uncategorized')
            text = rule.get('text', '')
            context = rule.get('context', '')
            evidence = rule.get('evidence', '')
            confidence = rule.get('confidence')
            decay = rule.get('decay')
            confidence_reasoning = rule.get('confidence_reasoning')
            decay_reasoning = rule.get('decay_reasoning')
            
            markdown_content += f"## Category: {category}\n"
            markdown_content += f"**Rule:** {text}\n"
            if context:
                markdown_content += f"**Context:** {context}\n"
            markdown_content += f"**Evidence:** {evidence}\n"
            if confidence is not None:
                markdown_content += f"**Confidence:** {confidence:.2f} ({int(confidence * 100)}%)\n"
            if decay is not None:
                markdown_content += f"**Decay:** {decay:.2f} ({'Specific' if decay > 0.6 else 'General'})\n"
            if confidence_reasoning:
                markdown_content += f"**Confidence Reasoning:** {confidence_reasoning}\n"
            if decay_reasoning:
                markdown_content += f"**Decay Reasoning:** {decay_reasoning}\n"
            markdown_content += "\n"
        
        if rules_file.exists():
            with open(rules_file, 'a', encoding='utf-8') as f:
                f.write(markdown_content)
        else:
            header = "# Dynamic Reflection Rules Database\n"
            header += "This file contains rules extracted from chat analysis.\n"
            header += "Rules are appended automatically from the visualization tool.\n\n"
            with open(rules_file, 'w', encoding='utf-8') as f:
                f.write(header + markdown_content)
        
        logger.info(f"POST /api/rules/save - Success ({len(rules)} rules saved)")
        return jsonify({
            'success': True,
            'message': f'Saved {len(rules)} rules to dynamic_reflection.md',
            'file_path': str(rules_file)
        })
        
    except Exception as e:
        return handle_error('save_rules', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan', methods=['GET'])
def get_plan(chat_id):
    try:
        logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Started")
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        
        if not plan_file.exists():
            logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Not Found")
            return jsonify({'success': False, 'plan': None})
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan = json.load(f)
        
        logger.info(f"GET /api/chat-visualizations/{chat_id}/plan - Success")
        return jsonify({'success': True, 'plan': plan})
        
    except Exception as e:
        return handle_error('get_plan', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/rule-notes', methods=['GET'])
def get_rule_notes(chat_id):
    try:
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Visualization not found'}), 404

        notes_doc = _load_rule_notes(chat_id)
        notes = notes_doc.get("notes", {}) or {}
        return jsonify({'success': True, 'notes': notes})
    except Exception as e:
        return handle_error('get_rule_notes', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/rule-notes', methods=['PUT'])
def update_rule_notes(chat_id):
    try:
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Visualization not found'}), 404

        data = request.json or {}
        notes = data.get('notes', {})
        if not isinstance(notes, dict):
            return jsonify({'success': False, 'error': 'notes must be an object'}), 400

        now_iso = datetime.now().isoformat()
        existing_doc = _load_rule_notes(chat_id)
        existing_notes = existing_doc.get("notes", {}) or {}
        normalized_notes = {}
        for note_key, note_value in notes.items():
            key = str(note_key)
            normalized = _normalize_note_record(chat_id, key, note_value, now_iso)
            prior = existing_notes.get(key, {})
            if isinstance(prior, dict) and prior.get("created_at"):
                normalized["created_at"] = prior.get("created_at")
            normalized_notes[key] = normalized

        notes_doc = {
            "chat_id": chat_id,
            "notes": normalized_notes,
            "created_at": existing_doc.get("created_at") or now_iso,
            "updated_at": now_iso,
        }
        _save_rule_notes(chat_id, notes_doc)

        return jsonify({'success': True, 'notes': normalized_notes})
    except Exception as e:
        return handle_error('update_rule_notes', e)

# Backward-compatible aliases
@visualization_bp.route('/api/chat-visualizations/<chat_id>/favorite-rule-notes', methods=['GET'])
def get_favorite_rule_notes(chat_id):
    return get_rule_notes(chat_id)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/favorite-rule-notes', methods=['PUT'])
def update_favorite_rule_notes(chat_id):
    return update_rule_notes(chat_id)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/extract-plan', methods=['POST'])
def extract_plan(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/extract-plan - Started")
        
        # Check for manual content in request body
        data = request.json or {}
        manual_content = data.get('content')
        
        if manual_content:
            # Use manually provided content
            content = manual_content
            logger.info(f"Using manual content ({len(content)} characters)")
        else:
            # Use chat history from metadata
            metadata = vm.get_visualization(chat_id)
            if not metadata:
                return jsonify({'error': 'Visualization not found'}), 404
            
            content = metadata.get('cleaned_accumulated_content', '')
            if not content:
                return jsonify({'error': 'No chat content available'}), 400
            logger.info(f"Using chat history content ({len(content)} characters)")
        
        prompt = PLAN_EXTRACTION_PROMPT.format(content=content)
        
        logger.info("="*80)
        logger.info("PLAN EXTRACTION - FULL PROMPT SENT TO LLM")
        logger.info("="*80)
        logger.info(prompt)
        logger.info("="*80)
        logger.info(f"PROMPT LENGTH: {len(prompt)} characters")
        logger.info("="*80)
        
        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5"
        )
        
        logger.info("="*80)
        logger.info("PLAN EXTRACTION - FULL LLM RESPONSE")
        logger.info("="*80)
        logger.info(response)
        logger.info("="*80)
        logger.info(f"RESPONSE LENGTH: {len(response)} characters")
        logger.info("="*80)
        
        result = json.loads(strip_markdown_json(response))
        
        logger.info("="*80)
        logger.info("PLAN EXTRACTION - PARSED RESULT")
        logger.info("="*80)
        logger.info(json.dumps(result, indent=2))
        logger.info("="*80)
        
        plan_dir = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / "plan.json"
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        # Get metadata for markdown generation (may not have been loaded if using manual content)
        if not manual_content:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
        else:
            metadata = vm.get_visualization(chat_id)
            chat_name = metadata.get("name", "Unnamed") if metadata else "Unnamed"
            tracking = metadata.get("plan_tracking", {}) if metadata else {}
        
        markdown = plan_to_markdown(chat_id, chat_name, result, tracking)
        
        plan_md_path = get_plan_markdown_path(get_project_root())
        plan_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        mode = get_enforcement_mode()
        if mode == "verification":
            template_file = "visualization_integration.md"
        elif mode == "selective-verification":
            template_file = "selective_verification.md"
        else:
            template_file = "no_verification.md"
        
        template_path = get_project_root() / "backend" / "cli" / "templates" / template_file
        integration_path = get_project_root() / ".clinerules" / "zoro_integration.md"
        if template_path.exists():
            copy2(template_path, integration_path)
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/extract-plan - Success")
        return jsonify({
            'success': True,
            'plan': result,
            'file_path': str(plan_file)
        })
        
    except Exception as e:
        return handle_error('extract_plan', e)

def _deduplicate_rules_in_hierarchy(items, ancestor_rules=None):
    if ancestor_rules is None:
        ancestor_rules = set()
    
    for item in items:
        item_rules = item.get('rules', [])
        unique_rules = []
        
        for rule in item_rules:
            rule_key = (rule.get('category', ''), rule.get('text', ''))
            if rule_key not in ancestor_rules:
                unique_rules.append(rule)
        
        item['rules'] = unique_rules
        
        child_ancestor_rules = ancestor_rules.copy()
        for rule in unique_rules:
            rule_key = (rule.get('category', ''), rule.get('text', ''))
            child_ancestor_rules.add(rule_key)
        
        if item.get('children'):
            _deduplicate_rules_in_hierarchy(item['children'], child_ancestor_rules)


def _populate_inherited_rules(items, parent_rules=None):
    if parent_rules is None:
        parent_rules = []
    
    for item in items:
        inherited_rules = []
        for rule, source in parent_rules:
            clean_rule = {k: v for k, v in rule.items() if k != 'verifications'}
            inherited_rules.append({
                'rule': clean_rule, 
                'source': source,
                'verifications': []
            })
        item['inherited_rules'] = inherited_rules
        
        if item.get('children'):
            child_parent_rules = list(parent_rules)
            for rule in item.get('rules', []):
                child_parent_rules.append((rule, item.get('title', 'Unknown')))
            
            _populate_inherited_rules(item['children'], child_parent_rules)


def _normalize_rule_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _find_matching_kb_item(rule, kb_items, kb_dict):
    kb_id = rule.get('kb_item_id')
    if kb_id and kb_id in kb_dict:
        return kb_dict[kb_id]

    rule_text = _normalize_rule_text(rule.get('text', ''))
    if not rule_text:
        return None

    for kb_item in kb_items:
        kb_content = _normalize_rule_text(kb_item.get('content', ''))
        kb_title = _normalize_rule_text(kb_item.get('title', ''))
        if rule_text == kb_content or (kb_title and rule_text == kb_title):
            return kb_item
    return None


def _sync_rule_with_kb(rule, kb_item):
    # Enforce verbatim rule payload from KB to prevent LLM drift/hallucinated fields.
    rule['kb_item_id'] = kb_item.get('item_id')
    rule['category'] = kb_item.get('category', rule.get('category', 'uncategorized'))
    rule['text'] = kb_item.get('content') or kb_item.get('title', rule.get('text', ''))
    rule['context'] = kb_item.get('context', '')
    rule['evidence'] = kb_item.get('evidence', '')
    rule['confidence'] = kb_item.get('confidence', 0.5)
    rule['decay'] = kb_item.get('decay', 0.5)
    rule['confidence_reasoning'] = kb_item.get('confidence_reasoning', '')
    rule['decay_reasoning'] = kb_item.get('decay_reasoning', '')
    rule['needs_strict_enforcement'] = kb_item.get('is_strict', False)
    rule['is_testable'] = kb_item.get('is_testable', False)


def _canonicalize_rules_from_kb(items, kb_items, kb_dict):
    for item in items:
        for rule in item.get('rules', []):
            kb_item = _find_matching_kb_item(rule, kb_items, kb_dict)
            if kb_item:
                _sync_rule_with_kb(rule, kb_item)

        if item.get('children'):
            _canonicalize_rules_from_kb(item['children'], kb_items, kb_dict)


def _prune_non_kb_rules(items, kb_items, kb_dict):
    for item in items:
        kept_rules = []
        for rule in item.get('rules', []):
            kb_item = _find_matching_kb_item(rule, kb_items, kb_dict)
            if not kb_item:
                continue
            _sync_rule_with_kb(rule, kb_item)
            kept_rules.append(rule)
        item['rules'] = kept_rules

        if item.get('children'):
            _prune_non_kb_rules(item['children'], kb_items, kb_dict)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/retrieve-rules', methods=['POST'])
def retrieve_rules_for_plan(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/retrieve-rules - Started")
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Visualization not found'}), 404
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'No plan found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        rule_retrieval_source = metadata.get('rule_retrieval_source', 'structured')
        logger.info(f"Loading rules from source: {rule_retrieval_source}")
        
        all_rules = []
        
        if rule_retrieval_source == 'structured':
            structured_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if structured_path.exists():
                with open(structured_path, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
                    structured_rules = kb_data.get('items', [])
                    all_rules.extend(structured_rules)
                    logger.info(f"Loaded {len(structured_rules)} structured rules")
        elif rule_retrieval_source == 'unstructured':
            unstructured_dir = get_project_root() / ".zoro" / "rules" / "unstructured"
            if unstructured_dir.exists():
                for rule_file in unstructured_dir.glob("*.md"):
                    with open(rule_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_rules.append({
                            'source_file': rule_file.name,
                            'content': content,
                            'rule': content
                        })
                logger.info(f"Loaded rules from {len(list(unstructured_dir.glob('*.md')))} unstructured files")
        
        if not all_rules:
            error_msg = f"No rules found for source '{rule_retrieval_source}'"
            logger.warning(error_msg)
            return jsonify({'success': False, 'error': error_msg}), 404
        
        # Format rules for POPULATE_RULES_PROMPT
        formatted_rules = []
        for rule in all_rules:
            if rule_retrieval_source == 'structured':
                # Structured KB format - include item_id for post-processing
                formatted_rules.append(f"## KB Item ID: {rule.get('item_id', '')}")
                formatted_rules.append(f"## Category: {rule.get('category', 'uncategorized')}")
                formatted_rules.append(f"**Rule:** {rule.get('content') or rule.get('title', '')}")
                if rule.get('context'):
                    formatted_rules.append(f"**Context:** {rule['context']}")
                if rule.get('evidence'):
                    formatted_rules.append(f"**Evidence:** {rule['evidence']}")
                formatted_rules.append(f"**Favorite:** {str(bool(rule.get('is_favorite', False))).lower()}")
                formatted_rules.append(f"**Strict:** {str(bool(rule.get('is_strict', False))).lower()}")
                if rule.get('confidence') is not None:
                    formatted_rules.append(f"**Confidence:** {rule['confidence']}")
                if rule.get('decay') is not None:
                    formatted_rules.append(f"**Decay:** {rule['decay']}")
                formatted_rules.append("")
            else:
                # Unstructured format - already markdown
                formatted_rules.append(rule.get('content', rule.get('rule', '')))
        
        rules_content = "\n".join(formatted_rules)
        
        prompt = POPULATE_RULES_PROMPT.format(
            plan_json=json.dumps(plan_data, indent=2),
            rules_content=rules_content
        )
        
        logger.info(f"Sending POPULATE_RULES_PROMPT to LLM")
        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5"
        )
        
        enhanced_plan = json.loads(strip_markdown_json(response))
        logger.info(f"LLM returned enhanced plan with substeps and rules")
        
        # Canonicalize retrieved rules against KB (verbatim KB payload only).
        if rule_retrieval_source == 'structured':
            plan_items = enhanced_plan.get('plan', {}).get('items', [])
            kb_dict = {item['item_id']: item for item in all_rules}
            _prune_non_kb_rules(plan_items, all_rules, kb_dict)
            _canonicalize_rules_from_kb(plan_items, all_rules, kb_dict)
            logger.info("Canonicalized rules from KB")
        
        # Deduplicate rules in hierarchy (remove from children if parent has them)
        plan_items = enhanced_plan.get('plan', {}).get('items', [])
        _deduplicate_rules_in_hierarchy(plan_items)
        logger.info(f"Deduplicated rules in hierarchy")
        
        # Populate inherited rules
        _populate_inherited_rules(plan_items)
        logger.info(f"Populated inherited rules")
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_plan, f, indent=2)
        logger.info(f"Saved enhanced plan to {plan_file}")
        
        chat_name = metadata.get("name", "Unnamed")
        tracking = metadata.get("plan_tracking", {})
        markdown = plan_to_markdown(chat_id, chat_name, enhanced_plan, tracking)
        
        plan_md_path = get_plan_markdown_path(get_project_root())
        plan_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        logger.info(f"Regenerated zoro_plan.md with rules and conflicts")
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/retrieve-rules - Success")
        return jsonify({
            'success': True,
            'plan': enhanced_plan
        })
        
    except Exception as e:
        return handle_error('retrieve_rules_for_plan', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/refine-substeps', methods=['POST'])
def refine_substeps(chat_id, item_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/refine-substeps - Started")
        
        data = request.json or {}
        user_guidance = data.get('guidance', '').strip()
        
        if not user_guidance:
            return jsonify({'success': False, 'error': 'Guidance is required'}), 400
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        from backend.visualization.services.visualization_manager import _find_item_in_tree
        phase, _, _ = _find_item_in_tree(items, item_id)
        if not phase:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Visualization not found'}), 404
        
        rule_retrieval_source = metadata.get('rule_retrieval_source', 'structured')
        all_rules = []
        
        if rule_retrieval_source == 'structured':
            structured_path = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if structured_path.exists():
                with open(structured_path, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
                    all_rules = kb_data.get('items', [])
        elif rule_retrieval_source == 'unstructured':
            unstructured_dir = get_project_root() / ".zoro" / "rules" / "unstructured"
            if unstructured_dir.exists():
                for rule_file in unstructured_dir.glob("*.md"):
                    with open(rule_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_rules.append({'source_file': rule_file.name, 'content': content})
        
        formatted_rules = []
        for rule in all_rules:
            if rule_retrieval_source == 'structured':
                formatted_rules.append(f"## KB Item ID: {rule.get('item_id', '')}")
                formatted_rules.append(f"## Category: {rule.get('category', 'uncategorized')}")
                formatted_rules.append(f"**Rule:** {rule.get('content') or rule.get('title', '')}")
                if rule.get('context'):
                    formatted_rules.append(f"**Context:** {rule['context']}")
                if rule.get('evidence'):
                    formatted_rules.append(f"**Evidence:** {rule['evidence']}")
                formatted_rules.append(f"**Favorite:** {str(bool(rule.get('is_favorite', False))).lower()}")
                formatted_rules.append(f"**Strict:** {str(bool(rule.get('is_strict', False))).lower()}")
                if rule.get('confidence') is not None:
                    formatted_rules.append(f"**Confidence:** {rule['confidence']}")
                if rule.get('decay') is not None:
                    formatted_rules.append(f"**Decay:** {rule['decay']}")
                formatted_rules.append("")
            else:
                formatted_rules.append(rule.get('content', ''))
        
        kb_rules = "\n".join(formatted_rules)
        
        prompt = REFINE_SUBSTEPS_PROMPT.format(
            user_guidance=user_guidance,
            phase_json=json.dumps(phase, indent=2),
            kb_rules=kb_rules
        )
        
        logger.info(f"Calling LLM to refine substeps for item {item_id}")
        provider = get_default_provider()
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5"
        )
        
        enhanced_phase = json.loads(strip_markdown_json(response))
        
        phase['children'] = enhanced_phase.get('children', [])
        phase['rules'] = enhanced_phase.get('rules', [])
        
        if rule_retrieval_source == 'structured':
            kb_dict = {item['item_id']: item for item in all_rules}
            children = phase.get('children', [])
            _prune_non_kb_rules([phase] + children, all_rules, kb_dict)
            _canonicalize_rules_from_kb([phase] + children, all_rules, kb_dict)
        
        _recalculate_inherited_rules(items)
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        chat_name = metadata.get("name", "Unnamed")
        tracking = metadata.get("plan_tracking", {})
        markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
        
        plan_md_path = get_plan_markdown_path(get_project_root())
        plan_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/refine-substeps - Success")
        return jsonify({
            'success': True,
            'phase': phase
        })
        
    except Exception as e:
        return handle_error('refine_substeps', e)

@visualization_bp.route('/api/visualization/rule-learning/<chat_id>', methods=['GET'])
def get_rule_learning(chat_id):
    try:
        logger.info(f"GET /api/visualization/rule-learning/{chat_id} - Started")
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'error': 'Visualization not found'}), 404
        
        rules = []
        last_analyzed_index = metadata.get('last_analyzed_token_index', 0)
        
        logger.info(f"GET /api/visualization/rule-learning/{chat_id} - Success (rules: {len(rules)}, analyzed: {last_analyzed_index})")
        return jsonify({
            'success': True,
            'rules': rules,
            'analyzed_tokens': last_analyzed_index
        })
        
    except Exception as e:
        return handle_error('get_rule_learning', e)

@visualization_bp.route('/api/visualization/supervision/<chat_id>', methods=['GET'])
def get_supervision(chat_id):
    try:
        logger.info(f"GET /api/visualization/supervision/{chat_id} - Started")
        
        monitoring_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "monitoring.json"
        metadata_path = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "metadata.json"
        
        # Always read metadata for token stats
        current_tokens = 0
        last_supervised_tokens = 0
        
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            supervision_content = metadata.get('supervision_cleaned_accumulated_content', '')
            if supervision_content:
                try:
                    enc = tiktoken.get_encoding("cl100k_base")
                    current_tokens = len(enc.encode(supervision_content))
                except Exception:
                    current_tokens = len(supervision_content.split())
            
            last_supervised_tokens = metadata.get('last_supervised_token_index', 0)
        
        # Calculate token stats regardless of monitoring.json existence
        tokens_since_last = current_tokens - last_supervised_tokens
        threshold = _watcher.TOKEN_INTERVAL
        progress_percent = min((tokens_since_last / threshold) * 100, 100) if threshold > 0 else 0
        
        token_stats = {
            'current_tokens': current_tokens,
            'last_supervised_tokens': last_supervised_tokens,
            'tokens_since_last': tokens_since_last,
            'threshold': threshold,
            'progress_percent': progress_percent
        }
        
        # Read monitoring history if file exists
        history = []
        if monitoring_file.exists():
            with open(monitoring_file, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                history = data
            elif isinstance(data, dict):
                history = [data]
        
        logger.info(f"GET /api/visualization/supervision/{chat_id} - Success (history: {len(history)} entries)")
        return jsonify({
            'success': True,
            'supervision_history': history,
            'token_stats': token_stats
        })
        
    except Exception as e:
        return handle_error('get_supervision', e)

@visualization_bp.route('/api/visualization/supervision/<chat_id>/resolve', methods=['POST'])
def resolve_supervision(chat_id):
    try:
        logger.info(f"POST /api/visualization/supervision/{chat_id}/resolve - Started")
        
        data = request.json or {}
        timestamp = data.get('timestamp')
        
        if not timestamp:
            return jsonify({'success': False, 'error': 'Missing timestamp'}), 400
        
        monitoring_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "monitoring.json"
        
        if not monitoring_file.exists():
            return jsonify({'success': False, 'error': 'No monitoring data found'}), 404
        
        with open(monitoring_file, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            history = data
        elif isinstance(data, dict):
            history = [data]
        else:
            return jsonify({'success': False, 'error': 'Invalid monitoring data'}), 500
        
        found = False
        for entry in history:
            if entry.get('timestamp') == timestamp:
                entry['resolved'] = True
                found = True
                break
        
        if not found:
            return jsonify({'success': False, 'error': 'Supervision entry not found'}), 404
        
        with open(monitoring_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"POST /api/visualization/supervision/{chat_id}/resolve - Success")
        return jsonify({'success': True})
        
    except Exception as e:
        return handle_error('resolve_supervision', e)

@visualization_bp.route('/api/chat-visualizations/<chat_id>/resolve-conflict', methods=['POST'])
def resolve_conflict(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/resolve-conflict - Started")
        
        data = request.json or {}
        item_id = data.get('item_id')
        conflict_id = data.get('conflict_id')
        chosen_rule_index = data.get('chosen_rule_index')
        
        if not item_id or not conflict_id or chosen_rule_index is None:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # Load plan.json
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r') as f:
            plan_data = json.load(f)
        
        # Find the target item in the plan tree
        def find_and_resolve_conflict(items):
            for item in items:
                if item.get('id') == item_id:
                    # Find the conflict
                    conflicts = item.get('conflicts', [])
                    conflict = None
                    conflict_idx = -1
                    
                    for idx, c in enumerate(conflicts):
                        if c.get('conflict_id') == conflict_id:
                            conflict = c
                            conflict_idx = idx
                            break
                    
                    if not conflict:
                        return {'error': 'Conflict not found'}
                    
                    # Mark conflict as resolved
                    conflict['resolved'] = True
                    conflict['chosen_rule_index'] = chosen_rule_index
                    conflict['resolved_at'] = datetime.now().isoformat()
                    
                    # Get the rule indices involved in this conflict for this item
                    rule_indices = conflict.get('rule_indices', {}).get(item_id, [])
                    
                    if chosen_rule_index not in rule_indices:
                        return {'error': f'Chosen rule index {chosen_rule_index} not in conflict'}
                    
                    # Remove unchosen rules (in reverse order to avoid index shifting)
                    rules = item.get('rules', [])
                    indices_to_remove = [idx for idx in rule_indices if idx != chosen_rule_index]
                    indices_to_remove.sort(reverse=True)
                    
                    for idx in indices_to_remove:
                        if idx < len(rules):
                            rules.pop(idx)
                    
                    item['rules'] = rules
                    
                    # Recompute has_unresolved_conflicts
                    unresolved_count = sum(1 for c in conflicts if not c.get('resolved', False))
                    item['has_unresolved_conflicts'] = unresolved_count > 0
                    
                    return {
                        'success': True,
                        'remaining_conflicts': unresolved_count,
                        'item_id': item_id,
                        'conflict_id': conflict_id
                    }
                
                # Recurse into children
                if item.get('children'):
                    result = find_and_resolve_conflict(item['children'])
                    if result:
                        return result
            
            return None
        
        items = plan_data.get('plan', {}).get('items', [])
        result = find_and_resolve_conflict(items)
        
        if not result:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        # Save updated plan.json
        with open(plan_file, 'w') as f:
            json.dump(plan_data, f, indent=2)
        
        # Regenerate .rules/zoro_plan.md
        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/resolve-conflict - Success")
        return jsonify(result)
    
    except Exception as e:
        return handle_error('resolve_conflict', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/supervise', methods=['POST'])
def supervise_chat_visualization(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/supervise - Started")
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'error': 'Visualization not found'}), 404
        
        supervision_cleaned_content = metadata.get('supervision_cleaned_accumulated_content', '')
        if not supervision_cleaned_content:
            return jsonify({'error': 'No content to supervise'}), 400
        
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            all_tokens = enc.encode(supervision_cleaned_content)
            total_tokens = len(all_tokens)
        except Exception:
            all_tokens = supervision_cleaned_content.split()
            total_tokens = len(all_tokens)
        
        last_supervised_index = metadata.get('last_supervised_token_index', 0)
        
        if last_supervised_index >= total_tokens:
            return jsonify({
                'supervision': None,
                'total_tokens': total_tokens,
                'supervised_tokens': last_supervised_index,
                'remaining_tokens': 0,
                'all_supervised': True
            })
        
        max_tokens = 200000
        start_index = last_supervised_index
        end_index = min(start_index + max_tokens, total_tokens)
        
        try:
            window_tokens = all_tokens[start_index:end_index]
            content_window = enc.decode(window_tokens)
        except Exception:
            content_window = supervision_cleaned_content[start_index:end_index]
        
        logger.info(f"Supervising tokens {start_index}-{end_index} of {total_tokens}")
        
        from backend.visualization.services.supervisor_agent import SupervisorAgent
        supervisor = SupervisorAgent()
        result = supervisor.supervise(chat_id, content_window)
        
        monitoring_dir = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id
        monitoring_dir.mkdir(parents=True, exist_ok=True)
        monitoring_file = monitoring_dir / "monitoring.json"
        
        history = []
        if monitoring_file.exists():
            try:
                with open(monitoring_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        history = data
                    elif isinstance(data, dict):
                        history = [data]
            except Exception:
                pass
        
        history.append({
            **result,
            "saved_at": datetime.now().isoformat()
        })
        history = history[-20:]
        
        with open(monitoring_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        metadata['last_supervised_token_index'] = end_index
        vm._save_metadata(chat_id, metadata)
        
        response_data = {
            'supervision': result,
            'total_tokens': total_tokens,
            'supervised_tokens': end_index,
            'remaining_tokens': total_tokens - end_index,
            'all_supervised': end_index >= total_tokens
        }
        logger.info(f"POST /api/chat-visualizations/{chat_id}/supervise - Success ({end_index}/{total_tokens} tokens)")
        return jsonify(response_data)
        
    except Exception as e:
        return handle_error('supervise_chat_visualization', e)


@visualization_bp.route('/api/visualization/<chat_id>/enforce-item/<item_id>', methods=['POST'])
def enforce_single_item_api(chat_id, item_id):
    try:
        logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Started")
        
        metadata = vm.get_visualization(chat_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Visualization not found'}), 404
        
        supervision_cleaned_content = metadata.get('supervision_cleaned_accumulated_content', '')
        if not supervision_cleaned_content:
            return jsonify({'success': False, 'error': 'No content to enforce'}), 400
        
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            all_tokens = enc.encode(supervision_cleaned_content)
            total_tokens = len(all_tokens)
        except Exception:
            all_tokens = supervision_cleaned_content.split()
            total_tokens = len(all_tokens)
        
        ENFORCEMENT_WINDOW = 75000
        window_start = max(0, total_tokens - ENFORCEMENT_WINDOW)
        
        try:
            window_tokens = all_tokens[window_start:]
            content_window = enc.decode(window_tokens)
        except Exception:
            content_window = supervision_cleaned_content[window_start:]
        
        logger.info(f"Enforcing item {item_id}: sliding window with last {len(window_tokens)} tokens")
        
        from backend.visualization.services.enforcement_agent import EnforcementAgent
        agent = EnforcementAgent()
        result = agent.enforce_single_item(chat_id, item_id, content_window)
        
        if result.get('error'):
            logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Error: {result['error']}")
            return jsonify({'success': False, 'error': result['error']}), 400
        
        logger.info(f"POST /api/visualization/{chat_id}/enforce-item/{item_id} - Success")
        return jsonify({
            'success': True,
            'enforcement': result
        })
        
    except Exception as e:
        return handle_error('enforce_single_item', e)


@visualization_bp.route('/api/visualization/enforcement-history/<chat_id>', methods=['GET'])
def get_enforcement_history_api(chat_id):
    try:
        logger.info(f"GET /api/visualization/enforcement-history/{chat_id} - Started")
        
        from backend.visualization.services.enforcement_agent import get_enforcement_history
        history = get_enforcement_history(chat_id)
        
        logger.info(f"GET /api/visualization/enforcement-history/{chat_id} - Success ({len(history)} runs)")
        return jsonify({'success': True, 'enforcement_history': history})
    except Exception as e:
        return handle_error('get_enforcement_history', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>', methods=['DELETE'])
def delete_plan_item(chat_id, item_id):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Started")
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        if not _delete_item_recursive(items, item_id):
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        _renumber_items(items)
        _recalculate_inherited_rules(items)
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        metadata = vm.get_visualization(chat_id)
        if metadata:
            tracking = metadata.get("plan_tracking", {})
            if item_id in tracking:
                del tracking[item_id]
                metadata["plan_tracking"] = tracking
                vm._save_metadata(chat_id, metadata)
            
            chat_name = metadata.get("name", "Unnamed")
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Success")
        return jsonify({'success': True})
        
    except Exception as e:
        return handle_error('delete_plan_item', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>', methods=['PUT'])
def update_plan_item(chat_id, item_id):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Started")

        data = request.json or {}
        title = data.get('title')
        description = data.get('description')

        if title is None and description is None:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)

        items = plan_data.get('plan', {}).get('items', [])
        target_item, _, _ = _find_item_in_tree(items, item_id)
        if not target_item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        if title is not None:
            target_item['title'] = str(title).strip()
        if description is not None:
            target_item['description'] = str(description)

        _recalculate_inherited_rules(items)

        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)

        metadata = vm.get_visualization(chat_id)
        if metadata:
            tracking = metadata.get("plan_tracking", {})
            chat_name = metadata.get("name", "Unnamed")
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id} - Success")
        return jsonify({'success': True, 'item': target_item})
    except Exception as e:
        return handle_error('update_plan_item', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items', methods=['POST'])
def add_plan_item(chat_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items - Started")
        
        data = request.json or {}
        parent_id = data.get('parent_id')
        title = data.get('title', '').strip()
        description = data.get('description', '')
        position = data.get('position')
        
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        import uuid
        new_item = {
            'id': str(uuid.uuid4())[:8],
            'number': '',
            'title': title,
            'description': description,
            'children': [],
            'rules': [],
            'inherited_rules': []
        }
        
        if parent_id:
            from backend.visualization.services.visualization_manager import _find_item_in_tree
            parent, _, _ = _find_item_in_tree(items, parent_id)
            if not parent:
                return jsonify({'success': False, 'error': 'Parent item not found'}), 404
            
            if 'children' not in parent:
                parent['children'] = []
            
            if position is not None and 0 <= position <= len(parent['children']):
                parent['children'].insert(position, new_item)
            else:
                parent['children'].append(new_item)
        else:
            if position is not None and 0 <= position <= len(items):
                items.insert(position, new_item)
            else:
                items.append(new_item)
        
        _renumber_items(items)
        _recalculate_inherited_rules(items)
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items - Success (new item: {new_item['id']})")
        return jsonify({'success': True, 'item': new_item})
        
    except Exception as e:
        return handle_error('add_plan_item', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>', methods=['DELETE'])
def delete_plan_item_rule(chat_id, item_id, rule_index):
    try:
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index} - Started")
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        from backend.visualization.services.visualization_manager import _find_item_in_tree
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        rules = item.get('rules', [])
        if rule_index < 0 or rule_index >= len(rules):
            return jsonify({'success': False, 'error': 'Rule index out of bounds'}), 400
        
        rules.pop(rule_index)
        item['rules'] = rules
        
        _recalculate_inherited_rules(items)
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"DELETE /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index} - Success")
        return jsonify({'success': True})
        
    except Exception as e:
        return handle_error('delete_plan_item_rule', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules', methods=['POST'])
def add_plan_item_rule(chat_id, item_id):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules - Started")
        
        data = request.json or {}
        kb_item_id = data.get('kb_item_id')
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        from backend.visualization.services.visualization_manager import _find_item_in_tree
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        if kb_item_id:
            kb_file = get_project_root() / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if not kb_file.exists():
                return jsonify({'success': False, 'error': 'Knowledge base not found'}), 404
            
            with open(kb_file, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
            
            kb_items = kb_data.get('items', [])
            kb_rule = None
            for kb_item in kb_items:
                if kb_item.get('item_id') == kb_item_id:
                    kb_rule = kb_item
                    break
            
            if not kb_rule:
                return jsonify({'success': False, 'error': 'Rule not found in knowledge base'}), 404
            
            new_rule = {
                'category': kb_rule.get('category', 'uncategorized'),
                'text': kb_rule.get('content') or kb_rule.get('title', ''),
                'context': kb_rule.get('context', ''),
                'evidence': kb_rule.get('evidence', ''),
                'confidence': kb_rule.get('confidence'),
                'decay': kb_rule.get('decay'),
                'confidence_reasoning': kb_rule.get('confidence_reasoning', ''),
                'decay_reasoning': kb_rule.get('decay_reasoning', ''),
                'kb_item_id': kb_item_id,
                'needs_strict_enforcement': kb_rule.get('is_strict', False),
                'is_testable': kb_rule.get('is_testable', False)
            }
        else:
            new_rule = {
                'category': data.get('category', 'uncategorized'),
                'text': data.get('text', ''),
                'context': data.get('context', ''),
                'evidence': data.get('evidence', ''),
                'confidence': data.get('confidence'),
                'decay': data.get('decay'),
                'confidence_reasoning': data.get('confidence_reasoning', ''),
                'decay_reasoning': data.get('decay_reasoning', '')
            }
            
            if not new_rule['text']:
                return jsonify({'success': False, 'error': 'Rule text is required'}), 400
        
        if 'rules' not in item:
            item['rules'] = []
        
        item['rules'].append(new_rule)
        
        _recalculate_inherited_rules(items)
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules - Success")
        return jsonify({'success': True, 'rule': new_rule})
        
    except Exception as e:
        return handle_error('add_plan_item_rule', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/move', methods=['POST'])
def move_plan_item_rule(chat_id, item_id, rule_index):
    try:
        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/move - Started")

        data = request.json or {}
        source_type = data.get('source_type', 'own')
        direction = data.get('direction')
        target_item_id = data.get('target_item_id')

        if source_type not in ['own', 'inherited']:
            return jsonify({'success': False, 'error': 'Invalid source_type'}), 400
        if direction not in ['up', 'down', 'adopt']:
            return jsonify({'success': False, 'error': 'Invalid direction'}), 400

        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)

        items = plan_data.get('plan', {}).get('items', [])
        item, parent, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        moved_rule = None
        destination_item = None

        if source_type == 'own':
            rules = item.get('rules', [])
            if rule_index < 0 or rule_index >= len(rules):
                return jsonify({'success': False, 'error': 'Rule index out of bounds'}), 400

            moved_rule = rules.pop(rule_index)
            item['rules'] = rules

            if direction == 'up':
                if not parent:
                    return jsonify({'success': False, 'error': 'Cannot move up: item has no parent'}), 400
                if 'rules' not in parent:
                    parent['rules'] = []
                parent['rules'].append(moved_rule)
                destination_item = parent
            elif direction == 'down':
                children = item.get('children', [])
                if not children:
                    return jsonify({'success': False, 'error': 'Cannot move down: item has no children'}), 400

                if target_item_id:
                    child = next((c for c in children if c.get('id') == target_item_id), None)
                    if not child:
                        return jsonify({'success': False, 'error': 'target_item_id must be a direct child of source item'}), 400
                    destination_item = child
                else:
                    if len(children) != 1:
                        return jsonify({'success': False, 'error': 'Multiple children found; target_item_id is required'}), 400
                    destination_item = children[0]

                if 'rules' not in destination_item:
                    destination_item['rules'] = []
                destination_item['rules'].append(moved_rule)
            else:
                return jsonify({'success': False, 'error': 'Direction not supported for own rules'}), 400

        else:
            if direction != 'adopt':
                return jsonify({'success': False, 'error': 'Inherited rules only support direction=adopt'}), 400

            inherited_rules = item.get('inherited_rules', [])
            if rule_index < 0 or rule_index >= len(inherited_rules):
                return jsonify({'success': False, 'error': 'Inherited rule index out of bounds'}), 400

            inherited_entry = inherited_rules[rule_index]
            moved_rule = dict(inherited_entry.get('rule', {}))
            destination_item = item
            if 'rules' not in item:
                item['rules'] = []
            item['rules'].append(moved_rule)

        _recalculate_inherited_rules(items)

        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)

        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)

            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

        logger.info(f"POST /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/move - Success")
        return jsonify({
            'success': True,
            'moved_rule': moved_rule,
            'from_item_id': item_id,
            'to_item_id': destination_item.get('id') if destination_item else item_id
        })

    except Exception as e:
        return handle_error('move_plan_item_rule', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/strict-enforcement', methods=['PUT'])
def toggle_rule_strict_enforcement_api(chat_id, item_id, rule_index):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - Started")
        
        data = request.json or {}
        enabled = data.get('enabled', False)
        
        rule, error = vm.toggle_rule_strict_enforcement(chat_id, item_id, rule_index, enabled)
        
        if error:
            logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - Error: {error}")
            return jsonify({'success': False, 'error': error}), 404
        
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/strict-enforcement - Success")
        return jsonify({'success': True, 'rule': rule})
        
    except Exception as e:
        return handle_error('toggle_rule_strict_enforcement', e)


@visualization_bp.route('/api/chat-visualizations/<chat_id>/plan/items/<item_id>/rules/<int:rule_index>/testable', methods=['PUT'])
def toggle_rule_testable_api(chat_id, item_id, rule_index):
    try:
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/testable - Started")
        
        data = request.json or {}
        enabled = data.get('enabled', False)
        
        plan_file = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        if not plan_file.exists():
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        items = plan_data.get('plan', {}).get('items', [])
        
        from backend.visualization.services.visualization_manager import _find_item_in_tree
        item, _, _ = _find_item_in_tree(items, item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        rules = item.get('rules', [])
        if rule_index < 0 or rule_index >= len(rules):
            return jsonify({'success': False, 'error': 'Rule index out of bounds'}), 400
        
        rules[rule_index]['is_testable'] = enabled
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2)
        
        metadata = vm.get_visualization(chat_id)
        if metadata:
            chat_name = metadata.get("name", "Unnamed")
            tracking = metadata.get("plan_tracking", {})
            markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
            
            plan_md_path = get_plan_markdown_path(get_project_root())
            plan_md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"PUT /api/chat-visualizations/{chat_id}/plan/items/{item_id}/rules/{rule_index}/testable - Success")
        return jsonify({'success': True, 'rule': rules[rule_index]})
        
    except Exception as e:
        return handle_error('toggle_rule_testable', e)
