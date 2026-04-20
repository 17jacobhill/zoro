from flask import Blueprint, request, jsonify
import json
import logging
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from backend.globals.models import get_default_provider
from backend.globals.schemas import get_schema
from backend.knowledge.schemas import KnowledgeItem, KnowledgeBase, ProcessingLog
from backend.knowledge.prompts.parse_unstructured import PARSE_UNSTRUCTURED_PROMPT
from backend.knowledge.prompts.category_suggestions import CATEGORY_MERGE_PROMPT
from backend.knowledge.prompts.duplicate_detection import BATCH_DUPLICATE_DETECTION_PROMPT
from backend.knowledge.prompts.refine_manual_rule import REFINE_MANUAL_RULE_PROMPT
from backend.utils import get_project_root

knowledge_bp = Blueprint('knowledge', __name__)
logger = logging.getLogger(__name__)


def load_knowledge_base() -> dict:
    root = get_project_root()
    kb_path = root / ".zoro" / "rules" / "structured" / "knowledge_base.json"
    
    if not kb_path.exists():
        return {'items': [], 'categories': []}
    
    with open(kb_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_knowledge_base(kb: dict):
    root = get_project_root()
    kb_path = root / ".zoro" / "rules" / "structured" / "knowledge_base.json"
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)


def load_processing_log() -> dict:
    root = get_project_root()
    log_path = root / ".zoro" / "rules" / "structured" / "processing_log.json"
    
    if not log_path.exists():
        return {'files': {}}
    
    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_processing_log(log: dict):
    root = get_project_root()
    log_path = root / ".zoro" / "rules" / "structured" / "processing_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def parse_markdown_sections(content: str) -> list:
    sections = []
    current_section = None
    
    for line in content.split('\n'):
        if line.startswith('## Category:'):
            if current_section:
                sections.append(current_section)
            current_section = {
                'category': line.replace('## Category:', '').strip(),
                'content': []
            }
        elif current_section:
            current_section['content'].append(line)
    
    if current_section:
        sections.append(current_section)
    
    return sections


def format_sections_for_llm(sections: list) -> str:
    formatted = []
    for sec in sections:
        formatted.append(f"## Category: {sec['category']}")
        formatted.append('\n'.join(sec['content']))
        formatted.append('\n---\n')
    return '\n'.join(formatted)


def extract_unique_categories(kb: dict) -> dict:
    categories = {}
    for item in kb['items']:
        cat = item['category']
        categories[cat] = categories.get(cat, 0) + 1
    return categories


@knowledge_bp.route('/api/kb/files/unstructured/count', methods=['GET'])
def count_unstructured_files():
    try:
        root = get_project_root()
        unstructured_dir = root / ".zoro" / "rules" / "unstructured"
        
        if not unstructured_dir.exists():
            return jsonify({'success': True, 'files': [], 'total_pending': 0})
        
        processing_log = load_processing_log()
        files_info = []
        
        for file_path in unstructured_dir.glob("*.md"):
            if "processed" in str(file_path):
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = parse_markdown_sections(content)
            total_items = len(sections)
            
            file_name = file_path.name
            log_entry = processing_log['files'].get(file_name, {})
            processed_count = log_entry.get('items_processed', 0)
            pending_count = max(0, total_items - processed_count)
            
            files_info.append({
                'filename': file_name,
                'total_items': total_items,
                'processed': processed_count,
                'pending': pending_count,
                'path': str(file_path.relative_to(root))
            })
        
        total_pending = sum(f['pending'] for f in files_info)
        
        return jsonify({
            'success': True,
            'files': files_info,
            'total_pending': total_pending
        })
    
    except Exception as e:
        logger.error(f"Error counting unstructured files: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/process', methods=['POST'])
def process_unstructured():
    try:
        data = request.json
        filenames = data.get('files', [])
        
        if not filenames:
            return jsonify({'success': False, 'error': 'No files specified'}), 400
        
        root = get_project_root()
        unstructured_dir = root / ".zoro" / "rules" / "unstructured"
        
        results = []
        
        for filename in filenames:
            file_path = unstructured_dir / filename
            
            if not file_path.exists():
                results.append({
                    'filename': filename,
                    'success': False,
                    'error': 'File not found'
                })
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = parse_markdown_sections(content)
            
            processing_log = load_processing_log()
            log_entry = processing_log['files'].get(filename, {})
            processed_count = log_entry.get('items_processed', 0)
            
            new_sections = sections[processed_count:]
            pre_count = len(new_sections)
            
            if pre_count == 0:
                results.append({
                    'filename': filename,
                    'success': True,
                    'items_added': 0,
                    'message': 'No new items to process'
                })
                continue
            
            sections_text = format_sections_for_llm(new_sections)
            
            provider = get_default_provider()
            prompt = PARSE_UNSTRUCTURED_PROMPT.format(
                content=sections_text,
                expected_count=pre_count
            )
            
            response = provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-5",
                response_format=get_schema({
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["rule", "doc"]},
                                    "category": {"type": "string"},
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                    "context": {"type": ["string", "null"]},
                                    "evidence": {"type": ["string", "null"]},
                                    "confidence": {"type": ["number", "null"]},
                                    "decay": {"type": ["number", "null"]},
                                    "confidence_reasoning": {"type": ["string", "null"]},
                                    "decay_reasoning": {"type": ["string", "null"]}
                                },
                                "required": ["type", "category", "title", "content"]
                            }
                        }
                    },
                    "required": ["items"]
                })
            )
            
            if not response:
                logger.error(f"Empty response from LLM for file {filename}")
                return jsonify({
                    'success': False,
                    'error': f'LLM returned empty response for {filename}'
                }), 500
            
            logger.info(f"LLM response for {filename}: length={len(response)}, preview={response[:200]}")
            
            try:
                parsed = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response for {filename}: {e}")
                logger.error(f"Response content (first 500 chars): {response[:500]}")
                return jsonify({
                    'success': False,
                    'error': f'Invalid JSON from LLM: {str(e)}'
                }), 500
            items = parsed['items']
            post_count = len(items)
            
            if post_count != pre_count:
                return jsonify({
                    'success': False,
                    'error': f'Count mismatch for {filename}: expected {pre_count}, got {post_count}'
                }), 500
            
            timestamp = datetime.now().isoformat()
            newly_added_ids = []
            for item in items:
                item['item_id'] = str(uuid.uuid4())
                item['source_file'] = filename
                item['usage_count'] = 0
                item['is_favorite'] = False
                item['is_strict'] = item.get('is_strict', False)
                item['created_at'] = timestamp
                
                # Ensure confidence and decay have defaults (never null)
                if item.get('confidence') is None:
                    item['confidence'] = 0.5
                if item.get('decay') is None:
                    item['decay'] = 0.5
                
                newly_added_ids.append(item['item_id'])
            
            kb = load_knowledge_base()
            kb['items'].extend(items)
            save_knowledge_base(kb)
            
            timestamp_str = datetime.now().strftime("%Y-%m-%d")
            processed_dir = unstructured_dir / "processed"
            processed_dir.mkdir(exist_ok=True)
            
            processed_filename = f"{file_path.stem}_{timestamp_str}.md"
            processed_path = processed_dir / processed_filename
            shutil.copy(file_path, processed_path)
            
            processing_log['files'][filename] = {
                'last_processed': timestamp,
                'items_processed': len(sections),
                'runs': log_entry.get('runs', []) + [{
                    'timestamp': timestamp,
                    'items_added': post_count
                }]
            }
            save_processing_log(processing_log)
            
            results.append({
                'filename': filename,
                'success': True,
                'items_added': post_count,
                'newly_added_ids': newly_added_ids,
                'pre_count': pre_count,
                'post_count': post_count,
                'processed_path': str(processed_path.relative_to(root))
            })
        
        all_newly_added_ids = []
        for result in results:
            if result.get('success') and 'newly_added_ids' in result:
                all_newly_added_ids.extend(result['newly_added_ids'])
        
        return jsonify({
            'success': True,
            'results': results,
            'total_added': sum(r.get('items_added', 0) for r in results),
            'newly_added_ids': all_newly_added_ids
        })
    
    except Exception as e:
        logger.error(f"Error processing files: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/categories/suggest-merges', methods=['GET'])
def suggest_category_merges():
    try:
        kb = load_knowledge_base()
        categories = extract_unique_categories(kb)
        
        if len(categories) < 2:
            return jsonify({'success': True, 'suggestions': []})
        
        # Build detailed category overview with sample rules (up to 10 each)
        category_details = []
        for cat_name, count in sorted(categories.items(), key=lambda x: -x[1]):
            items_in_cat = [i for i in kb['items'] if i['category'] == cat_name]
            samples = items_in_cat[:10]  # Get up to 10 samples
            
            category_details.append(f"\n## {cat_name} ({count} items)")
            for item in samples:
                category_details.append(f"  - [{item['type']}] {item['title']}")
                # Truncate content to ~150 chars for readability
                content_preview = item['content'][:150] + "..." if len(item['content']) > 150 else item['content']
                category_details.append(f"    Content: {content_preview}")
        
        provider = get_default_provider()
        prompt = CATEGORY_MERGE_PROMPT.format(
            category_details='\n'.join(category_details)
        )
        
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5",
            response_format=get_schema({
                "type": "object",
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "merge_from": {"type": "array", "items": {"type": "string"}},
                                "merge_to": {"type": "string"},
                                "reasoning": {"type": "string"}
                            },
                            "required": ["merge_from", "merge_to", "reasoning"]
                        }
                    }
                },
                "required": ["suggestions"]
            })
        )
        
        parsed = json.loads(response)
        suggestions = []
        
        for sug in parsed['suggestions']:
            suggestions.append({
                'suggestion_id': str(uuid.uuid4()),
                'merge_from': sug['merge_from'],
                'merge_to': sug['merge_to'],
                'reasoning': sug['reasoning'],
                'dismissed': False
            })
        
        return jsonify({'success': True, 'suggestions': suggestions})
    
    except Exception as e:
        logger.error(f"Error suggesting merges: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/categories/accept', methods=['POST'])
def accept_category_merge():
    try:
        data = request.json
        merge_from = data.get('merge_from', [])
        merge_to = data.get('merge_to', '')
        
        if not merge_from or not merge_to:
            return jsonify({'success': False, 'error': 'Missing merge parameters'}), 400
        
        kb = load_knowledge_base()
        
        updated_count = 0
        for item in kb['items']:
            if item['category'] in merge_from:
                item['category'] = merge_to
                updated_count += 1
        
        save_knowledge_base(kb)
        
        return jsonify({
            'success': True,
            'updated_items': updated_count,
            'merge_from': merge_from,
            'merge_to': merge_to
        })
    
    except Exception as e:
        logger.error(f"Error accepting merge: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/categories/dismiss', methods=['POST'])
def dismiss_category_merge():
    try:
        data = request.json
        suggestion_id = data.get('suggestion_id', '')
        
        return jsonify({'success': True, 'suggestion_id': suggestion_id})
    
    except Exception as e:
        logger.error(f"Error dismissing suggestion: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items', methods=['GET'])
def list_items():
    try:
        category = request.args.get('category')
        item_type = request.args.get('type')
        favorites_only = request.args.get('favorites') == 'true'
        search = request.args.get('search', '').lower()
        
        kb = load_knowledge_base()
        items = kb['items']
        
        if category:
            items = [i for i in items if i['category'] == category]
        
        if item_type:
            items = [i for i in items if i['type'] == item_type]
        
        if favorites_only:
            items = [i for i in items if i['is_favorite']]
        
        if search:
            items = [i for i in items if 
                    search in i['title'].lower() or 
                    search in i['content'].lower()]
        
        return jsonify({'success': True, 'items': items, 'count': len(items)})
    
    except Exception as e:
        logger.error(f"Error listing items: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items/refine', methods=['POST'])
def refine_manual_rule():
    try:
        data = request.json
        
        required_fields = ['rule_type', 'category', 'title', 'content']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        rule_type = data['rule_type']
        category = data['category']
        title = data['title']
        content = data['content']
        context = data.get('context') or ''
        evidence = data.get('evidence') or ''
        
        provider = get_default_provider()
        prompt = REFINE_MANUAL_RULE_PROMPT.format(
            rule_type=rule_type,
            category=category,
            title=title,
            content=content,
            context=context,
            evidence=evidence
        )
        
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-5",
            response_format=get_schema({
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "confidence": {"type": "number"},
                    "decay": {"type": "number"},
                    "confidence_reasoning": {"type": "string"},
                    "decay_reasoning": {"type": "string"},
                    "context": {"type": ["string", "null"]},
                    "evidence": {"type": ["string", "null"]}
                },
                "required": ["title", "content", "confidence", "decay", "confidence_reasoning", "decay_reasoning"]
            })
        )
        
        if not response:
            logger.error("Empty response from LLM for rule refinement")
            return jsonify({
                'success': False,
                'error': 'LLM returned empty response'
            }), 500
        
        try:
            # Strip markdown code fences if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            refined = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response content: {response[:500]}")
            return jsonify({
                'success': False,
                'error': f'Invalid JSON from LLM: {str(e)}'
            }), 500

        return jsonify({
            'success': True,
            'refined': refined
        })
    
    except Exception as e:
        logger.error(f"Error refining rule: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items', methods=['POST'])
def create_item():
    try:
        data = request.json
        
        required_fields = ['type', 'category', 'title', 'content']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        item = {
            'item_id': str(uuid.uuid4()),
            'type': data['type'],
            'category': data['category'],
            'title': data['title'],
            'content': data['content'],
            'context': data.get('context'),
            'evidence': data.get('evidence'),
            'confidence': data.get('confidence', 0.5),
            'decay': data.get('decay', 0.5),
            'confidence_reasoning': data.get('confidence_reasoning'),
            'decay_reasoning': data.get('decay_reasoning'),
            'source_file': 'manual',
            'usage_count': 0,
            'is_favorite': data.get('is_favorite', False),
            'is_strict': data.get('is_strict', False),
            'is_testable': data.get('is_testable', False),
            'created_at': datetime.now().isoformat()
        }
        
        kb = load_knowledge_base()
        kb['items'].append(item)
        save_knowledge_base(kb)
        
        return jsonify({'success': True, 'item': item})
    
    except Exception as e:
        logger.error(f"Error creating item: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items/<item_id>', methods=['PATCH'])
def update_item(item_id):
    try:
        data = request.json
        
        kb = load_knowledge_base()
        item = next((i for i in kb['items'] if i['item_id'] == item_id), None)
        
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        updatable_fields = [
            'title',
            'content',
            'category',
            'context',
            'evidence',
            'is_favorite',
            'is_strict',
            'is_testable',
            'confidence',
            'decay',
            'confidence_reasoning',
            'decay_reasoning',
        ]
        for field in updatable_fields:
            if field in data:
                item[field] = data[field]
        
        save_knowledge_base(kb)
        
        return jsonify({'success': True, 'item': item})
    
    except Exception as e:
        logger.error(f"Error updating item: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/favorites', methods=['GET'])
def get_favorites():
    try:
        kb = load_knowledge_base()
        favorites = [item for item in kb['items'] if item.get('is_favorite', False)]
        
        return jsonify({'success': True, 'favorites': favorites})
    
    except Exception as e:
        logger.error(f"Error getting favorites: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items/<item_id>/favorite', methods=['POST'])
def toggle_favorite(item_id):
    try:
        data = request.json or {}
        is_favorite = data.get('is_favorite', True)
        
        kb = load_knowledge_base()
        item = next((i for i in kb['items'] if i['item_id'] == item_id), None)
        
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        item['is_favorite'] = is_favorite
        save_knowledge_base(kb)
        
        return jsonify({'success': True, 'item': item})
    
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    try:
        kb = load_knowledge_base()
        original_count = len(kb['items'])
        
        kb['items'] = [i for i in kb['items'] if i['item_id'] != item_id]
        
        if len(kb['items']) == original_count:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        save_knowledge_base(kb)
        
        return jsonify({'success': True, 'item_id': item_id})
    
    except Exception as e:
        logger.error(f"Error deleting item: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/categories', methods=['GET'])
def list_categories():
    try:
        kb = load_knowledge_base()
        categories = extract_unique_categories(kb)
        
        category_list = [
            {
                'name': name,
                'item_count': count
            }
            for name, count in sorted(categories.items())
        ]
        
        return jsonify({'success': True, 'categories': category_list})
    
    except Exception as e:
        logger.error(f"Error listing categories: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/duplicates/detect', methods=['POST'])
def detect_duplicates():
    try:
        data = request.json or {}
        requested_categories = data.get('categories', None)
        
        kb = load_knowledge_base()
        
        if requested_categories:
            categories_to_check = requested_categories
        else:
            all_categories = extract_unique_categories(kb)
            categories_to_check = list(all_categories.keys())
        
        category_items = {}
        for item in kb['items']:
            cat = item['category']
            if cat in categories_to_check:
                if cat not in category_items:
                    category_items[cat] = []
                category_items[cat].append(item)
        
        all_duplicates = []
        provider = get_default_provider()
        
        for cat_name, items in category_items.items():
            if len(items) < 2:
                continue
            
            items_list = []
            for idx, item in enumerate(items, 1):
                items_list.append(f"\n--- Item {idx} (ID: {item['item_id']}) ---")
                items_list.append(f"Title: {item['title']}")
                items_list.append(f"Type: {item['type']}")
                items_list.append(f"Content: {item['content']}")
                if item.get('context'):
                    items_list.append(f"Context: {item['context']}")
                if item.get('evidence'):
                    items_list.append(f"Evidence: {item['evidence']}")
                if item.get('confidence') is not None:
                    items_list.append(f"Confidence: {item['confidence']}")
                if item.get('decay') is not None:
                    items_list.append(f"Decay: {item['decay']}")
            
            prompt = BATCH_DUPLICATE_DETECTION_PROMPT.format(
                category=cat_name,
                items_list='\n'.join(items_list)
            )
            
            response = provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-5",
                response_format=get_schema({
                    "type": "object",
                    "properties": {
                        "groups": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_ids": {"type": "array", "items": {"type": "string"}},
                                    "similarity_score": {"type": "number"},
                                    "is_conflict": {"type": "boolean"},
                                    "reasoning": {"type": "string"},
                                    "merged_title": {"type": "string"},
                                    "merged_content": {"type": "string"},
                                    "merged_context": {"type": ["string", "null"]},
                                    "merged_evidence": {"type": ["string", "null"]},
                                    "merged_confidence": {"type": ["number", "null"]},
                                    "merged_decay": {"type": ["number", "null"]},
                                    "scoring_explanation": {"type": ["string", "null"]}
                                },
                                "required": ["item_ids", "similarity_score", "reasoning", "merged_title", "merged_content"]
                            }
                        }
                    },
                    "required": ["groups"]
                })
            )
            
            if not response:
                logger.warning(f"Empty response for category {cat_name}")
                continue
            
            try:
                result = json.loads(response)
                groups = result.get('groups', [])
                
                for group in groups:
                    group_item_ids = group['item_ids']
                    group_items = [i for i in items if i['item_id'] in group_item_ids]
                    
                    if len(group_items) < 2:
                        continue
                    
                    all_duplicates.append({
                        'category': cat_name,
                        'suggestion_id': str(uuid.uuid4()),
                        'item_ids': [i['item_id'] for i in group_items],
                        'items': group_items,
                        'similarity_score': group['similarity_score'],
                        'is_conflict': group.get('is_conflict', False),
                        'reasoning': group['reasoning'],
                        'suggested_merged': group['merged_content'],
                        'merged_title': group['merged_title'],
                        'merged_context': group.get('merged_context'),
                        'merged_evidence': group.get('merged_evidence'),
                        'merged_confidence': group.get('merged_confidence'),
                        'merged_decay': group.get('merged_decay'),
                        'scoring_explanation': group.get('scoring_explanation'),
                        'dismissed': False
                    })
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response for category {cat_name}: {e}")
                continue
        
        grouped = {}
        for dup in all_duplicates:
            cat = dup['category']
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(dup)
        
        return jsonify({
            'success': True,
            'duplicates': all_duplicates,
            'grouped_by_category': grouped,
            'categories_checked': categories_to_check
        })
    
    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/kb/duplicates/merge', methods=['POST'])
def merge_duplicates():
    try:
        data = request.json
        item_ids = data.get('item_ids', [])
        is_conflict = data.get('is_conflict', False)
        
        if len(item_ids) < 2:
            return jsonify({'success': False, 'error': 'Invalid merge parameters'}), 400
        
        kb = load_knowledge_base()
        items_to_update = [i for i in kb['items'] if i['item_id'] in item_ids]
        
        if len(items_to_update) != len(item_ids):
            missing_count = len(item_ids) - len(items_to_update)
            return jsonify({
                'success': False, 
                'error': f'{missing_count} item(s) were already merged or deleted',
                'code': 'ALREADY_MERGED'
            }), 409
        
        # CONFLICT: Update both rules, don't merge
        if is_conflict:
            for item in items_to_update:
                old_decay = item.get('decay', 0.5)
                new_decay = min(1.0, old_decay + 0.2)
                item['decay'] = new_decay
                item['decay_reasoning'] = f"Increased from {old_decay:.2f} to {new_decay:.2f} due to conflict with another rule"
            
            save_knowledge_base(kb)
            
            return jsonify({
                'success': True,
                'updated_ids': item_ids,
                'action': 'conflict_marked'
            })
        
        # DUPLICATE: Normal merge logic
        merged_content = data.get('merged_content', '')
        merged_title = data.get('merged_title', '')
        
        if not merged_content:
            return jsonify({'success': False, 'error': 'Merged content required'}), 400
        
        # Use merged scores if provided, otherwise calculate default
        merged_confidence = data.get('merged_confidence')
        merged_decay = data.get('merged_decay')
        scoring_explanation = data.get('scoring_explanation', '')
        
        if merged_confidence is None or merged_decay is None:
            # Calculate default scores if not provided
            confidences = [i.get('confidence', 0.5) for i in items_to_update]
            decays = [i.get('decay', 0.5) for i in items_to_update]
            merged_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            merged_decay = sum(decays) / len(decays) if decays else 0.5
        
        merged_item = {
            'item_id': str(uuid.uuid4()),
            'type': items_to_update[0]['type'],
            'category': items_to_update[0]['category'],
            'title': merged_title or items_to_update[0]['title'],
            'content': merged_content,
            'context': items_to_update[0].get('context'),
            'evidence': '\n\n'.join(filter(None, [i.get('evidence', '') for i in items_to_update])),
            'confidence': merged_confidence,
            'decay': merged_decay,
            'confidence_reasoning': scoring_explanation if scoring_explanation else 'Merged from multiple rules',
            'decay_reasoning': scoring_explanation if scoring_explanation else 'Merged from multiple rules',
            'source_file': ', '.join(set(i['source_file'] for i in items_to_update)),
            'usage_count': sum(i['usage_count'] for i in items_to_update),
            'is_favorite': any(i['is_favorite'] for i in items_to_update),
            'is_strict': any(i.get('is_strict', False) for i in items_to_update),
            'created_at': datetime.now().isoformat()
        }
        
        kb['items'] = [i for i in kb['items'] if i['item_id'] not in item_ids]
        kb['items'].append(merged_item)
        
        save_knowledge_base(kb)
        
        return jsonify({
            'success': True,
            'merged_item': merged_item,
            'removed_ids': item_ids,
            'action': 'merged'
        })
    
    except Exception as e:
        logger.error(f"Error merging items: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
