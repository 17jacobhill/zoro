PARSE_REPO_INSTRUCTIONS_PROMPT = """
You are converting a repository instruction file (for example AGENTS.md, CLAUDE.md, or CODEX.md)
into a structured rule library.

Input markdown content:
{content}

Your task: extract as many distinct, reusable items as are genuinely present in the file.

## Extraction Rules

- Split separate requirements into separate items when an agent could follow them independently.
- Preserve exact file paths, command names, flags, and protocol details when they matter.
- Use `type = "rule"` for prescriptive guidance and `type = "doc"` for explanatory background/context.
- Merge obvious duplicates within the same file instead of repeating them.
- Prefer short, scannable titles (5-8 words).
- Preserve the full directive text in `content`; do not summarize away important details.

## What to Extract

Look for:
- workflow requirements,
- setup requirements,
- files that must be read first,
- command-order requirements,
- proof / verification requirements,
- compatibility requirements,
- configuration constraints,
- non-negotiable coding or review rules.

## Output Fields

For each extracted item, return:

1. `type`: "rule" or "doc"
2. `category`: inferred practical category (workflow, setup, verification, tooling, ui, backend, testing, meta, etc.)
3. `title`: short descriptive title
4. `content`: the actual instruction text
5. `context`: optional contextual note
6. `evidence`: optional supporting quote/example
7. `confidence`: float 0.0-1.0 (return null if unclear)
8. `decay`: float 0.0-1.0 (return null if unclear)
9. `confidence_reasoning`: optional explanation
10. `decay_reasoning`: optional explanation
11. `source_quote`: concise source excerpt from the file (1-3 lines, or null)
12. `source_start_line`: 1-based line number where this starts (or null)
13. `source_end_line`: 1-based line number where this ends (or null)

Return ONLY valid JSON in this format:
{{
  "items": [
    {{
      "type": "rule" | "doc",
      "category": "workflow",
      "title": "Short title",
      "content": "Full instruction text",
      "context": null,
      "evidence": null,
      "confidence": null,
      "decay": null,
      "confidence_reasoning": null,
      "decay_reasoning": null,
      "source_quote": null,
      "source_start_line": null,
      "source_end_line": null
    }}
  ]
}}
"""
