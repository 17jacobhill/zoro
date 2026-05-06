from typing import Tuple, Optional
import json
from backend.visualization.paths import get_existing_plan_path


def _load_plan(chat_id: str) -> Optional[dict]:
    plan_path = get_existing_plan_path(chat_id)
    if not plan_path.exists():
        return None
    
    with open(plan_path, 'r') as f:
        return json.load(f)


def _find_item_in_plan(items: list, item_id: str) -> Optional[dict]:
    for item in items:
        if item.get('id') == item_id:
            return item
        
        if item.get('children'):
            result = _find_item_in_plan(item['children'], item_id)
            if result:
                return result
    
    return None


def validate_item_can_start(chat_id: str, item_id: str) -> Tuple[bool, str]:
    plan_data = _load_plan(chat_id)
    if not plan_data:
        return False, f"Plan not found for chat {chat_id}"
    
    items = plan_data.get('plan', {}).get('items', [])
    item = _find_item_in_plan(items, item_id)
    
    if not item:
        return False, f"Item {item_id} not found in plan"
    
    has_unresolved_conflicts = item.get('has_unresolved_conflicts', False)
    
    if has_unresolved_conflicts:
        conflicts = item.get('conflicts', [])
        unresolved_count = sum(1 for c in conflicts if not c.get('resolved', False))
        
        return False, (
            f"❌ Cannot start item {item_id}: {unresolved_count} unresolved rule conflict(s) detected.\n"
            f"Please resolve conflicts in the frontend UI before starting this item."
        )
    
    return True, "OK"


def validate_item_can_complete(chat_id: str, item_id: str) -> Tuple[bool, str]:
    plan_data = _load_plan(chat_id)
    if not plan_data:
        return False, f"Plan not found for chat {chat_id}"
    
    items = plan_data.get('plan', {}).get('items', [])
    item = _find_item_in_plan(items, item_id)
    
    if not item:
        return False, f"Item {item_id} not found in plan"
    
    has_unresolved_conflicts = item.get('has_unresolved_conflicts', False)
    
    if has_unresolved_conflicts:
        conflicts = item.get('conflicts', [])
        unresolved_count = sum(1 for c in conflicts if not c.get('resolved', False))
        
        return False, (
            f"❌ Cannot complete item {item_id}: {unresolved_count} unresolved rule conflict(s) detected.\n"
            f"Please resolve conflicts in the frontend UI before completing this item."
        )
    
    return True, "OK"
