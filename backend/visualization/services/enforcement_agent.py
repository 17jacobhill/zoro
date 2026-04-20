import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from backend.utils import get_project_root, strip_markdown_json, get_enforcement_mode
from backend.globals.models import get_default_provider
from backend.visualization.prompts.enforcement import ENFORCEMENT_PROMPT
from backend.visualization.services.plan_tracker import (
    load_plan_data, 
    save_plan_data, 
    collect_rules_for_item
)

logger = logging.getLogger(__name__)


class EnforcementAgent:
    def __init__(self):
        self.provider = get_default_provider()
    
    def enforce_single_item(self, chat_id: str, item_id: str, content_window: str) -> Dict:
        logger.info("="*80)
        logger.info(f"SINGLE ITEM ENFORCEMENT - Chat ID: {chat_id}, Item ID: {item_id}")
        logger.info("="*80)
        
        plan_data = load_plan_data(chat_id)
        if not plan_data:
            return self._create_error_result("No plan found")
        
        # Find the specific item
        def find_item(items, target_id):
            for item in items:
                if item.get('id') == target_id:
                    return item
                if item.get('children'):
                    found = find_item(item.get('children'), target_id)
                    if found:
                        return found
            return None
        
        target_item = find_item(self._get_root_items(plan_data), item_id)
        if not target_item:
            return self._create_error_result(f"Item {item_id} not found in plan")
        
        # Check if it's a leaf node
        has_children = target_item.get('children') and len(target_item.get('children', [])) > 0
        if has_children:
            return self._create_error_result(f"Item {item_id} is not a leaf node. Only leaf nodes can be enforced.")
        
        logger.info(f"\n📋 ENFORCING ITEM: {item_id} - {target_item.get('title', 'Untitled')}")
        
        # Load enforcement mode
        mode = get_enforcement_mode()
        is_selective = mode == 'selective-verification'
        
        rules = target_item.get('rules', [])
        inherited_rules = target_item.get('inherited_rules', [])
        
        logger.info(f"  Enforcement mode: {mode}")
        logger.info(f"  Own rules (before filtering): {len(rules)}")
        logger.info(f"  Inherited rules (before filtering): {len(inherited_rules)}")
        
        # FILTER rules to NON-strict only if in selective mode (UI button path)
        if is_selective:
            rules = [r for r in rules if not r.get('needs_strict_enforcement', False)]
            inherited_rules = [
                ir for ir in inherited_rules 
                if not ir['rule'].get('needs_strict_enforcement', False)
            ]
            logger.info(f"  📋 Selective mode: filtered to {len(rules)} own rules and {len(inherited_rules)} inherited rules WITHOUT strict enforcement")
        
        logger.info(f"  Own rules (after filtering): {len(rules)}")
        for rule in rules:
            strict_marker = "⚡" if rule.get('needs_strict_enforcement', False) else ""
            logger.info(f"    {strict_marker} [{rule.get('category')}] {rule.get('text')}")
        
        if inherited_rules:
            logger.info(f"  Inherited rules (after filtering): {len(inherited_rules)}")
            for ir in inherited_rules:
                rule = ir['rule']
                strict_marker = "⚡" if rule.get('needs_strict_enforcement', False) else ""
                logger.info(f"    {strict_marker} [{rule.get('category')}] {rule.get('text')} (from {ir['source']})")
        
        # Create a filtered item copy with only the rules to verify
        filtered_item = target_item.copy()
        filtered_item['rules'] = rules
        filtered_item['inherited_rules'] = inherited_rules
        
        # Create filtered plan with the filtered item
        filtered_plan = {
            "items": [filtered_item],
            "note": f"Enforcing single item: {item_id} (mode: {mode})"
        }
        
        prompt = ENFORCEMENT_PROMPT.format(
            chat_content=content_window,
            plan=json.dumps(filtered_plan, indent=2),
            tracking=json.dumps({item_id: "in_progress"}, indent=2)
        )
        
        try:
            response = self.provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-5"
            )
            
            result = self._parse_response(response)
            
            # Save only to enforcement_history.json (no tracking update, no runs)
            self._save_single_item_enforcement(chat_id, item_id, result)
            
            logger.info(f"Single item enforcement complete for {item_id}")
            return result
            
        except Exception as e:
            logger.error(f"Single item enforcement failed: {e}", exc_info=True)
            return self._create_error_result(str(e))
    
    def _get_root_items(self, plan_data: Dict) -> List[Dict]:
        """Get root items regardless of plan structure type."""
        plan = plan_data.get('plan', {})
        
        # Try all possible root keys based on structure_type
        if 'phases' in plan:
            return plan['phases']
        elif 'steps' in plan:
            return plan['steps']
        elif 'items' in plan:
            return plan['items']
        else:
            return []
    
    def _parse_response(self, response: str) -> Dict:
        try:
            cleaned = strip_markdown_json(response)
            result = json.loads(cleaned)
            
            if "completed_items" not in result:
                result["completed_items"] = []
            if "overall_status" not in result:
                result["overall_status"] = "needs_attention"
            
            result["timestamp"] = datetime.now().isoformat()
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse enforcement response: {e}")
            return self._create_error_result(f"Parse error: {str(e)}")
    
    def _save_single_item_enforcement(self, chat_id: str, item_id: str, result: Dict):
        history_path = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "enforcement_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                # File exists but is empty or corrupted, start fresh
                logger.warning(f"Corrupted enforcement_history.json for {chat_id}, starting fresh")
                data = {"items": {}, "runs": []}
        else:
            data = {"items": {}, "runs": []}
        
        # Extract the enforcement result for this item
        completed_items = result.get("completed_items", [])
        if completed_items:
            item_result = completed_items[0]  # Should only be one item
            data["items"][item_id] = {
                "last_enforced": result["timestamp"],
                "detected_evidence": item_result.get("detected_evidence", ""),
                "rules_verified": item_result.get("rules_verified", [])
            }
        
        with open(history_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _create_error_result(self, error: str) -> Dict:
        return {
            "completed_items": [],
            "overall_status": "needs_attention",
            "error": error,
            "timestamp": datetime.now().isoformat()
        }


def get_enforcement_history(chat_id: str) -> Dict:
    history_path = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "enforcement_history.json"
    
    if not history_path.exists():
        return {"items": {}, "runs": []}
    
    with open(history_path, 'r') as f:
        data = json.load(f)
    
    if "items" not in data:
        data["items"] = {}
    if "runs" not in data:
        data["runs"] = []
    
    return data


