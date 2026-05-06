POPULATE_RULES_PROMPT = """You are refining a plan by attaching rules and creating substeps only when needed.

CRITICAL CONSTRAINTS:
- Max 5 substeps per parent step.
- At most 3 rules may live on the parent step; push the rest to the most relevant substep.
- General rules (apply to all child actions) go on the parent step.
- Specific rules (apply to one action) go on that substep.
- Substeps inherit parent rules automatically.
- Treat each rule's `Context` as a scope boundary:
  - If context clearly matches the plan item, the rule is eligible.
  - If context clearly does not match, do not attach the rule.
  - If context is empty or generic, treat the rule as broadly applicable.
- Do not decompose unless necessary. If a step is already concrete and actionable, keep it as-is.
- Too much structure is not inherently better; prefer the simplest actionable structure.
- If a rule says "manually test", the substep must say "pause and ask user to verify".
- Preserve original numbering (for example, "Step 1" -> "Step 1.1, 1.2").
- Rules marked `**Favorite:** true` are mandatory and must appear at least once.
- Do not place every favorite on every step; place each favorite where most relevant.
- Conflict precedence: favorite beats non-favorite even at lower confidence.
- Use confidence only as a tiebreaker when favorite status is equal.

PLAN STRUCTURE:
{plan_json}

AVAILABLE RULES (with full context):
{rules_content}

Your task:
1. Analyze each parent step and identify relevant rules.
2. Use context-aware scope matching before assigning rules.
3. Assign parent-level general rules (max 3).
4. Create substeps only when distinct rule-driven actions are needed (max 5).
5. Assign substep-level specific rules.
6. Preserve original plan detail and intent.

OUTPUT FORMAT:
Return the COMPLETE enhanced plan structure as JSON matching the original plan schema:

{{
  "plan": {{
    "title": "...",
    "items": [
      {{
        "id": "step-1",
        "number": "1",
        "title": "Parent step title",
        "description": "Optional description",
        "children": [
          {{
            "id": "step-1-1",
            "number": "1.1",
            "title": "Atomic substep title",
            "description": "What to do",
            "children": [],
            "rules": [
              {{
                "category": "code-style",
                "text": "Rule text",
                "context": "Context if available",
                "evidence": "Evidence if available",
                "confidence": 0.9,
                "decay": 0.6,
                "kb_item_id": "preserve the 'KB Item ID' from the input rule if present",
                "reasoning": "Detailed explanation of why this rule matches this specific substep. Reference the substep's objective and how the rule's context relates to it.",
                "context_match": 0.95,
                "relevance_score": 0.92
              }}
            ]
          }}
        ],
        "rules": []
      }}
    ]
  }},
  "rules_retrieved": true
}}

Return ONLY the JSON object, no additional text."""

REFINE_SUBSTEPS_PROMPT = """You are refining a Step by regenerating its substeps based on user guidance.

USER GUIDANCE: "{user_guidance}"

CURRENT PHASE:
{phase_json}

AVAILABLE KB RULES:
{kb_rules}

CRITICAL CONSTRAINTS:
- Create 2-5 substeps (minimum 2, maximum 5).
- Each substep must be one concrete, atomic action.
- Only create substeps required by user guidance (explicit or implicit).
- Assign general rules to Step level (max 3, only if they apply to all substeps).
- Assign specific rules to the relevant substep (prefer this).
- Substeps inherit Step-level rules automatically; avoid duplication.
- Place each rule at the most general level where it still applies.
- Treat each rule's `Context` as scope:
  - If context clearly matches the step, the rule is eligible.
  - If context clearly does not match, do not attach it.
  - If context is empty/generic, it may apply broadly.
- Rules marked `**Favorite:** true` are mandatory and must appear at least once across step + substeps.
- Do not place every favorite on every step.
- Conflict precedence: favorite beats non-favorite; confidence only breaks ties with equal favorite status.

Your task:
1. Select 3-7 most relevant KB rules plus all favorited rules.
2. Resolve conflicts with favorite-first logic.
3. Regenerate substeps to match guidance.
4. Assign rules at step/substep level based on scope.

RULE PROVENANCE REQUIREMENTS:
Each rule must include:
- kb_item_id: Preserve from input KB rule
- confidence: 0.0-1.0 score
- decay: 0.0-1.0 score (specificity)
- confidence_reasoning: Why this confidence score
- decay_reasoning: Why this decay/specificity score
- reasoning: Why this rule applies to this specific step

OUTPUT: Return ONLY valid JSON (no markdown code fences, no extra text) matching this structure:

{{{{
  "rules": [
    {{{{
      "category": "category-name",
      "text": "Rule text",
      "context": "Context from KB",
      "evidence": "Evidence from KB",
      "confidence": 0.9,
      "decay": 0.5,
      "confidence_reasoning": "Why this confidence",
      "decay_reasoning": "Why this specificity",
      "kb_item_id": "kb-item-uuid",
      "reasoning": "Why this rule applies to the Phase"
    }}}}
  ],
  "children": [
    {{{{
      "id": "step-X-1",
      "number": "X.1",
      "title": "Step title (action-oriented)",
      "description": "What to do in this step",
      "rules": [
        {{{{
          "category": "category-name",
          "text": "Rule text",
          "context": "Context from KB",
          "evidence": "Evidence from KB",
          "confidence": 0.85,
          "decay": 0.7,
          "confidence_reasoning": "Why this confidence",
          "decay_reasoning": "Why this specificity",
          "kb_item_id": "kb-item-uuid",
          "reasoning": "Why this rule applies specifically to THIS step"
        }}}}
      ],
      "children": []
    }}}}
  ]
}}}}

IMPORTANT: Return pure JSON only. No markdown fences, no explanations, just the JSON object."""

PLAN_EXTRACTION_PROMPT = """You are analyzing a chat conversation between a user and a coding agent (an AI assistant).

Task: Extract the plan the coding agent created with high fidelity.

CRITICAL:
- Extract FLAT plans only (1 level, no hierarchy).
- Keep actionable sections only (Backend, Frontend, Testing, etc.).
- Skip conceptual/organizational headers (Architecture, Overview, Implementation Details, Complete Plan, etc.).
- Preserve all actionable content in each step description, including code blocks and examples.
- If numbering is missing or unclear, infer a logical flat sequence.
- If no actionable plan exists, return an empty `items` array.

For each step, capture:
- Number (for example: "1", "2", "Step 3")
- Title (section heading or first clear action phrase)
- Description (all remaining actionable content from that section)

Output ONLY valid JSON in this format:

```json
{{
  "plan": {{
    "title": "Optional plan title",
    "items": [
      {{
        "id": "step-1",
        "number": "1",
        "title": "Step title",
        "description": "Optional detailed description",
        "children": []
      }}
    ]
  }}
}}
```

Chat content to analyze:

{content}

Extract the plan as JSON:"""
