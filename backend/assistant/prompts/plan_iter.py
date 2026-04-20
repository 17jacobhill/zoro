REWRITE_STEP_PROMPT = """You are updating a plan step based on new requirements.

Original step description:
{original_description}

User wants to change:
{user_query}

Rewrite the step description to incorporate the requested changes. Keep the same level of detail and structure, just update the relevant parts.

Return only the new description, nothing else."""


REWRITE_SUBSTEPS_PROMPT = """You are updating substeps for a plan step based on new requirements.

Original substeps:
{substeps_text}

The main step description was updated to:
{new_description}

User's change request:
{user_query}

Rewrite each substep text to align with the new description. Preserve the same number of substeps and their IDs. Only update the text field to match the new requirements.

Return ONLY a JSON array with this exact structure:
[
  {{"id": "substep-1", "text": "updated text 1", "completed": false}},
  {{"id": "substep-2", "text": "updated text 2", "completed": false}},
  ...
]

Return valid JSON only, no markdown formatting."""


CREATE_SUBSTEPS_PROMPT = """You are creating substeps for a plan step.

Step type: code-style

Main step description:
{description}

Create 3-5 incremental substeps. Each substep should implement 1-2 small features (not everything at once).
Keep the text actionable and specific.

Return ONLY a JSON array with this exact structure:
[
  {"id": "substep-1", "text": "...", "completed": false},
  {"id": "substep-2", "text": "...", "completed": false}
]

Return valid JSON only, no markdown formatting."""


GENERATE_CODE_STYLE_STEPS_PROMPT = """You are generating code-style implementation steps based on an approved planning strategy.

User's original request: {query}

Implementation strategy (from planning node):
{strategy}

Past similar tasks analysis:

GOOD TRAJECTORIES:
{good_tasks}

BAD TRAJECTORIES:
{bad_tasks}

Generate 3-5 code-style steps starting from step {start_step_number}. Each step should:
- Have a clear, focused objective (max 100 words)
- Include 2-4 substeps that implement 1-2 features each
- Be subject to change if user feedback requires adjustments
- Follow patterns from good trajectories and avoid patterns from bad trajectories

Return JSON matching this exact structure:
{{
  "task_query": "{query}",
  "good_trajectories": ["summary of good task 1", "summary of good task 2"],
  "bad_trajectories": ["summary of bad task 1", "summary of bad task 2"],
  "reasoning": "Overall pattern analysis of what works vs what fails for this implementation",
  "steps": [
    {{
      "step_number": {start_step_number},
      "task_type": "code-style",
      "objective": "Clear, specific description of what to implement in this step",
      "rules": [],
      "failure_point_watch": "What to watch out for in this step",
      "substeps": [
        "Substep 1 description",
        "Substep 2 description",
        "Substep 3 description"
      ],
      "before_starting": "Review step-{prev_step} for context/outputs; Run: zoro update-step step-{start_step_number} in_progress",
      "after_completing": "After completing: 1) Add notes: zoro add-note step-{start_step_number} 'what you learned'; 2) Complete: zoro complete-step step-{start_step_number} --rules-used 'rule-ids'; 3) Re-read plan: read_file .rules/zoro_plan.md\\n\\n**⏸️ PAUSE HERE**\\n- Present results to user with attempt_completion\\n- Wait for explicit approval before proceeding to next step\\n- Do NOT automatically continue to the next step"
    }}
  ]
}}

Note: 
- Leave rules empty - they will be filled per-step later
- Substeps should be plain strings, not objects (conversion happens later)
- Each step should be independently completable
- Mark steps as "Subject to change" in objective if uncertain
"""
