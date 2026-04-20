from __future__ import annotations
import json
from typing import List, Tuple
from pathlib import Path

from backend.globals.models import get_default_provider
from backend.globals.schemas import RuleV2
from backend.learner.learning import load_all_analyzed_tasks
from backend.assistant.prompts.search import CLASSIFY_QUERY_PROMPT, RANK_RULES_PROMPT
from backend.utils import get_project_root


def read_favorites() -> List[RuleV2]:
    try:
        favorites_path = get_project_root() / ".zoro" / "generated" / "favorites.json"
        if not favorites_path.exists():
            return []
        
        with open(favorites_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [RuleV2(**rule) for rule in data.get('favorites', [])]
    except Exception:
        return []


def llm_classify_query(query: str, model: str = 'gpt-5') -> str:
    provider = get_default_provider()
    
    prompt = CLASSIFY_QUERY_PROMPT.format(query=query)
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    data = json.loads(response)
    return data["task_type"]


def filter_rules_by_type(task_type: str, tags: List[str] = None) -> List[RuleV2]:
    favorites = read_favorites()
    
    tag = f"[{task_type}]"
    favorite_rules = [rule for rule in favorites if rule.rule.startswith(tag)]
    
    all_tasks = load_all_analyzed_tasks(tags=tags)
    all_rules = []
    for task in all_tasks:
        all_rules.extend(task.rules)
    
    tag_filtered_rules = [rule for rule in all_rules if rule.rule.startswith(tag)]
    
    seen_ids = {rule.rule_id for rule in favorite_rules}
    unique_tag_filtered = [rule for rule in tag_filtered_rules if rule.rule_id not in seen_ids]
    
    ordered_rules = favorite_rules + unique_tag_filtered
    
    return ordered_rules


def llm_rank_rules(query: str, rules: List[RuleV2], limit: int = 10, model: str = 'gpt-5') -> List[RuleV2]:
    if not rules:
        return []
    
    if len(rules) <= limit:
        return rules
    
    provider = get_default_provider()
    
    formatted_rules = "\n".join([
        f"{i+1}. {rule.rule}"
        for i, rule in enumerate(rules)
    ])
    
    prompt = RANK_RULES_PROMPT.format(
        query=query,
        rules=formatted_rules,
        limit=limit
    )
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    data = json.loads(response)
    rule_numbers = data["rule_numbers"]
    
    ranked_rules = []
    for num in rule_numbers:
        if 0 < num <= len(rules):
            ranked_rules.append(rules[num - 1])
    
    return ranked_rules


def search_by_type(query: str, limit: int = 10, model: str = 'gpt-5', tags: List[str] = None) -> Tuple[str, List[RuleV2]]:
    task_type = llm_classify_query(query, model)
    
    filtered_rules = filter_rules_by_type(task_type, tags=tags)
    
    ranked_rules = llm_rank_rules(query, filtered_rules, limit, model)
    
    return task_type, ranked_rules
