from flask import Blueprint, request, jsonify
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from backend.assistant.plan_manager import load_metadata, load_plan, save_plan, save_metadata
from backend.assistant.chat_recommendations import get_chat_recommendations
from backend.globals.schemas import PlanEdge, AuditEntry, RuleRef, FavoritesDB, RuleV2
from backend.utils import get_project_root
from backend.globals.tag_registry import TagRegistry
from backend.learner.learning import load_all_analyzed_tasks

assistant_bp = Blueprint('assistant', __name__)
logger = logging.getLogger(__name__)

def handle_error(endpoint_name, error, status_code=500):
    logger.error(f"Error in {endpoint_name}: {str(error)}", exc_info=True)
    return jsonify({'success': False, 'error': str(error)}), status_code

@assistant_bp.route('/api/assistant-chats', methods=['GET'])
def get_assistant_chats():
    try:
        logger.info("GET /api/assistant-chats - Started")
        metadata = load_metadata()
        chats = [c.model_dump() for c in metadata.chats]
        logger.info(f"GET /api/assistant-chats - Success ({len(chats)} chats)")
        return jsonify({'success': True, 'chats': chats})
    except Exception as e:
        return handle_error('get_assistant_chats', e)

@assistant_bp.route('/api/plan/<chatId>', methods=['GET'])
def get_plan(chatId):
    try:
        logger.info(f"GET /api/plan/{chatId} - Started")
        plan = load_plan(chatId)
        
        if not plan:
            logger.info(f"GET /api/plan/{chatId} - Not Found")
            return jsonify({'error': 'Plan not found'}), 404
        
        logger.info(f"GET /api/plan/{chatId} - Success")
        return jsonify(plan.model_dump(by_alias=True))
    except Exception as e:
        return handle_error('get_plan', e)

@assistant_bp.route('/api/plan/<chatId>/nodes/<nodeId>/substeps', methods=['POST'])
def add_plan_node_substep(chatId, nodeId):
    try:
        logger.info(f"POST /api/plan/{chatId}/nodes/{nodeId}/substeps - Started")

        plan = load_plan(chatId)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        node = next((n for n in plan.nodes if n.id == nodeId), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404

        data = request.json or {}
        text = (data.get('text') or '').strip()
        requested_id = (data.get('id') or '').strip() or None

        if not text:
            return jsonify({'success': False, 'error': 'Missing text'}), 400

        if node.type != 'code-style':
            return jsonify({'success': False, 'error': 'Substeps only supported for code-style nodes'}), 400

        if node.substeps is None:
            node.substeps = []

        existing_ids = {s.get('id') for s in node.substeps if isinstance(s, dict)}

        substep_id = requested_id
        if not substep_id:
            n = 1
            while f"substep-{n}" in existing_ids:
                n += 1
            substep_id = f"substep-{n}"
        elif substep_id in existing_ids:
            return jsonify({'success': False, 'error': f"Substep id already exists: {substep_id}"}), 409

        new_substep = {
            'id': substep_id,
            'text': text,
            'completed': False,
        }
        node.substeps.append(new_substep)

        node.audit.append(AuditEntry(
            at=datetime.now().isoformat(),
            who='user',
            action='substep_added',
            details=f"{substep_id}: {text}",
        ))

        plan.updated_at = datetime.now().isoformat()
        save_plan(chatId, plan)

        logger.info("POST substep - Success")
        return jsonify({'success': True, 'node': node.model_dump(by_alias=True)})
    except Exception as e:
        return handle_error('add_plan_node_substep', e)

@assistant_bp.route('/api/plan/<chatId>/nodes/<nodeId>/substeps/<substepId>', methods=['DELETE'])
def delete_plan_node_substep(chatId, nodeId, substepId):
    try:
        logger.info(f"DELETE /api/plan/{chatId}/nodes/{nodeId}/substeps/{substepId} - Started")

        plan = load_plan(chatId)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        node = next((n for n in plan.nodes if n.id == nodeId), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404

        if not node.substeps:
            return jsonify({'success': False, 'error': 'No substeps on node'}), 404

        before = len(node.substeps)
        removed = [s for s in node.substeps if isinstance(s, dict) and s.get('id') == substepId]
        node.substeps = [s for s in node.substeps if not (isinstance(s, dict) and s.get('id') == substepId)]

        if len(node.substeps) == before:
            return jsonify({'success': False, 'error': 'Substep not found'}), 404

        removed_text = removed[0].get('text', '') if removed else ''
        node.audit.append(AuditEntry(
            at=datetime.now().isoformat(),
            who='user',
            action='substep_deleted',
            details=f"{substepId}: {removed_text}",
        ))

        plan.updated_at = datetime.now().isoformat()
        save_plan(chatId, plan)

        logger.info("DELETE substep - Success")
        return jsonify({'success': True, 'node': node.model_dump(by_alias=True)})
    except Exception as e:
        return handle_error('delete_plan_node_substep', e)

@assistant_bp.route('/api/assistant-chats/<chat_id>', methods=['DELETE'])
def delete_assistant_chat(chat_id):
    try:
        logger.info(f"DELETE /api/assistant-chats/{chat_id} - Started")
        root = get_project_root()
        
        chat_dir = root / ".zoro" / "generated" / "assistant" / chat_id
        
        if not chat_dir.exists():
            logger.info(f"DELETE /api/assistant-chats/{chat_id} - Not Found")
            return jsonify({'success': False, 'error': 'Chat not found'}), 404
        
        shutil.rmtree(chat_dir)
        
        metadata = load_metadata()
        original_count = len(metadata.chats)
        metadata.chats = [c for c in metadata.chats if c.chat_id != chat_id]
        
        if len(metadata.chats) < original_count:
            save_metadata(metadata)
            logger.info(f"DELETE /api/assistant-chats/{chat_id} - Removed from metadata")
        
        logger.info(f"DELETE /api/assistant-chats/{chat_id} - Success")
        
        return jsonify({
            'success': True,
            'deleted': str(chat_dir),
            'chat_id': chat_id
        })
    except Exception as e:
        return handle_error('delete_assistant_chat', e)

@assistant_bp.route('/api/plan/<chatId>/nodes/<nodeId>', methods=['DELETE'])
def delete_plan_node(chatId, nodeId):
    try:
        logger.info(f"DELETE /api/plan/{chatId}/nodes/{nodeId} - Started")
        
        plan = load_plan(chatId)
        if not plan:
            logger.info(f"DELETE node - Plan not found: {chatId}")
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        node_to_delete = next((n for n in plan.nodes if n.id == nodeId), None)
        if not node_to_delete:
            logger.info(f"DELETE node - Node not found: {nodeId}")
            return jsonify({'success': False, 'error': 'Node not found'}), 404
        
        predecessors = [e.from_node for e in plan.edges if e.to_node == nodeId]
        successors = [e.to_node for e in plan.edges if e.from_node == nodeId]
        
        plan.nodes = [n for n in plan.nodes if n.id != nodeId]
        
        plan.edges = [e for e in plan.edges if e.from_node != nodeId and e.to_node != nodeId]
        
        for pred in predecessors:
            for succ in successors:
                new_edge = PlanEdge(
                    id=f"edge-{str(uuid.uuid4())[:8]}",
                    from_node=pred,
                    to_node=succ,
                    type="sequence"
                )
                plan.edges.append(new_edge)
        
        plan.updated_at = datetime.now().isoformat()
        
        save_plan(chatId, plan)
        
        logger.info(f"DELETE node - Success (mended {len(predecessors)} → {len(successors)} edges)")
        return jsonify({
            'success': True,
            'node_id': nodeId,
            'edges_removed': len(predecessors) + len(successors),
            'edges_added': len(predecessors) * len(successors)
        })
    except Exception as e:
        return handle_error('delete_plan_node', e)

@assistant_bp.route('/api/plan/<chatId>/nodes/<nodeId>/rules/<ruleId>', methods=['DELETE'])
def delete_plan_node_rule(chatId, nodeId, ruleId):
    try:
        logger.info(f"DELETE /api/plan/{chatId}/nodes/{nodeId}/rules/{ruleId} - Started")

        plan = load_plan(chatId)
        if not plan:
            logger.info(f"DELETE plan rule - Plan not found: {chatId}")
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        node = next((n for n in plan.nodes if n.id == nodeId), None)
        if not node:
            logger.info(f"DELETE plan rule - Node not found: {nodeId}")
            return jsonify({'success': False, 'error': 'Node not found'}), 404

        original_count = len(node.rules or [])
        node.rules = [r for r in (node.rules or []) if r.rule_id != ruleId]

        if len(node.rules) == original_count:
            logger.info(f"DELETE plan rule - Rule not found on node: {ruleId}")
            return jsonify({'success': False, 'error': 'Rule not found'}), 404

        plan.updated_at = datetime.now().isoformat()
        save_plan(chatId, plan)

        logger.info("DELETE plan rule - Success")
        return jsonify({'success': True, 'node_id': nodeId, 'rule_id': ruleId})
    except Exception as e:
        return handle_error('delete_plan_node_rule', e)

@assistant_bp.route('/api/plan/<chatId>/nodes/<nodeId>/rules', methods=['POST'])
def add_plan_node_rule(chatId, nodeId):
    try:
        logger.info(f"POST /api/plan/{chatId}/nodes/{nodeId}/rules - Started")

        plan = load_plan(chatId)
        if not plan:
            logger.info(f"POST plan rule - Plan not found: {chatId}")
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        node = next((n for n in plan.nodes if n.id == nodeId), None)
        if not node:
            logger.info(f"POST plan rule - Node not found: {nodeId}")
            return jsonify({'success': False, 'error': 'Node not found'}), 404

        data = request.json or {}
        rule_id = (data.get('rule_id') or '').strip() or str(uuid.uuid4())
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        source = (data.get('source') or '').strip()

        if not name:
            return jsonify({'success': False, 'error': 'Missing name'}), 400
        if not description:
            return jsonify({'success': False, 'error': 'Missing description'}), 400
        if not source:
            return jsonify({'success': False, 'error': 'Missing source'}), 400

        existing_ids = {r.rule_id for r in (node.rules or [])}
        if rule_id in existing_ids:
            return jsonify({'success': False, 'error': f"Rule id already exists on node: {rule_id}"}), 409

        node.rules.append(RuleRef(
            rule_id=rule_id,
            name=name,
            description=description,
            source=source,
        ))

        node.audit.append(AuditEntry(
            at=datetime.now().isoformat(),
            who='user',
            action='rule_added',
            details=f"{rule_id}: {name}",
        ))

        plan.updated_at = datetime.now().isoformat()
        save_plan(chatId, plan)

        logger.info("POST plan rule - Success")
        return jsonify({'success': True, 'node': node.model_dump(by_alias=True)})
    except Exception as e:
        return handle_error('add_plan_node_rule', e)

@assistant_bp.route('/api/chat-recommendations', methods=['GET'])
def get_chat_recommendations_route():
    try:
        logger.info("GET /api/chat-recommendations - Started")

        limit = request.args.get('limit', 100, type=int)
        path = request.args.get('path', default=None, type=str)
        chat_id = request.args.get('chat_id', default=None, type=str)
        debug_prompt = request.args.get('debug_prompt', default=0, type=int)

        if not chat_id:
            logger.info("GET /api/chat-recommendations - No chat selected (returning empty)")
            return jsonify({'success': True, 'recommendations': [], 'source': None})

        result = get_chat_recommendations(
            chat_id=chat_id,
            path=path,
            limit_messages=limit,
            debug_prompt=bool(debug_prompt),
        )

        if not result.get('success', False):
            logger.info("GET /api/chat-recommendations - Failed")
            return jsonify({'success': False, 'error': result.get('error', 'provider_error')}), 500

        logger.info("GET /api/chat-recommendations - Success")
        return jsonify(result)
    except Exception as e:
        return handle_error('get_chat_recommendations', e)

@assistant_bp.route('/api/assistant/plan/audit', methods=['POST'])
def assistant_plan_audit():
    try:
        logger.info("POST /api/assistant/plan/audit - Started")

        data = request.json or {}
        chat_id = (data.get("chat_id") or "").strip()
        node_id = (data.get("node_id") or "").strip()
        action = (data.get("action") or "").strip()
        details = (data.get("details") or "").strip()
        who = (data.get("who") or "user").strip() or "user"

        if not chat_id:
            return jsonify({'success': False, 'error': 'Missing chat_id'}), 400
        if not node_id:
            return jsonify({'success': False, 'error': 'Missing node_id'}), 400
        if not action:
            return jsonify({'success': False, 'error': 'Missing action'}), 400

        plan = load_plan(chat_id)
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404

        node = next((n for n in plan.nodes if n.id == node_id), None)
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'}), 404

        node.audit.append(AuditEntry(
            at=datetime.now().isoformat(),
            who=who,
            action=action,
            details=details,
        ))

        plan.updated_at = datetime.now().isoformat()
        save_plan(chat_id, plan)

        logger.info("POST /api/assistant/plan/audit - Success")
        return jsonify({'success': True, 'node': node.model_dump(by_alias=True)})
    except Exception as e:
        return handle_error('assistant_plan_audit', e)

@assistant_bp.route('/api/tags', methods=['GET'])
def get_tags():
    try:
        logger.info("GET /api/tags - Started")
        registry = TagRegistry('assistant_tags.json')
        tag_counts = registry.list_all_tags()
        tag_names = sorted(list(tag_counts.keys()))
        logger.info(f"GET /api/tags - Success ({len(tag_names)} tags)")
        return jsonify({'success': True, 'tags': tag_names})
    except Exception as e:
        return handle_error('get_tags', e)

@assistant_bp.route('/api/chats/<chat_name>/tags', methods=['GET'])
def get_chat_tags(chat_name):
    try:
        logger.info(f"GET /api/chats/{chat_name}/tags - Started")
        registry = TagRegistry('assistant_tags.json')
        tags = registry.get_tags(chat_name)
        logger.info(f"GET /api/chats/{chat_name}/tags - Success ({len(tags)} tags)")
        return jsonify({'success': True, 'tags': tags})
    except Exception as e:
        return handle_error('get_chat_tags', e)

@assistant_bp.route('/api/tags/assign', methods=['POST'])
def assign_tags():
    try:
        logger.info("POST /api/tags/assign - Started")
        data = request.json or {}
        chat_name = (data.get('chat_name') or '').strip()
        tags = data.get('tags', [])
        
        if not chat_name:
            return jsonify({'success': False, 'error': 'Missing chat_name'}), 400
        if not tags:
            return jsonify({'success': False, 'error': 'Missing tags'}), 400
        
        registry = TagRegistry('assistant_tags.json')
        registry.add_tags(chat_name, tags)
        
        updated_tags = registry.get_tags(chat_name)
        logger.info(f"POST /api/tags/assign - Success ({len(tags)} tags assigned to {chat_name})")
        return jsonify({'success': True, 'chat_name': chat_name, 'tags': updated_tags})
    except Exception as e:
        return handle_error('assign_tags', e)

@assistant_bp.route('/api/tags/remove', methods=['DELETE'])
def remove_tags():
    try:
        logger.info("DELETE /api/tags/remove - Started")
        data = request.json or {}
        chat_name = (data.get('chat_name') or '').strip()
        tags = data.get('tags', [])
        
        if not chat_name:
            return jsonify({'success': False, 'error': 'Missing chat_name'}), 400
        if not tags:
            return jsonify({'success': False, 'error': 'Missing tags'}), 400
        
        registry = TagRegistry('assistant_tags.json')
        registry.remove_tags(chat_name, tags)
        
        updated_tags = registry.get_tags(chat_name)
        logger.info(f"DELETE /api/tags/remove - Success ({len(tags)} tags removed from {chat_name})")
        return jsonify({'success': True, 'chat_name': chat_name, 'tags': updated_tags})
    except Exception as e:
        return handle_error('remove_tags', e)

@assistant_bp.route('/api/favorites', methods=['GET'])
def get_favorites():
    try:
        logger.info("GET /api/favorites - Started")
        root = get_project_root()
        favorites_path = root / ".zoro" / "generated" / "favorites.json"
        
        if not favorites_path.exists():
            logger.info("GET /api/favorites - No file, returning empty")
            return jsonify({'success': True, 'favorites': []})
        
        with open(favorites_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        db = FavoritesDB(**data)
        logger.info(f"GET /api/favorites - Success ({len(db.favorites)} favorites)")
        return jsonify({'success': True, 'favorites': [r.model_dump() for r in db.favorites]})
    except Exception as e:
        return handle_error('get_favorites', e)

@assistant_bp.route('/api/favorites', methods=['POST'])
def add_favorite():
    try:
        logger.info("POST /api/favorites - Started")
        data = request.json or {}
        rule_id = (data.get('rule_id') or '').strip()
        
        if not rule_id:
            return jsonify({'success': False, 'error': 'Missing rule_id'}), 400
        
        root = get_project_root()
        favorites_path = root / ".zoro" / "generated" / "favorites.json"
        favorites_path.parent.mkdir(parents=True, exist_ok=True)
        
        if favorites_path.exists():
            with open(favorites_path, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
            db = FavoritesDB(**db_data)
        else:
            db = FavoritesDB()
        
        if rule_id in {r.rule_id for r in db.favorites}:
            return jsonify({'success': False, 'error': 'Rule already in favorites'}), 409
        
        # Try to find in analyzed tasks first (learner module)
        all_tasks = load_all_analyzed_tasks()
        rule = None
        for task in all_tasks:
            rule = next((r for r in task.rules if r.rule_id == rule_id), None)
            if rule:
                break
        
        # If not found in analyzed tasks, try Knowledge Base
        if not rule:
            kb_path = root / ".zoro" / "rules" / "structured" / "knowledge_base.json"
            if kb_path.exists():
                try:
                    with open(kb_path, 'r', encoding='utf-8') as f:
                        kb_data = json.load(f)
                    items = kb_data.get('items', [])
                    for item in items:
                        if item.get('item_id') == rule_id:
                            # Convert KB item to RuleV2 format
                            rule = RuleV2(
                                rule_id=rule_id,
                                rule=item.get('content', ''),
                                reasoning=item.get('context', ''),
                                confidence=item.get('confidence', 0.5) * 10,  # KB uses 0-1, RuleV2 uses 0-10
                                decay=item.get('decay', 0.5) * 10,
                                from_task_id=item.get('category', 'knowledge-base')
                            )
                            break
                except Exception as e:
                    logger.warning(f"Error reading knowledge_base.json: {e}")
        
        if not rule:
            return jsonify({'success': False, 'error': 'Rule not found in learner tasks or knowledge base'}), 404
        
        db.favorites.append(rule)
        
        with open(favorites_path, 'w', encoding='utf-8') as f:
            json.dump(db.model_dump(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"POST /api/favorites - Success (rule_id: {rule_id})")
        return jsonify({'success': True, 'rule': rule.model_dump()})
    except Exception as e:
        return handle_error('add_favorite', e)

@assistant_bp.route('/api/favorites/<rule_id>', methods=['DELETE'])
def remove_favorite(rule_id):
    try:
        logger.info(f"DELETE /api/favorites/{rule_id} - Started")
        root = get_project_root()
        favorites_path = root / ".zoro" / "generated" / "favorites.json"
        
        if not favorites_path.exists():
            return jsonify({'success': False, 'error': 'No favorites found'}), 404
        
        with open(favorites_path, 'r', encoding='utf-8') as f:
            db_data = json.load(f)
        db = FavoritesDB(**db_data)
        
        original_count = len(db.favorites)
        db.favorites = [r for r in db.favorites if r.rule_id != rule_id]
        
        if len(db.favorites) == original_count:
            return jsonify({'success': False, 'error': 'Rule not in favorites'}), 404
        
        with open(favorites_path, 'w', encoding='utf-8') as f:
            json.dump(db.model_dump(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"DELETE /api/favorites/{rule_id} - Success")
        return jsonify({'success': True, 'rule_id': rule_id})
    except Exception as e:
        return handle_error('remove_favorite', e)

@assistant_bp.route('/api/favorites/manual', methods=['POST'])
def add_manual_favorite():
    try:
        logger.info("POST /api/favorites/manual - Started")
        data = request.json or {}
        
        rule_text = (data.get('rule') or '').strip()
        reasoning = (data.get('reasoning') or '').strip()
        confidence = data.get('confidence', 5)
        decay = data.get('decay', 5)
        
        if not rule_text:
            return jsonify({'success': False, 'error': 'Missing rule text'}), 400
        if not reasoning:
            return jsonify({'success': False, 'error': 'Missing reasoning'}), 400
        
        root = get_project_root()
        favorites_path = root / ".zoro" / "generated" / "favorites.json"
        favorites_path.parent.mkdir(parents=True, exist_ok=True)
        
        if favorites_path.exists():
            with open(favorites_path, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
            db = FavoritesDB(**db_data)
        else:
            db = FavoritesDB()
        
        new_rule = RuleV2(
            rule_id=str(uuid.uuid4()),
            rule=rule_text,
            reasoning=reasoning,
            confidence=confidence,
            decay=decay,
            from_task_id=None
        )
        
        db.favorites.append(new_rule)
        
        with open(favorites_path, 'w', encoding='utf-8') as f:
            json.dump(db.model_dump(), f, indent=2, ensure_ascii=False)
        
        logger.info("POST /api/favorites/manual - Success")
        return jsonify({'success': True, 'rule': new_rule.model_dump()})
    except Exception as e:
        return handle_error('add_manual_favorite', e)