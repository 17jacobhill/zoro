from pathlib import Path
from typing import Optional, List
import json
import copy
from backend.utils import get_enforcement_mode
from backend.plan_paths import get_existing_plan_markdown_path, get_plan_markdown_path

def find_item_by_id(items: list, item_id: str) -> Optional[dict]:
    for item in items:
        if item.get('id') == item_id:
            return item
        if item.get('children'):
            result = find_item_by_id(item['children'], item_id)
            if result:
                return result
    return None

def collect_rules_for_item(plan_data: dict, item_id: str) -> List[dict]:
    def build_parent_map(items, parent=None, parent_map=None):
        if parent_map is None:
            parent_map = {}
        for item in items:
            current_item_id = item.get('id')
            if current_item_id:
                parent_map[current_item_id] = parent.get('id') if parent else None
                if item.get('children'):
                    build_parent_map(item['children'], item, parent_map)
        return parent_map
    
    items = plan_data.get('plan', {}).get('items', [])
    parent_map = build_parent_map(items)
    
    target_item = find_item_by_id(items, item_id)
    if not target_item:
        return []
    
    collected = []
    seen_rules = set()
    current_id = item_id
    
    while current_id:
        current_item = find_item_by_id(items, current_id)
        if current_item:
            for idx, rule in enumerate(current_item.get('rules', [])):
                rule_key = (rule.get('category', ''), rule.get('text', ''))
                
                if rule_key not in seen_rules:
                    seen_rules.add(rule_key)
                    source = 'self' if current_id == item_id else 'parent'
                    collected.append({
                        'rule': rule,
                        'source': source,
                        'source_id': current_id,
                        'source_title': current_item.get('title', current_id),
                        'is_inherited': False,
                        'rule_index': idx
                    })
        current_id = parent_map.get(current_id)
    
    for idx, inherited in enumerate(target_item.get('inherited_rules', [])):
        rule = inherited['rule']
        rule_key = (rule.get('category', ''), rule.get('text', ''))
        if rule_key not in seen_rules:
            seen_rules.add(rule_key)
            collected.append({
                'rule': rule,
                'source': 'parent',
                'source_id': item_id,
                'source_title': inherited.get('source', 'Inherited'),
                'is_inherited': True,
                'inherited_index': idx,
                'inherited_entry': inherited
            })
    
    return collected

def load_plan_data(chat_id: str) -> Optional[dict]:
    plan_path = Path(f".zoro/generated/visualization/{chat_id}/plan.json")
    if not plan_path.exists():
        return None
    
    with open(plan_path) as f:
        return json.load(f)

def save_plan_data(chat_id: str, data: dict):
    plan_path = Path(f".zoro/generated/visualization/{chat_id}/plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(plan_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    refresh_plan_markdown(chat_id)

def refresh_plan_markdown(chat_id: str):
    from backend.visualization.services.visualization_manager import _load_metadata
    metadata = _load_metadata(chat_id)
    if not metadata:
        return

    plan_file = Path(f".zoro/generated/visualization/{chat_id}/plan.json")
    if not plan_file.exists():
        return

    with open(plan_file, 'r') as f:
        plan_data = json.load(f)

    tracking = metadata.get("plan_tracking", {})
    chat_name = metadata.get("name", "Unnamed")
    markdown = plan_to_markdown(chat_id, chat_name, plan_data, tracking)
    
    plan_md_path = get_plan_markdown_path(Path.cwd())
    plan_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_md_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

def flatten_plan_items(items: list, parent_prefix="") -> list:
    flat = []
    for i, item in enumerate(items, 1):
        item_id = f"{parent_prefix}{i}" if parent_prefix else f"{i}"
        flat.append({
            "id": item_id,
            "number": item.get("number", item_id),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "rules": item.get("rules", [])
        })
        children = item.get("children", [])
        if children:
            flat.extend(flatten_plan_items(children, f"{item_id}-"))
    return flat


def plan_to_markdown(chat_id: str, chat_name: str, plan_data: dict, tracking: dict) -> str:
    mode = get_enforcement_mode()
    items = plan_data.get("plan", {}).get("items", [])
    
    md = f"# Visualization Plan: {chat_name or 'Unnamed'} ({chat_id})\n\n"
    md += "**Rule flags:** [STRICT] requires explicit verification before completion. [TESTABLE] requires test evidence when verifying.\n\n"
    md += "## Items\n\n"
    
    def format_rule_flags(rule: dict) -> str:
        labels = []
        if rule.get('needs_strict_enforcement', False):
            labels.append("STRICT")
        if rule.get('is_testable', False):
            labels.append("TESTABLE")
        return f" {' '.join(f'[{label}]' for label in labels)}" if labels else ""

    def render_item(item: dict, parent_prefix="", level=0):
        nonlocal md
        
        item_id = item.get("id", "")
        number = item.get("number", "")
        title = item.get("title", "")
        description = item.get("description", "")
        rules = item.get("rules", [])
        children = item.get("children", [])
        has_unresolved_conflicts = item.get("has_unresolved_conflicts", False)
        conflicts = item.get("conflicts", [])
        
        status = tracking.get(item_id, "pending")
        if has_unresolved_conflicts:
            status = "blocked"
        
        indent = "  " * level
        
        md += f"{indent}### {number}: {title}\n"
        md += f"{indent}**Status:** {status}\n\n"
        
        if description:
            md += f"{indent}{description}\n\n"
        
        md += f"{indent}**Tracking:**\n"
        md += f"{indent}- Start: `zoro viz-update {item_id} in_progress`\n"
        md += f"{indent}- Complete: `zoro viz-update {item_id} completed`\n\n"
        
        if has_unresolved_conflicts and conflicts:
            md += f"{indent}⚠️ **RULE CONFLICTS DETECTED**\n\n"
            md += f"{indent}This item cannot be started or completed until conflicts are resolved in the frontend UI.\n\n"
            for conflict in conflicts:
                if not conflict.get('resolved', False):
                    conflict_id = conflict.get('conflict_id', 'unknown')
                    explanation = conflict.get('explanation', 'No explanation provided')
                    severity = conflict.get('severity', 'unknown')
                    
                    md += f"{indent}**Conflict {conflict_id}** (Severity: {severity}):\n"
                    md += f"{indent}{explanation}\n\n"
                    
                    rule_indices = conflict.get('rule_indices', {})
                    if item_id in rule_indices:
                        indices = rule_indices[item_id]
                        md += f"{indent}Conflicting rules in this item (indices: {indices}):\n"
                        for idx in indices:
                            if idx < len(rules):
                                rule = rules[idx]
                                flags = format_rule_flags(rule)
                                md += f"{indent}- [{rule.get('category', 'rule')}] {rule.get('text', '')}{flags}\n"
                        md += "\n"
            
            md += f"{indent}**To resolve:** Use the frontend UI to select which rule to keep for each conflict.\n\n"
        
        if rules:
            md += f"{indent}**Rules:**\n"
            for rule in rules:
                category = rule.get('category', 'rule')
                text = rule.get('text', '')
                flags = format_rule_flags(rule)
                md += f"{indent}- [{category}] {text}{flags}\n"
            md += "\n"
        
        md += f"{indent}---\n\n"
        
        if children:
            for child in children:
                render_item(child, item_id, level + 1)
    
    for item in items:
        render_item(item, "", 0)
    
    return md


def get_chat_id_from_plan_md() -> Optional[str]:
    plan_path = get_existing_plan_markdown_path(Path.cwd())
    if not plan_path.exists():
        return None
    
    with open(plan_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    
    if '(' in first_line and ')' in first_line:
        start = first_line.rfind('(')
        end = first_line.rfind(')')
        if start != -1 and end != -1 and end > start:
            return first_line[start+1:end]
    
    return None
