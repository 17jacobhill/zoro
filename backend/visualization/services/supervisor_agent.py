import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from backend.utils import get_project_root, strip_markdown_json, get_enforcement_mode
from backend.globals.models import get_default_provider
from backend.visualization.prompts.supervisor import SUPERVISOR_PROMPT, SUPERVISOR_PROMPT_SIMPLE, SUPERVISOR_PROMPT_SELECTIVE

logger = logging.getLogger(__name__)


class SupervisorAgent:
    def __init__(self):
        self.provider = get_default_provider()
    
    def supervise(self, chat_id: str, content_window: str) -> Dict:
        logger.info(f"Supervising chat {chat_id}")
        
        chat_content = content_window
        plan = self._load_plan(chat_id)
        tracking = self._load_tracking(chat_id)
        
        if not plan:
            logger.warning(f"No plan found for chat {chat_id}")
            return self._create_empty_result("No plan available yet")
        
        # Choose prompt based on enforcement mode
        mode = get_enforcement_mode()
        if mode == "selective-verification":
            prompt_template = SUPERVISOR_PROMPT_SELECTIVE
            logger.info("Using selective supervisor prompt (selective-verification mode)")
        elif mode == "verification":
            prompt_template = SUPERVISOR_PROMPT
            logger.info("Using full supervisor prompt (verification mode)")
        else:
            prompt_template = SUPERVISOR_PROMPT_SIMPLE
            logger.info("Using simple supervisor prompt (no-verification mode)")
        
        prompt = prompt_template.format(
            chat_content=chat_content,
            plan=json.dumps(plan, indent=2),
            tracking=json.dumps(tracking, indent=2)
        )
        
        try:
            response = self.provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-5"
            )
            
            result = self._parse_response(response)
            logger.info(f"Supervision complete for {chat_id}: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Supervision failed for {chat_id}: {e}", exc_info=True)
            return self._create_error_result(str(e))
    
    
    def _load_plan(self, chat_id: str) -> Optional[Dict]:
        plan_path = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "plan.json"
        
        if not plan_path.exists():
            return None
        
        with open(plan_path, 'r') as f:
            return json.load(f)
    
    def _load_tracking(self, chat_id: str) -> Dict:
        metadata_path = get_project_root() / ".zoro" / "generated" / "visualization" / chat_id / "metadata.json"
        
        if not metadata_path.exists():
            return {}
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return metadata.get("plan_tracking", {})
    
    def _parse_response(self, response: str) -> Dict:
        try:
            cleaned = strip_markdown_json(response)
            result = json.loads(cleaned)
            
            required_fields = [
                "status",
                "summary",
                "action_required"
            ]
            
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            if "timestamp" not in result:
                result["timestamp"] = datetime.now().isoformat()
            
            if result["status"] not in ["on_track", "needs_attention", "blocked"]:
                result["status"] = "needs_attention"
            
            if not isinstance(result["action_required"], list):
                result["action_required"] = []
            
            if "blocker" in result and result["blocker"] is not None:
                if not isinstance(result["blocker"], dict):
                    result["blocker"] = None
            else:
                result["blocker"] = None
            
            if "current_step" not in result:
                result["current_step"] = None
            
            if "expected_step" not in result:
                result["expected_step"] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse supervision response: {e}", exc_info=True)
            return self._create_error_result(f"Parse error: {str(e)}")
    
    def _create_empty_result(self, reason: str) -> Dict:
        return {
            "status": "needs_attention",
            "summary": reason,
            "blocker": None,
            "action_required": [
                "1. Extract a plan using the 'Extract Plan' button",
                "2. Once plan is extracted, try supervision again"
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_error_result(self, error: str) -> Dict:
        return {
            "status": "needs_attention",
            "summary": f"Supervision encountered an error: {error}",
            "blocker": None,
            "action_required": [
                "1. Check backend logs for details",
                "2. Retry supervision",
                "3. If error persists, report to development team"
            ],
            "timestamp": datetime.now().isoformat()
        }
