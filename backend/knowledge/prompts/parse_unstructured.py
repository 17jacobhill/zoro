PARSE_UNSTRUCTURED_PROMPT = """
You are parsing a knowledge base document into structured items.

Input markdown content:
{content}

Your task: Extract rules from this content, handling various markdown formats flexibly.

## Parsing Strategy

**Be flexible with formats:**
- Look for explicit "## Category:" markers OR infer from section headings
- Look for "Rule:", "Context:", "Evidence:" labels OR extract from natural text
- Handle both structured format AND free-form markdown
- Extract from bullet points, paragraphs, or any format

## Output Fields (ALL REQUIRED)

For each rule or doc section, extract:

1. **type**: "rule" (prescriptive guidance) or "doc" (general knowledge/architecture)
2. **category**: Extract from "## Category:" OR infer from content (workflow, ui-ux, architecture, code-style, meta, data-model, testing, etc.)
3. **title**: Create a short descriptive title (5-8 words)
4. **content**: The actual rule text or documentation - preserve fully, don't summarize
5. **context**: What was being built when this emerged (or null if not rule/not available)
6. **evidence**: Supporting quotes or examples (or null if not available)
7. **confidence**: Float 0.0-1.0
   - Extract from "Confidence: 0.85" markers if present
   - **DEFAULT to 0.5 if not present** (NEVER null)
8. **decay**: Float 0.0-1.0  
   - Extract from "Decay: 0.75" markers if present
   - **DEFAULT to 0.5 if not present** (NEVER null)
9. **confidence_reasoning**: Explanation of confidence (or null)
10. **decay_reasoning**: Explanation of decay (or null)

## Important Rules

- Preserve ALL original content - don't truncate or summarize
- If confidence/decay are missing, use **0.5** (not null!)
- Extract numeric values only (0.85, not "85%" or "high")
- Count sections carefully to match expected count
- Be creative in extracting from unstructured text

## Examples

**Structured format:**
```
## Category: code-style
Rule: Always use TypeScript strict mode
Context: Building frontend components
Evidence: "Caught 15 type errors early"
Confidence: 0.9 (90%)
Decay: 0.6 (Specific to TypeScript projects)
```

**Unstructured format:**
```
# Code Standards
- Use TypeScript strict mode everywhere
- This caught lots of bugs in the auth module
```
→ Extract as: category="code-style", content="Use TypeScript strict mode everywhere", context="auth module", confidence=0.5, decay=0.5

CRITICAL: You must return exactly {expected_count} items. Pre-count: {expected_count}

Return JSON array of objects with this structure:
{{
  "items": [
    {{
      "type": "rule" | "doc",
      "category": string,
      "title": string,
      "content": string,
      "context": string | null,
      "evidence": string | null,
      "confidence": float | null,
      "decay": float | null,
      "confidence_reasoning": string | null,
      "decay_reasoning": string | null
    }}
  ]
}}
"""