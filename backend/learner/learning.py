from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import List, Union

from backend.globals.models import get_default_provider
from backend.globals.schemas import Task, RuleV2, AnalyzedTaskV3, AnalyzedTasksV3DB, AnalyzedTaskV4, AnalyzedTasksV4DB, get_schema
from backend.learner.prompts.learning import (
    LEARNING_PROMPT_v3, 
    LEARNING_PROMPT_v3_NO_EVIDENCE, 
    LEARNING_PROMPT_v3_NO_CHUNKING, 
    LEARNING_PROMPT_v3_NO_CHUNKING_NO_EVIDENCE,
    LEARNING_PROMPT_V4_RULES_ONLY,
    LEARNING_PROMPT_V4_RULES_ONLY_NO_EVIDENCE,
    LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING,
    LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING_NO_EVIDENCE
)
from backend.utils import get_project_root


class TaskLearner:
    def __init__(self, user_name: str, chat_name: str, model: str = 'gpt-5', use_evidence_prompt: bool = True, no_task_chunking: bool = False, rules_only: bool = False):
        self._user_name = user_name
        self._chat_name = chat_name
        self._model = model
        self._use_evidence_prompt = use_evidence_prompt
        self._no_task_chunking = no_task_chunking
        self._rules_only = rules_only
        self._provider = get_default_provider()
        self._project_root = get_project_root()
        self._generated_dir = self._project_root / ".zoro" / "generated"
        self._analyzed_dir = self._generated_dir / "analyzed"
        self._db_path = self._analyzed_dir / f"{chat_name}.json"
    
    def _load_db(self) -> Union[AnalyzedTasksV3DB, AnalyzedTasksV4DB]:
        if not self._db_path.exists():
            return AnalyzedTasksV4DB(analyzed_tasks=[]) if self._rules_only else AnalyzedTasksV3DB(analyzed_tasks=[])
        
        with open(self._db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if self._rules_only:
            return AnalyzedTasksV4DB(**data)
        return AnalyzedTasksV3DB(**data)
    
    def _save_db(self, db: Union[AnalyzedTasksV3DB, AnalyzedTasksV4DB]):
        self._analyzed_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self._db_path, 'w', encoding='utf-8') as f:
            json.dump(db.model_dump(), f, indent=2)

    def learn(self, tasks: List[Task]) -> Union[AnalyzedTasksV3DB, AnalyzedTasksV4DB]:
        if self._rules_only:
            return self._learn_rules_only(tasks)
        return self._learn_trajectory(tasks)

    def _learn_trajectory(self, tasks: List[Task]) -> AnalyzedTasksV3DB:
        db = self._load_db()
        
        if self._no_task_chunking:
            prompt_template = LEARNING_PROMPT_v3_NO_CHUNKING_NO_EVIDENCE if not self._use_evidence_prompt else LEARNING_PROMPT_v3_NO_CHUNKING
        else:
            prompt_template = LEARNING_PROMPT_v3_NO_EVIDENCE if not self._use_evidence_prompt else LEARNING_PROMPT_v3
        
        for i, task in enumerate(tasks, 1):
            print(f"  Analyzing task {i}/{len(tasks)}: {task.description[:50]}...")
            
            prompt = prompt_template.format(
                user_name=self._user_name,
                task_description=task.description,
                inputs=task.raw_data
            )
            
            response = self._provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
                response_format=get_schema(AnalyzedTaskV3.model_json_schema())
            )
            
            task_data = json.loads(response)
            
            task_id = str(uuid.uuid4())
            task_data['task_id'] = task_id
            task_data['description'] = task.description
            
            # Preserve suggested_type from original task
            if task.suggested_type:
                task_data['suggested_type'] = task.suggested_type
            
            for rule in task_data.get('rules', []):
                rule['rule_id'] = str(uuid.uuid4())
                rule['from_task_id'] = task_id
            
            analyzed_task = AnalyzedTaskV3(**task_data)
            db.analyzed_tasks.append(analyzed_task)
        
        self._save_db(db)
        return db

    def _learn_rules_only(self, tasks: List[Task]) -> AnalyzedTasksV4DB:
        db = self._load_db()

        if self._no_task_chunking:
            prompt_template = LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING_NO_EVIDENCE if not self._use_evidence_prompt else LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING
        else:
            prompt_template = LEARNING_PROMPT_V4_RULES_ONLY_NO_EVIDENCE if not self._use_evidence_prompt else LEARNING_PROMPT_V4_RULES_ONLY

        for i, task in enumerate(tasks, 1):
            print(f"  Analyzing task {i}/{len(tasks)} for rules only: {task.description[:50]}...")
            
            prompt = prompt_template.format(inputs=task.raw_data)
            
            response = self._provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
                response_format=get_schema(AnalyzedTaskV4.model_json_schema())
            )
            
            task_data = json.loads(response)
            
            task_id = str(uuid.uuid4())
            task_data['task_id'] = task_id
            task_data['description'] = task.description
            
            for rule in task_data.get('rules', []):
                rule['rule_id'] = str(uuid.uuid4())
                rule['from_task_id'] = task_id
            
            analyzed_task = AnalyzedTaskV4(**task_data)
            db.analyzed_tasks.append(analyzed_task)
            
        self._save_db(db)
        return db


# Backward compatibility functions for existing code
def _load_analyzed_tasks_v3() -> AnalyzedTasksV3DB:
    learner = TaskLearner(user_name="", chat_name="default")
    return learner._load_db()


def _save_analyzed_tasks_v3(db: AnalyzedTasksV3DB):
    learner = TaskLearner(user_name="", chat_name="default")
    learner._save_db(db)


def process_tasks_v3(tasks: List[Task], user_name: str, chat_name: str, model: str = 'gpt-5', use_evidence_prompt: bool = True, no_task_chunking: bool = False, rules_only: bool = False) -> Union[AnalyzedTasksV3DB, AnalyzedTasksV4DB]:
    learner = TaskLearner(user_name=user_name, chat_name=chat_name, model=model, use_evidence_prompt=use_evidence_prompt, no_task_chunking=no_task_chunking, rules_only=rules_only)
    return learner.learn(tasks)


def load_all_analyzed_tasks(tags: List[str] = None) -> List[AnalyzedTaskV3]:
    from backend.globals.tag_registry import TagRegistry
    
    analyzed_dir = get_project_root() / ".zoro" / "generated" / "analyzed"
    
    if not analyzed_dir.exists():
        return []
    
    if tags:
        registry = TagRegistry()
        allowed_chats = registry.get_chats_by_tags(tags)
        
        if not allowed_chats:
            return []
    
    all_tasks = []
    for json_file in analyzed_dir.glob("*.json"):
        chat_name = json_file.stem
        
        if tags and chat_name not in allowed_chats:
            continue
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            db = AnalyzedTasksV3DB(**data)
            all_tasks.extend(db.analyzed_tasks)
        except Exception as e:
            print(f"Warning: Failed to load {json_file}: {e}")
    
    return all_tasks
