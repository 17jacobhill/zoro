from __future__ import annotations
import json
from typing import List, Tuple
from pathlib import Path

from backend.globals.models import get_default_provider
from backend.globals.schemas import AnalyzedTaskV3, RuleV2, Plan, PlanStep, get_schema, AnalyzedTasksV3DB
from backend.learner.learning import load_all_analyzed_tasks
from backend.assistant.prompts.planning import (
    TASK_SELECTION_PROMPT,
    INITIAL_PLAN_PROMPT,
    PLAN_STRUCTURE_PROMPT,
    STEP_TASK_SELECTION_PROMPT,
    STEP_RULE_SELECTION_PROMPT
)
from backend.utils import get_project_root



def load_chat_tags() -> dict:
    tags_file = get_project_root() / ".zoro" / "generated" / "learner_tags.json"
    if not tags_file.exists():
        return {}
    with open(tags_file) as f:
        data = json.load(f)
    return data.get("chat_tags", {})


def load_task_descriptions(tags: List[str] = None, match_mode: str = 'any') -> List[Tuple[str, str]]:
    analyzed_dir = get_project_root() / ".zoro" / "generated" / "analyzed"
    if not analyzed_dir.exists():
        return []
    
    chat_tags = load_chat_tags() if tags else {}
    all_tasks = []
    
    for chat_file in analyzed_dir.glob("*.json"):
        chat_name = chat_file.stem
        
        if tags:
            file_tags = chat_tags.get(chat_name, [])
            if match_mode == 'all':
                if not all(tag in file_tags for tag in tags):
                    continue
            else:
                if not any(tag in file_tags for tag in tags):
                    continue
        
        with open(chat_file) as f:
            data = json.load(f)
            db = AnalyzedTasksV3DB(**data)
            all_tasks.extend(db.analyzed_tasks)
    
    return [(t.task_id, t.task) for t in all_tasks]


def load_tasks_by_ids(task_ids: List[str], tags: List[str] = None, match_mode: str = 'any') -> List[AnalyzedTaskV3]:
    analyzed_dir = get_project_root() / ".zoro" / "generated" / "analyzed"
    if not analyzed_dir.exists():
        return []
    
    chat_tags = load_chat_tags() if tags else {}
    all_tasks = []
    
    for chat_file in analyzed_dir.glob("*.json"):
        chat_name = chat_file.stem
        
        if tags:
            file_tags = chat_tags.get(chat_name, [])
            if match_mode == 'all':
                if not all(tag in file_tags for tag in tags):
                    continue
            else:
                if not any(tag in file_tags for tag in tags):
                    continue
        
        with open(chat_file) as f:
            data = json.load(f)
            db = AnalyzedTasksV3DB(**data)
            all_tasks.extend(db.analyzed_tasks)
    
    return [t for t in all_tasks if t.task_id in task_ids]


def select_relevant_tasks_for_analysis(query: str, task_descriptions: List[Tuple[str, str]], model: str = 'gpt-5') -> List[str]:
    provider = get_default_provider()
    
    formatted_descriptions = "\n".join([f"{task_id}: {desc}" for task_id, desc in task_descriptions])
    
    prompt = TASK_SELECTION_PROMPT.format(
        query=query,
        task_descriptions=formatted_descriptions
    )
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    data = json.loads(response)
    return data.get("task_ids", [])


def generate_plan_structure(query: str, relevant_tasks: List[AnalyzedTaskV3], model: str = 'gpt-5') -> Plan:
    provider = get_default_provider()
    
    prompt = INITIAL_PLAN_PROMPT.format(query=query)
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        response_format=get_schema(Plan.model_json_schema())
    )
    
    plan_data = json.loads(response)
    return Plan(**plan_data)


def select_tasks_for_step(step_objective: str, task_descriptions: List[Tuple[str, str]], model: str = 'gpt-5') -> List[str]:
    provider = get_default_provider()
    
    formatted_descriptions = "\n".join([f"{task_id}: {desc}" for task_id, desc in task_descriptions])
    
    prompt = STEP_TASK_SELECTION_PROMPT.format(
        step_objective=step_objective,
        task_descriptions=formatted_descriptions
    )
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    data = json.loads(response)
    return data.get("task_ids", [])


def select_rules_for_step(step_objective: str, rules: List[RuleV2], limit: int = 5, model: str = 'gpt-5') -> List[RuleV2]:
    provider = get_default_provider()
    
    formatted_rules = []
    for rule in rules:
        formatted_rules.append(f"ID: {rule.rule_id}\nRule: {rule.rule}\nReasoning: {rule.reasoning}")
    
    rules_text = "\n\n".join(formatted_rules)
    
    prompt = STEP_RULE_SELECTION_PROMPT.format(
        step_objective=step_objective,
        rules=rules_text,
        limit=limit
    )
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    data = json.loads(response)
    selected_ids = data.get("rule_ids", [])
    
    return [r for r in rules if r.rule_id in selected_ids]


def generate_plan(task_query: str, model: str = 'gpt-5', tags: List[str] = None, match_mode: str = 'any') -> Plan:
    print(f"Generating plan for: {task_query}")
    if tags:
        mode_str = "all of" if match_mode == 'all' else "any of"
        print(f"Filtering by tags: {mode_str} [{', '.join(tags)}]")
    
    print("\nStage 1: Initial task analysis...")
    task_descriptions = load_task_descriptions(tags=tags, match_mode=match_mode)
    
    if not task_descriptions:
        if tags:
            mode_str = "all tags" if match_mode == 'all' else "any of these tags"
            print(f"No tasks found with {mode_str}: {', '.join(tags)}")
        else:
            print("No tasks found in database. Run 'zoro process' first.")
        return Plan(
            task_query=task_query,
            reasoning="No past tasks available for analysis",
            steps=[]
        )
    
    print(f"  Found {len(task_descriptions)} total tasks")
    
    relevant_task_ids = select_relevant_tasks_for_analysis(task_query, task_descriptions, model)
    print(f"  Selected {len(relevant_task_ids)} relevant tasks")
    
    relevant_tasks = load_tasks_by_ids(relevant_task_ids, tags=tags, match_mode=match_mode)
    
    plan = generate_plan_structure(task_query, relevant_tasks, model)
    print(f"  Generated plan with {len(plan.steps)} steps")
    
    print("\nStage 2: Per-step rule retrieval...")
    for i, step in enumerate(plan.steps, 1):
        print(f"  Step {i}: {step.objective[:60]}...")
        
        step_query = step.objective
        step_task_ids = select_tasks_for_step(step_query, task_descriptions, model)
        print(f"    Found {len(step_task_ids)} relevant tasks")
        
        step_tasks = load_tasks_by_ids(step_task_ids, tags=tags, match_mode=match_mode)
        all_step_rules = [rule for task in step_tasks for rule in task.rules]
        print(f"    Total {len(all_step_rules)} rules available")
        
        if all_step_rules:
            step.rules = select_rules_for_step(step.objective, all_step_rules, limit=10, model=model)
            print(f"    Selected {len(step.rules)} rules")
    
    print("\n✓ Plan generation complete")
    return plan
