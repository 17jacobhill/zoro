CLASSIFY_QUERY_PROMPT = """Query: {query}

Classify this query into ONE of these task types:
- debugging: fixing errors, bugs, or broken functionality
- testing: verifying correctness, writing tests, checking behavior
- planning: designing approach, architecting solution, organizing work
- code-style: formatting, naming conventions, readability, documentation
- checking-with-user: confirming requirements, aligning on approach, getting approval

Return JSON format:
{{
  "task_type": "debugging"
}}"""


RANK_RULES_PROMPT = """Query: {query}

Available rules:
{rules}

Select the {limit} most relevant rule numbers for this specific query.
Only select rules that directly help with: {query}

Return JSON format:
{{
  "rule_numbers": [1, 2, 3]
}}"""
