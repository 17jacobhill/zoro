REFINE_MANUAL_RULE_PROMPT = """You refine knowledge-base rules for readability and practical use.

Input rule:
- type: {rule_type}
- category: {category}
- title: {title}
- content: {content}
- context: {context}
- evidence: {evidence}

Goal:
- Keep intent and required constraints intact.
- Make wording concise, direct, and human-readable.
- Avoid verbose filler, repetition, and long winding sentences.
- Refine additively: preserve original rule substance and add clarifications; do not replace with a completely new rule.

Refinement rules:
1. Title: 4-8 words, plain language, action-oriented when possible.
2. Content:
   - Keep all critical requirements and guardrails from the original.
   - Use short, concrete sentences.
   - Remove fluff and redundant phrasing.
   - If multiple checks exist, use compact bullets or compact sentence structure.
3. Context/evidence:
   - Keep useful specifics.
   - Tighten wording.
   - Leave null only when truly unavailable.
4. Confidence (0-1): certainty this rule is valid and broadly useful.
5. Decay (0-1): how quickly the rule may become stale (higher = more task-specific/temporary).
6. confidence_reasoning and decay_reasoning:
   - 1-2 short sentences each.
   - Concrete and non-generic.

Output JSON only with fields:
- title
- content
- confidence
- decay
- confidence_reasoning
- decay_reasoning
- context
- evidence

Return ONLY JSON. No markdown. No prose outside JSON.
"""
