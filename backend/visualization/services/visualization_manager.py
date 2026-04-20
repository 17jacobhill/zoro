import json
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import tiktoken

from backend.plan_paths import get_plan_markdown_path
from backend.utils import get_project_root, get_rule_retrieval_source_from_config, get_chat_history_source_from_config
from backend.visualization.services.rule_learning_agent import (
    find_latest_chat_history_path,
    read_new_chat_content,
    _parse_codex_jsonl_messages
)
from backend.learner.chat_parser import ChatParser
from backend.visualization.services.plan_tracker import (
    plan_to_markdown,
    get_chat_id_from_plan_md
)

VIS_DIR = get_project_root() / ".zoro" / "generated" / "visualization"
INDEX_FILE = VIS_DIR / "index.json"

TOKEN_THRESHOLD = 150000

def _ensure_vis_dir():
    VIS_DIR.mkdir(parents=True, exist_ok=True)

def _load_index() -> Dict[str, str]:
    if not INDEX_FILE.exists():
        return {"path_to_chat_id": {}}
    with open(INDEX_FILE, 'r') as f:
        return json.load(f)

def _save_index(index: Dict[str, str]):
    _ensure_vis_dir()
    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2)

def _get_metadata_path(chat_id: str) -> Path:
    return VIS_DIR / chat_id / "metadata.json"

def _load_metadata(chat_id: str) -> Optional[Dict]:
    path = _get_metadata_path(chat_id)
    if not path.exists():
        return None
    with open(path, 'r') as f:
        return json.load(f)

def _save_metadata(chat_id: str, metadata: Dict):
    path = _get_metadata_path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(metadata, f, indent=2)

def _count_tokens(text: str) -> int:
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())

def list_visualizations() -> List[Dict]:
    _ensure_vis_dir()
    visualizations = []
    
    for chat_dir in VIS_DIR.iterdir():
        if chat_dir.is_dir() and chat_dir.name != "index.json":
            metadata = _load_metadata(chat_dir.name)
            if metadata:
                visualizations.append(metadata)
    
    return visualizations

def get_visualization(chat_id: str) -> Optional[Dict]:
    return _load_metadata(chat_id)

def create_visualization(rule_retrieval_source: str = None) -> Tuple[Optional[Dict], Optional[str]]:
    if rule_retrieval_source is None:
        rule_retrieval_source = get_rule_retrieval_source_from_config()
    
    latest_path = find_latest_chat_history_path()
    
    if not latest_path:
        source = get_chat_history_source_from_config()
        return None, f"No {source} chat history found"
    
    latest_path_str = str(latest_path)
    
    index = _load_index()
    path_map = index.get("path_to_chat_id", {})
    
    if latest_path_str in path_map:
        existing_chat_id = path_map[latest_path_str]
        existing_metadata = _load_metadata(existing_chat_id)
        existing_name = existing_metadata.get('name', existing_chat_id) if existing_metadata else existing_chat_id
        return None, f"Chat already visualized as '{existing_name}'"
    
    if rule_retrieval_source not in ['structured', 'unstructured']:
        return None, f"Invalid rule_retrieval_source: must be 'structured' or 'unstructured'"
    
    chat_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    metadata = {
        "chat_id": chat_id,
        "name": None,
        "chat_file_path": latest_path_str,
        "chat_history_source": get_chat_history_source_from_config(),
        "status": "idle",
        "last_polled_at": None,
        "token_count": 0,
        "last_message_index": 0,
        "accumulated_content": "",
        "cleaned_accumulated_content": "",
        "supervision_cleaned_accumulated_content": "",
        "last_analyzed_token_index": 0,
        "last_supervised_token_index": 0,
        "total_clean_tokens": 0,
        "total_supervision_clean_tokens": 0,
        "plan_tracking": {},
        "rule_retrieval_source": rule_retrieval_source,
        "created_at": now,
        "updated_at": now
    }
    
    _save_metadata(chat_id, metadata)
    
    path_map[latest_path_str] = chat_id
    index["path_to_chat_id"] = path_map
    _save_index(index)
    
    return metadata, None

def delete_visualization(chat_id: str) -> Tuple[bool, Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return False, "Visualization not found"
    
    chat_file_path = metadata.get("chat_file_path")
    
    index = _load_index()
    path_map = index.get("path_to_chat_id", {})
    if chat_file_path and chat_file_path in path_map:
        del path_map[chat_file_path]
        index["path_to_chat_id"] = path_map
        _save_index(index)
    
    chat_dir = VIS_DIR / chat_id
    if chat_dir.exists():
        import shutil
        shutil.rmtree(chat_dir)
    
    return True, None

def update_visualization_name(chat_id: str, name: str) -> Tuple[Optional[Dict], Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return None, "Visualization not found"
    
    metadata["name"] = name
    metadata["updated_at"] = datetime.now().isoformat()
    _save_metadata(chat_id, metadata)
    
    return metadata, None

def start_visualization(chat_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return None, "Visualization not found"
    
    metadata["status"] = "polling"
    metadata["updated_at"] = datetime.now().isoformat()
    _save_metadata(chat_id, metadata)
    
    return metadata, None

def pause_visualization(chat_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return None, "Visualization not found"
    
    metadata["status"] = "paused"
    metadata["updated_at"] = datetime.now().isoformat()
    _save_metadata(chat_id, metadata)
    
    return metadata, None

def poll_visualization(chat_id: str) -> Tuple[Optional[str], str, Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return None, "idle", "Visualization not found"
    
    if metadata["status"] != "polling":
        return None, metadata["status"], None
    
    chat_file_path = metadata.get("chat_file_path")
    if not chat_file_path:
        return None, metadata["status"], "No chat file path"
    
    last_polled_at = metadata.get("last_polled_at")
    
    content, modified_at = read_new_chat_content(chat_file_path, last_polled_at)
    
    if content is None:
        return None, metadata["status"], None
    
    try:
        if chat_file_path.endswith(".jsonl"):
            messages = _parse_codex_jsonl_messages(content)
        else:
            data = json.loads(content)
            if isinstance(data, list):
                messages = data
            else:
                messages = data.get("messages", [])
        
        last_message_index = metadata.get("last_message_index", 0)
        new_messages = messages[last_message_index:]
        
        if not new_messages:
            metadata["last_polled_at"] = modified_at
            _save_metadata(chat_id, metadata)
            return None, metadata["status"], None
        
        new_content = "\n\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in new_messages
        ])
        
        parser = ChatParser()
        try:
            cleaned_messages = parser._clean_json_messages(new_messages)
            
            new_clean_text = "\n\n".join([
                f"{msg.get('role', 'unknown')}: {block.get('text', '') if block.get('type') == 'text' else block.get('thinking', '')}"
                for msg in cleaned_messages
                for block in msg.get('content', [])
                if block.get('type') in ['text', 'thinking']
            ])
            
            supervision_cleaned_messages = parser._create_supervision_cleaned_json(new_messages)
            
            new_supervision_clean_text = "\n\n".join([
                f"{msg.get('role', 'unknown')}: {block.get('text', '')}"
                for msg in supervision_cleaned_messages
                for block in msg.get('content', [])
                if block.get('type') == 'text'
            ])
        except Exception:
            new_clean_text = new_content
            new_supervision_clean_text = new_content
        
        new_tokens = _count_tokens(new_content)
        new_clean_tokens = _count_tokens(new_clean_text)
        
        accumulated = metadata.get("accumulated_content", "")
        if accumulated:
            accumulated += "\n\n" + new_content
        else:
            accumulated = new_content
        
        cleaned_accumulated = metadata.get("cleaned_accumulated_content", "")
        if cleaned_accumulated:
            cleaned_accumulated += "\n\n" + new_clean_text
        else:
            cleaned_accumulated = new_clean_text
        
        supervision_cleaned_accumulated = metadata.get("supervision_cleaned_accumulated_content", "")
        if supervision_cleaned_accumulated:
            supervision_cleaned_accumulated += "\n\n" + new_supervision_clean_text
        else:
            supervision_cleaned_accumulated = new_supervision_clean_text
        
        metadata["token_count"] += new_tokens
        metadata["total_clean_tokens"] = _count_tokens(cleaned_accumulated)
        metadata["total_supervision_clean_tokens"] = _count_tokens(supervision_cleaned_accumulated)
        metadata["last_message_index"] = len(messages)
        metadata["accumulated_content"] = accumulated
        metadata["cleaned_accumulated_content"] = cleaned_accumulated
        metadata["supervision_cleaned_accumulated_content"] = supervision_cleaned_accumulated
        metadata["last_polled_at"] = modified_at
        metadata["updated_at"] = datetime.now().isoformat()
        
        if metadata["token_count"] >= TOKEN_THRESHOLD:
            pass
        
        _save_metadata(chat_id, metadata)
        
        return new_content, metadata["status"], None
        
    except json.JSONDecodeError as e:
        return None, metadata["status"], f"Failed to parse chat content: {str(e)}"


def _find_item_in_tree(items: List[Dict], item_id: str, parent: Optional[Dict] = None, parent_index: int = -1) -> Tuple[Optional[Dict], Optional[Dict], int]:
    for idx, item in enumerate(items):
        if item.get('id') == item_id:
            return (item, parent, parent_index if parent else idx)
        if item.get('children'):
            result = _find_item_in_tree(item['children'], item_id, item, idx)
            if result[0]:
                return result
    return (None, None, -1)

def _renumber_items(items: List[Dict], parent_number: str = ""):
    for idx, item in enumerate(items, 1):
        if parent_number:
            item['number'] = f"{parent_number}.{idx}"
        else:
            item['number'] = str(idx)
        
        if item.get('children'):
            _renumber_items(item['children'], item['number'])

def _recalculate_inherited_rules(items: List[Dict], parent_rules: Optional[List[Tuple[Dict, str]]] = None):
    if parent_rules is None:
        parent_rules = []
    
    for item in items:
        inherited_rules = []
        for rule, source in parent_rules:
            clean_rule = rule.copy()
            inherited_rules.append({'rule': clean_rule, 'source': source})
        item['inherited_rules'] = inherited_rules
        
        if item.get('children'):
            child_parent_rules = list(parent_rules)
            for rule in item.get('rules', []):
                child_parent_rules.append((rule, item.get('title', 'Unknown')))
            _recalculate_inherited_rules(item['children'], child_parent_rules)

def _delete_item_recursive(items: List[Dict], item_id: str) -> bool:
    for idx, item in enumerate(items):
        if item.get('id') == item_id:
            items.pop(idx)
            return True
        if item.get('children'):
            if _delete_item_recursive(item['children'], item_id):
                return True
    return False

def update_item_status(chat_id: str, item_id: str, status: str) -> Tuple[Optional[Dict], Optional[str]]:
    metadata = _load_metadata(chat_id)
    if not metadata:
        return None, "Visualization not found"
    
    if status not in ["pending", "in_progress", "completed"]:
        return None, f"Invalid status: {status}"
    
    tracking = metadata.get("plan_tracking", {})
    tracking[item_id] = status
    metadata["plan_tracking"] = tracking
    metadata["updated_at"] = datetime.now().isoformat()
    
    _save_metadata(chat_id, metadata)
    
    plan_file = VIS_DIR / chat_id / "plan.json"
    if plan_file.exists():
        with open(plan_file, 'r') as f:
            plan_data = json.load(f)
        
        chat_name = metadata.get("name", "Unnamed")
        markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
        
        plan_md_path = get_plan_markdown_path(Path.cwd())
        plan_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
    
    return metadata, None


def _load_kb() -> Dict:
    root = get_project_root()
    kb_path = root / ".zoro" / "rules" / "structured" / "knowledge_base.json"
    
    if not kb_path.exists():
        return {'items': [], 'categories': []}
    
    with open(kb_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def add_rule_from_kb(chat_id: str, item_id: str, kb_item_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    kb = _load_kb()
    kb_item = next((item for item in kb['items'] if item['item_id'] == kb_item_id), None)
    
    if not kb_item:
        return None, f"KB item {kb_item_id} not found"
    
    plan_file = VIS_DIR / chat_id / "plan.json"
    if not plan_file.exists():
        return None, "Plan not found"
    
    with open(plan_file, 'r') as f:
        plan_data = json.load(f)
    
    items = plan_data.get('plan', {}).get('items', [])
    target_item, _, _ = _find_item_in_tree(items, item_id)
    
    if not target_item:
        return None, f"Item {item_id} not found in plan"
    
    rule = {
        "category": kb_item['category'],
        "text": kb_item['content'],
        "context": kb_item.get('context'),
        "evidence": kb_item.get('evidence'),
        "confidence": kb_item.get('confidence', 0.5),
        "decay": kb_item.get('decay', 0.5),
        "kb_item_id": kb_item_id,
        "needs_strict_enforcement": kb_item.get('is_strict', False),
        "is_testable": kb_item.get('is_testable', False)
    }
    
    if 'rules' not in target_item:
        target_item['rules'] = []
    
    target_item['rules'].append(rule)
    
    _recalculate_inherited_rules(items)
    
    with open(plan_file, 'w') as f:
        json.dump(plan_data, f, indent=2)
    
    return rule, None


def toggle_rule_strict_enforcement(chat_id: str, item_id: str, rule_index: int, enabled: bool) -> Tuple[Optional[Dict], Optional[str]]:
    plan_file = VIS_DIR / chat_id / "plan.json"
    if not plan_file.exists():
        return None, "Plan not found"
    
    with open(plan_file, 'r') as f:
        plan_data = json.load(f)
    
    items = plan_data.get('plan', {}).get('items', [])
    target_item, _, _ = _find_item_in_tree(items, item_id)
    
    if not target_item:
        return None, f"Item {item_id} not found in plan"
    
    rules = target_item.get('rules', [])
    if rule_index < 0 or rule_index >= len(rules):
        return None, f"Rule index {rule_index} out of range"
    
    rules[rule_index]['needs_strict_enforcement'] = enabled
    
    _recalculate_inherited_rules(items)
    
    with open(plan_file, 'w') as f:
        json.dump(plan_data, f, indent=2)
    
    return rules[rule_index], None
