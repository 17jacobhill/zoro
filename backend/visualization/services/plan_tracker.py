import json
from pathlib import Path
from typing import List, Optional

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
    items = plan_data.get('plan', {}).get('items', [])
    target_item = find_item_by_id(items, item_id)
    if not target_item:
        return []

    collected = []
    seen_rules = set()

    for idx, rule in enumerate(target_item.get('rules', [])):
        rule_key = (rule.get('kb_item_id', ''), rule.get('category', ''), rule.get('text', ''))
        if rule_key in seen_rules:
            continue
        seen_rules.add(rule_key)
        collected.append({
            'rule': rule,
            'source': 'self',
            'source_id': item_id,
            'source_title': target_item.get('title', item_id),
            'is_inherited': False,
            'rule_index': idx
        })

    for idx, inherited in enumerate(target_item.get('inherited_rules', [])):
        rule = inherited.get('rule', {})
        rule_key = (rule.get('kb_item_id', ''), rule.get('category', ''), rule.get('text', ''))
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


def build_rules_in_focus_snapshot(plan_data: dict, step_id: str | None) -> Optional[dict]:
    if not step_id:
        return None

    items = plan_data.get('plan', {}).get('items', [])
    if not items:
        return None

    item = find_item_by_id(items, step_id)
    if not item:
        return None

    serialized_rules = []
    seen = set()

    for rule in item.get('rules', []):
        key = ('own', rule.get('category', ''), rule.get('text', ''))
        if key in seen:
            continue
        seen.add(key)
        serialized_rules.append(
            {
                'source': 'own',
                'source_title': item.get('title', step_id),
                'category': rule.get('category', 'uncategorized'),
                'text': rule.get('text', ''),
                'needs_strict_enforcement': bool(rule.get('needs_strict_enforcement', False)),
                'is_testable': bool(rule.get('is_testable', False)),
            }
        )

    for inherited in item.get('inherited_rules', []):
        rule = inherited.get('rule', {})
        source_title = inherited.get('source', 'Inherited')
        key = ('inherited', source_title, rule.get('category', ''), rule.get('text', ''))
        if key in seen:
            continue
        seen.add(key)
        serialized_rules.append(
            {
                'source': 'inherited',
                'source_title': source_title,
                'category': rule.get('category', 'uncategorized'),
                'text': rule.get('text', ''),
                'needs_strict_enforcement': bool(rule.get('needs_strict_enforcement', False)),
                'is_testable': bool(rule.get('is_testable', False)),
            }
        )

    return {
        'step_id': step_id,
        'step_title': item.get('title', step_id),
        'rules': serialized_rules,
    }

def load_plan_data(chat_id: str) -> Optional[dict]:
    from backend.visualization.services.plan_persistence import load_plan_document

    return load_plan_document(chat_id)

def save_plan_data(chat_id: str, data: dict):
    from backend.visualization.services.plan_persistence import save_plan_document

    save_plan_document(chat_id, data)

def refresh_plan_markdown(chat_id: str):
    from backend.visualization.services.plan_persistence import refresh_plan_markdown as refresh_plan_markdown_document

    refresh_plan_markdown_document(chat_id)

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


def collect_leaf_items(items: list) -> list[dict]:
    leaves = []
    for item in items:
        children = item.get("children", [])
        if children:
            leaves.extend(collect_leaf_items(children))
        else:
            leaves.append(item)
    return leaves


def get_next_pending_leaf_item(plan_data: dict, tracking: dict, after_item_id: str | None = None) -> Optional[dict]:
    leaf_items = collect_leaf_items(plan_data.get("plan", {}).get("items", []))
    if not leaf_items:
        return None

    start_index = 0
    if after_item_id:
        for idx, item in enumerate(leaf_items):
            if item.get("id") == after_item_id:
                start_index = idx + 1
                break

    remaining = leaf_items[start_index:] + leaf_items[:start_index]
    for item in remaining:
        status = tracking.get(item.get("id", ""), "pending")
        if status != "completed":
            return item
    return None


def plan_to_markdown(chat_id: str, chat_name: str, plan_data: dict, tracking: dict) -> str:
    mode = get_enforcement_mode()
    items = plan_data.get("plan", {}).get("items", [])
    
    md = f"# Visualization Plan: {chat_name or 'Unnamed'} ({chat_id})\n\n"
    md += "**Rule flags:** [STRICT] requires explicit verification before completion. [TESTABLE] requires test evidence when verifying.\n\n"
    next_item = get_next_pending_leaf_item(plan_data, tracking)
    if next_item:
        next_item_id = next_item.get("id", "")
        next_number = next_item.get("number", "")
        next_title = next_item.get("title", "")
        next_status = tracking.get(next_item_id, "pending")
        md += f"**Next Step:** {next_number} `{next_item_id}` - {next_title} ({next_status})\n"
        md += f"**Run Next:** `zoro update-step {next_item_id} in_progress`\n\n"
    else:
        md += "**Next Step:** All leaf steps are complete.\n\n"
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
        md += f"{indent}- Start: `zoro update-step {item_id} in_progress`\n"
        md += f"{indent}- Complete: `zoro update-step {item_id} completed`\n\n"
        
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
