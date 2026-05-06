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
   - If missing or ambiguous, return null
8. **decay**: Float 0.0-1.0  
   - Extract from "Decay: 0.75" markers if present
   - If missing or ambiguous, return null
9. **confidence_reasoning**: Explanation of confidence (or null)
10. **decay_reasoning**: Explanation of decay (or null)
11. **source_quote**: Minimal source excerpt grounding this item (1-3 lines, no fluff, or null)
12. **source_start_line**: 1-based start line number in the provided content (or null if unknown)
13. **source_end_line**: 1-based end line number in the provided content (or null if unknown)

## Important Rules

- Preserve ALL original content - don't truncate or summarize
- If confidence/decay are missing, return null
- Extract numeric values only (0.85, not "85%" or "high")
- Prefer precise extraction, not forced count-matching
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
→ Extract as: category="code-style", content="Use TypeScript strict mode everywhere", context="auth module", confidence=null, decay=null

Document was pre-split into {expected_count} section(s). Treat this as guidance, not a hard constraint.
Return every meaningful rule/doc item you can extract from the provided content.

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
      "decay_reasoning": string | null,
      "source_quote": string | null,
      "source_start_line": integer | null,
      "source_end_line": integer | null
    }}
  ]
}}
"""
