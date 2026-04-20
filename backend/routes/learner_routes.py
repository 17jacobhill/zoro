from flask import Blueprint, request, jsonify
import json
import logging
from pathlib import Path

from backend.learner.chat_parser import ChatParser
from backend.learner.categorizer import TaskCategorizer
from backend.learner.learning import process_tasks_v3
from backend.globals.schemas import Task
from backend.utils import get_project_root
from backend.cli.cli import mark_file_processed
from backend.globals.tag_registry import TagRegistry

learner_bp = Blueprint('learner', __name__)
logger = logging.getLogger(__name__)

def handle_error(endpoint_name, error, status_code=500):
    logger.error(f"Error in {endpoint_name}: {str(error)}", exc_info=True)
    return jsonify({'success': False, 'error': str(error)}), status_code

@learner_bp.route('/api/parse', methods=['POST'])
def parse_chat():
    logs = []
    
    def log_fn(msg):
        print(msg)
        logs.append({'type': 'info', 'message': msg})
    
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        text = file.read().decode('utf-8')
        parser = ChatParser(debug=True, logger=log_fn)
        tasks = parser.parse(text)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks),
            'logs': logs
        })
    except Exception as e:
        logger.error(f"Error in parse_chat: {str(e)}", exc_info=True)
        logs.append({'type': 'error', 'message': f'Error: {str(e)}'})
        return jsonify({'success': False, 'error': str(e), 'logs': logs}), 500

@learner_bp.route('/api/categorize', methods=['POST'])
def categorize():
    try:
        data = request.json
        tasks = data.get('tasks', [])
        
        if not tasks:
            return jsonify({'error': 'No tasks provided'}), 400
        
        categorizer = TaskCategorizer()
        suggestions = categorizer.categorize_batch(tasks)
        
        return jsonify({'success': True, 'suggestions': suggestions})
    except Exception as e:
        return handle_error('categorize', e)

@learner_bp.route('/api/analyze-batch', methods=['POST'])
def analyze_batch():
    try:
        data = request.json
        tasks = data.get('tasks', [])
        user_name = data.get('user_name', 'User')
        chat_name = data.get('chat', 'default')
        
        if not tasks:
            return jsonify({'error': 'No tasks provided'}), 400
        
        task_objects = [Task(**t) for t in tasks]
        result = process_tasks_v3(task_objects, user_name, chat_name)
        analyzed_tasks = [t.model_dump() for t in result.analyzed_tasks]
        
        return jsonify({
            'success': True,
            'analyzed_tasks': analyzed_tasks,
            'count': len(analyzed_tasks)
        })
    except Exception as e:
        return handle_error('analyze_batch', e)

@learner_bp.route('/api/chats', methods=['GET'])
def get_chats():
    try:
        root = get_project_root()
        
        categorized_dir = root / ".zoro" / "generated" / "categorized"
        analyzed_dir = root / ".zoro" / "generated" / "analyzed"
        
        chats = set()
        
        if categorized_dir.exists():
            cat_files = list(categorized_dir.glob("*.json"))
            logger.info(f"CATEGORIZED: {categorized_dir} -> {[f.stem for f in cat_files]}")
            chats.update(f.stem for f in cat_files)
        else:
            logger.warning(f"CATEGORIZED DIR NOT FOUND: {categorized_dir}")
        
        if analyzed_dir.exists():
            ana_files = list(analyzed_dir.glob("*.json"))
            logger.info(f"ANALYZED: {analyzed_dir} -> {[f.stem for f in ana_files]}")
            chats.update(f.stem for f in ana_files)
        else:
            logger.warning(f"ANALYZED DIR NOT FOUND: {analyzed_dir}")
        
        logger.info(f"FINAL CHATS: {sorted(list(chats))}")
        return jsonify({'success': True, 'chats': sorted(list(chats))})
    except Exception as e:
        return handle_error('get_chats', e)

@learner_bp.route('/api/categorized-tasks', methods=['GET'])
def get_categorized_tasks():
    try:
        root = get_project_root()
        chat = request.args.get('chat', 'default')
        path = root / ".zoro" / "generated" / "categorized" / f"{chat}.json"
        
        if not path.exists():
            return jsonify({'success': True, 'tasks': []})
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({'success': True, 'tasks': data.get('tasks', [])})
    except Exception as e:
        return handle_error('get_categorized_tasks', e)

@learner_bp.route('/api/categorized-tasks', methods=['POST'])
def save_categorized_tasks():
    try:
        data = request.json
        tasks = data.get('tasks', [])
        chat = data.get('chat', 'default')
        
        if not tasks:
            return jsonify({'error': 'No tasks provided'}), 400
        
        root = get_project_root()
        categorized_dir = root / ".zoro" / "generated" / "categorized"
        categorized_dir.mkdir(parents=True, exist_ok=True)
        
        path = categorized_dir / f"{chat}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'tasks': tasks}, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'count': len(tasks)})
    except Exception as e:
        return handle_error('save_categorized_tasks', e)

@learner_bp.route('/api/analyzed-tasks', methods=['GET'])
def get_analyzed_tasks():
    try:
        root = get_project_root()
        chat = request.args.get('chat', 'default')
        path = root / ".zoro" / "generated" / "analyzed" / f"{chat}.json"
        
        if not path.exists():
            return jsonify({'success': True, 'analyzed_tasks': []})
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({'success': True, 'analyzed_tasks': data.get('analyzed_tasks', [])})
    except Exception as e:
        return handle_error('get_analyzed_tasks', e)

@learner_bp.route('/api/analyzed-tasks', methods=['POST'])
def save_analyzed_tasks():
    try:
        data = request.json
        tasks = data.get('analyzed_tasks', [])
        chat = data.get('chat', 'default')
        
        if not tasks:
            return jsonify({'error': 'No tasks provided'}), 400
        
        root = get_project_root()
        analyzed_dir = root / ".zoro" / "generated" / "analyzed"
        analyzed_dir.mkdir(parents=True, exist_ok=True)
        
        path = analyzed_dir / f"{chat}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'analyzed_tasks': tasks}, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'count': len(tasks)})
    except Exception as e:
        return handle_error('save_analyzed_tasks', e)

@learner_bp.route('/api/learner-chats/<chat_id>', methods=['DELETE'])
def delete_learner_chat(chat_id):
    try:
        logger.info(f"DELETE /api/learner-chats/{chat_id} - Started")
        root = get_project_root()
        
        deleted_files = []
        categorized_path = root / ".zoro" / "generated" / "categorized" / f"{chat_id}.json"
        analyzed_path = root / ".zoro" / "generated" / "analyzed" / f"{chat_id}.json"
        
        if categorized_path.exists():
            categorized_path.unlink()
            deleted_files.append(str(categorized_path))
        
        if analyzed_path.exists():
            analyzed_path.unlink()
            deleted_files.append(str(analyzed_path))
        
        if not deleted_files:
            logger.info(f"DELETE /api/learner-chats/{chat_id} - Not Found")
            return jsonify({'success': False, 'error': 'Chat not found'}), 404
        
        logger.info(f"DELETE /api/learner-chats/{chat_id} - Success")
        return jsonify({
            'success': True,
            'deleted': deleted_files,
            'chat_id': chat_id
        })
    except Exception as e:
        return handle_error('delete_learner_chat', e)

@learner_bp.route('/api/learner-chats/<chat>/tasks/<task_id>/rules/<rule_id>', methods=['PATCH'])
def update_rule(chat, task_id, rule_id):
    try:
        logger.info(f"PATCH /api/learner-chats/{chat}/tasks/{task_id}/rules/{rule_id} - Started")
        root = get_project_root()
        path = root / ".zoro" / "generated" / "analyzed" / f"{chat}.json"
        
        if not path.exists():
            logger.info(f"PATCH rule - Chat not found: {chat}")
            return jsonify({'success': False, 'error': 'Chat not found'}), 404
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        task = next((t for t in data.get('analyzed_tasks', []) if t['task_id'] == task_id), None)
        if not task:
            logger.info(f"PATCH rule - Task not found: {task_id}")
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        rule = next((r for r in task.get('rules', []) if r['rule_id'] == rule_id), None)
        if not rule:
            logger.info(f"PATCH rule - Rule not found: {rule_id}")
            return jsonify({'success': False, 'error': 'Rule not found'}), 404
        
        updates = request.json
        if 'rule' in updates:
            rule['rule'] = updates['rule']
        if 'reasoning' in updates:
            rule['reasoning'] = updates['reasoning']
        if 'confidence' in updates:
            confidence = int(updates['confidence'])
            if confidence < 1 or confidence > 10:
                return jsonify({'success': False, 'error': 'Confidence must be 1-10'}), 400
            rule['confidence'] = confidence
        if 'decay' in updates:
            decay = int(updates['decay'])
            if decay < 1 or decay > 10:
                return jsonify({'success': False, 'error': 'Decay must be 1-10'}), 400
            rule['decay'] = decay
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"PATCH rule - Success")
        return jsonify({'success': True, 'rule': rule})
    except Exception as e:
        return handle_error('update_rule', e)

@learner_bp.route('/api/learner-chats/<chat>/tasks/<task_id>/rules/<rule_id>', methods=['DELETE'])
def delete_rule(chat, task_id, rule_id):
    try:
        logger.info(f"DELETE /api/learner-chats/{chat}/tasks/{task_id}/rules/{rule_id} - Started")
        root = get_project_root()
        path = root / ".zoro" / "generated" / "analyzed" / f"{chat}.json"
        
        if not path.exists():
            logger.info(f"DELETE rule - Chat not found: {chat}")
            return jsonify({'success': False, 'error': 'Chat not found'}), 404
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        task = next((t for t in data.get('analyzed_tasks', []) if t['task_id'] == task_id), None)
        if not task:
            logger.info(f"DELETE rule - Task not found: {task_id}")
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        original_count = len(task.get('rules', []))
        task['rules'] = [r for r in task.get('rules', []) if r['rule_id'] != rule_id]
        
        if len(task['rules']) == original_count:
            logger.info(f"DELETE rule - Rule not found: {rule_id}")
            return jsonify({'success': False, 'error': 'Rule not found'}), 404
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"DELETE rule - Success")
        return jsonify({'success': True, 'rule_id': rule_id})
    except Exception as e:
        logger.error(f"DELETE rule - Failed: {str(e)}", exc_info=True)
        return handle_error('delete_rule', e)

@learner_bp.route('/api/learner/tags', methods=['GET'])
def get_learner_tags():
    try:
        logger.info("GET /api/learner/tags - Started")
        registry = TagRegistry('learner_tags.json')
        tag_counts = registry.list_all_tags()
        tag_names = sorted(list(tag_counts.keys()))
        logger.info(f"GET /api/learner/tags - Success ({len(tag_names)} tags)")
        return jsonify({'success': True, 'tags': tag_names})
    except Exception as e:
        return handle_error('get_learner_tags', e)

@learner_bp.route('/api/learner/chats/<chat_name>/tags', methods=['GET'])
def get_learner_chat_tags(chat_name):
    try:
        logger.info(f"GET /api/learner/chats/{chat_name}/tags - Started")
        registry = TagRegistry('learner_tags.json')
        tags = registry.get_tags(chat_name)
        logger.info(f"GET /api/learner/chats/{chat_name}/tags - Success ({len(tags)} tags)")
        return jsonify({'success': True, 'tags': tags})
    except Exception as e:
        return handle_error('get_learner_chat_tags', e)

@learner_bp.route('/api/learner/tags/assign', methods=['POST'])
def assign_learner_tags():
    try:
        logger.info("POST /api/learner/tags/assign - Started")
        data = request.json or {}
        chat_name = (data.get('chat_name') or '').strip()
        tags = data.get('tags', [])
        
        if not chat_name:
            return jsonify({'success': False, 'error': 'Missing chat_name'}), 400
        if not tags:
            return jsonify({'success': False, 'error': 'Missing tags'}), 400
        
        registry = TagRegistry('learner_tags.json')
        registry.add_tags(chat_name, tags)
        
        updated_tags = registry.get_tags(chat_name)
        logger.info(f"POST /api/learner/tags/assign - Success ({len(tags)} tags assigned to {chat_name})")
        return jsonify({'success': True, 'chat_name': chat_name, 'tags': updated_tags})
    except Exception as e:
        return handle_error('assign_learner_tags', e)

@learner_bp.route('/api/learner/tags/remove', methods=['DELETE'])
def remove_learner_tags():
    try:
        logger.info("DELETE /api/learner/tags/remove - Started")
        data = request.json or {}
        chat_name = (data.get('chat_name') or '').strip()
        tags = data.get('tags', [])
        
        if not chat_name:
            return jsonify({'success': False, 'error': 'Missing chat_name'}), 400
        if not tags:
            return jsonify({'success': False, 'error': 'Missing tags'}), 400
        
        registry = TagRegistry('learner_tags.json')
        registry.remove_tags(chat_name, tags)
        
        updated_tags = registry.get_tags(chat_name)
        logger.info(f"DELETE /api/learner/tags/remove - Success ({len(tags)} tags removed from {chat_name})")
        return jsonify({'success': True, 'chat_name': chat_name, 'tags': updated_tags})
    except Exception as e:
        return handle_error('remove_learner_tags', e)

@learner_bp.route('/api/mark-processed', methods=['POST'])
def mark_processed():
    try:
        logger.info("POST /api/mark-processed - Started")
        data = request.json or {}
        filename = (data.get('filename') or '').strip()
        
        if not filename:
            return jsonify({'success': False, 'error': 'Missing filename'}), 400
        
        mark_file_processed(filename)
        logger.info(f"POST /api/mark-processed - Success: {filename}")
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return handle_error('mark_processed', e)