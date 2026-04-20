BATCH_DUPLICATE_DETECTION_PROMPT = """Analyze these rules from category "{category}" to find duplicates AND conflicts.

## DUPLICATE: Similar rules that should be merged
- Same intent, similar wording
- When merging: new_confidence = avg(confidences) * 1.15 (boost for agreement)
- When merging: new_decay = avg(decay) * 0.85 (becomes more general)

## CONFLICT: Similar context but contradictory rules
- Same topic but opposite actions
- When conflicting: 
  * merged_confidence = avg(confidences) - 0.2 (minimum 0.1)
  * merged_decay = avg(decays) + 0.2 (maximum 1.0)
- Flag as conflict for user review

## RULE FORMAT GUIDELINES

When generating merged rules, follow these quality standards:

Good Rules (Generalizable):
- "User has specific /frontend and /backend directories, uses MUI and Flask"
- "User prefers to scope out edge cases before implementing features"
- "Keep testing APIs at the end of files"

Bad Rules (Too Specific - Avoid):
- "Keep /set_globals_for_uuid at bottom of server.py" → Too file-specific
- "Use one-way linking from tasks to notes" → Feature-specific
- "Surface matrix edits per cell with approve/reject" → Product feature

When merging duplicates, ensure the merged_content follows the "Good Rules" pattern:
generalizable, clear, and not tied to specific implementation details.

For each group of duplicates/conflicts:
1. Identify item_ids involved
2. Calculate similarity_score (0-1)
3. Determine if DUPLICATE or CONFLICT
4. If DUPLICATE: provide merged content + adjusted scores
5. If CONFLICT: flag as conflict, increase decay

CRITICAL: Each item can appear in AT MOST ONE group. Do not create overlapping groups.

Items to analyze:
{items_list}

Output JSON in this exact format:
{{{{
  "groups": [
    {{{{
      "item_ids": ["id1", "id2"],
      "similarity_score": 0.9,
      "is_conflict": false,
      "reasoning": "Both rules about same pattern",
      "merged_title": "Combined title",
      "merged_content": "Merged rule text",
      "merged_context": "Combined context or null",
      "merged_evidence": "Combined evidence or null",
      "merged_confidence": 0.88,
      "merged_decay": 0.42,
      "scoring_explanation": "For duplicates: Confidence boosted by agreement (avg * 1.15), decay lowered as more general (avg * 0.85). For conflicts: Confidence reduced due to contradiction (avg - 0.2), decay increased as context-dependent (avg + 0.2)"
    }}}}
  ]
}}}}

Detect duplicates and conflicts. And return both.

"""