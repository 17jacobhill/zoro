from backend.globals.models import get_default_provider
from backend.globals.schemas import TaskTypesDB, get_schema
from backend.globals.task_types import DEFAULT_TASK_TYPES
from backend.learner.prompts.categorizer import BATCH_CATEGORIZER_PROMPT
from backend.utils import get_project_root
from pathlib import Path
import json
import tiktoken
from typing import List, Dict, Any


class TaskCategorizer:
    
    def __init__(self, model: str = "gpt-5.1"):
        self._model = model
        self._provider = get_default_provider()
        self._types_path = get_project_root() / ".zoro" / "generated" / "task_types.json"
        self._user_types_cache = None
    
    def _load_user_types(self) -> list:
        if self._user_types_cache is not None:
            return self._user_types_cache
        
        if not self._types_path.exists():
            self._user_types_cache = []
            return []
        
        with open(self._types_path) as f:
            data = json.load(f)
            db = TaskTypesDB(**data)
            self._user_types_cache = [{"name": t.name, "description": t.description} for t in db.task_types]
            return self._user_types_cache
    
    def _get_all_types(self) -> list:
        return DEFAULT_TASK_TYPES + self._load_user_types()
    
    def _categorize_chunk(self, tasks_chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_types = self._get_all_types()
        type_list = "\n".join([f"- {t['name']}: {t['description']}" for t in all_types])
        
        slim_tasks = [
            {"task_id": t["task_id"], "raw_data": t["raw_data"]} 
            for t in tasks_chunk
        ]
        tasks_json = json.dumps(slim_tasks, indent=2)
        
        prompt = BATCH_CATEGORIZER_PROMPT.format(
            type_list=type_list,
            tasks_json=tasks_json
        )
        
        schema = {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "task": {"type": "string"},
                            "type": {"type": "string"},
                            "confidence": {"type": "integer", "minimum": 1, "maximum": 10},
                            "description": {"type": "string"}
                        },
                        "required": ["task_id", "task", "type", "confidence", "description"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["suggestions"],
            "additionalProperties": False
        }
        
        response = self._provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self._model,
            response_format=get_schema(schema)
        )
        
        result = json.loads(response)
        return result["suggestions"]
    
    def _estimate_tokens(self, text: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4
    
    def categorize_batch(self, tasks: List[Dict[str, Any]], max_tokens: int = 200_000) -> List[Dict[str, Any]]:
        if len(tasks) == 0:
            return []
        
        all_types = self._get_all_types()
        type_list = "\n".join([f"- {t['name']}: {t['description']}" for t in all_types])
        base_prompt_tokens = self._estimate_tokens(BATCH_CATEGORIZER_PROMPT.format(
            type_list=type_list,
            tasks_json=""
        ))
        
        batches = []
        current_batch = []
        current_tokens = base_prompt_tokens
        
        print(f"\nCreating token-aware batches (max {max_tokens:,} tokens per batch)...")
        print(f"  Base prompt: ~{base_prompt_tokens:,} tokens")
        
        for task in tasks:
            slim_task = {"task_id": task["task_id"], "raw_data": task["raw_data"]}
            task_json = json.dumps(slim_task, indent=2)
            task_tokens = self._estimate_tokens(task_json)
            
            if current_tokens + task_tokens > max_tokens and current_batch:
                batches.append(current_batch)
                current_batch = [task]
                current_tokens = base_prompt_tokens + task_tokens
            else:
                current_batch.append(task)
                current_tokens += task_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        print(f"  Created {len(batches)} batches from {len(tasks)} tasks\n")
        
        all_results = []
        for i, batch in enumerate(batches, 1):
            batch_tokens = base_prompt_tokens + sum(
                self._estimate_tokens(json.dumps({"task_id": t["task_id"], "raw_data": t["raw_data"]}, indent=2))
                for t in batch
            )
            print(f"  Processing batch {i}/{len(batches)}: {len(batch)} tasks (~{batch_tokens:,} tokens)...")
            
            batch_results = self._categorize_chunk(batch)
            all_results.extend(batch_results)
        
        print(f"✓ Categorization complete: {len(all_results)} tasks categorized\n")
        
        return all_results
