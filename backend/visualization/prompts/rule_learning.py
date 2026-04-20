RULE_LEARNING_PROMPT = """You are extracting reusable rules from an INCREMENTAL chat window.

You are given:
1) only the newly-unread token window (not full history),
2) existing rules already in the knowledge base.

Goal:
- produce concise, human-readable rules the user would actually keep,
- prioritize USER-stated preferences and corrections,
- avoid duplicates/near-duplicates of existing rules.

## Priority and weighting
- Highest priority: explicit user instructions/preferences/corrections.
- Medium priority: repeated user complaints or approvals.
- Lowest priority: assistant-only wording unless it directly reflects user intent.

## Scope
- Focus on stable workflow/style/process rules.
- Avoid one-off implementation details.
- If window has no strong new rule signal, return an empty rules array.

## Dedup with existing rules
- If a candidate already exists (same meaning), do NOT emit it again.
- If meaning is similar but wording can be clearer, only emit if clearly additive.

## Writing quality (strict)
- `text` must be short and plain English (target <= 18 words).
- `text` should read like a directive a human can scan quickly.
- `evidence` must be brief (1-2 short sentences, no long essay).
- Keep categories practical and consistent.

## Scoring guidelines
Confidence (0-1):
- 0.9-1.0 explicit user direction in this window
- 0.7-0.8 repeated user signal
- 0.5-0.6 inferred but plausible
- <=0.4 weak signal (generally avoid emitting)

Decay (0-1):
- lower = broader/general convention
- higher = narrow/task-specific preference

## Existing rules snapshot
{existing_rules}

## Incremental window metadata
- analyzed_from_token: {analyzed_from_token}
- analyzed_to_token: {analyzed_to_token}

Output ONLY valid JSON in this exact format:
```json
{{{{
  "rules": [
    {{{{
      "category": "your-determined-category",
      "text": "Clear description of the rule",
      "context": "What they were building",
      "evidence": "Evidence from chat",
      "confidence": 0.85,
      "confidence_reasoning": "User explicitly stated this 4 times across different contexts",
      "decay": 0.3,
      "decay_reasoning": "This is a language-level best practice, applies broadly"
    }}}}
  ],
  "token_count": <number of tokens analyzed>
}}}}
```

Here is the chat content to analyze:

{content}

Extract rules from this incremental window as JSON:"""
