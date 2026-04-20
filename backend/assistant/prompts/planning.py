TASK_SELECTION_PROMPT = """Given this task query: {query}

Here are all available past tasks (ID: description):
{task_descriptions}

Return the task IDs that are most similar or relevant to this query. Make sure there is a real connection.

Return JSON format:
{{
  "task_ids": ["id1", "id2", "id3"]
}}"""


INITIAL_PLAN_PROMPT = """User wants to: {query}

Generate a lightweight 2-node plan skeleton:
1. checking-with-user - Iteratively clarify requirements with user
2. planning - Analyze codebase globally and design implementation strategy

Do NOT analyze good/bad trajectories yet. Do NOT generate code-style steps yet.
Just create the structural skeleton for the workflow.

Return JSON matching this exact structure:
{{
  "task_query": "{query}",
  "reasoning": "Initial 2-node workflow: clarify requirements first, then analyze codebase and design strategy",
  "steps": [
    {{
      "step_number": 1,
      "task_type": "checking-with-user",
      "objective": "Confirm and clarify all requirements for: {query}",
      "rules": [],
      "failure_point_watch": "Assuming requirements without explicit user confirmation; missing edge cases or constraints",
      "substeps": [],
      "before_starting": "Run: zoro update-step step-1 in_progress",
      "after_completing": "After completing: 1) Save output: zoro set-output step-1 '<json of requirements_checklist + user_story>'; 2) Add notes: zoro add-note step-1 'final requirements checklist'; 3) Complete: zoro complete-step step-1 --rules-used 'rule-ids'; 4) Re-read plan: read_file .rules/zoro_plan.md\\n\\n**⏸️ PAUSE HERE**\\n- Present results to user with attempt_completion\\n- Wait for explicit approval before proceeding to next step\\n- Do NOT automatically continue to the next step"
    }},
    {{
      "step_number": 2,
      "task_type": "planning",
      "objective": "Analyze codebase globally, design implementation strategy, and generate code-style steps for: {query}",
      "rules": [],
      "failure_point_watch": "Skipping codebase analysis; proposing strategy without user approval; generating code-style steps before approval",
      "substeps": [],
      "before_starting": "Review step-1 for context/outputs; Run: zoro update-step step-2 in_progress",
      "after_completing": "After completing: 1) Save output: zoro set-output step-2 '<strategy>'; 2) Add notes: zoro add-note step-2 'strategy and generated steps'; 3) Complete: zoro complete-step step-2 --rules-used 'rule-ids'; 4) Re-read plan: read_file .rules/zoro_plan.md\\n\\n**⏸️ PAUSE HERE**\\n- Present results to user with attempt_completion\\n- Wait for explicit approval before proceeding to next step\\n- Do NOT automatically continue to the next step"
    }}
  ]
}}

Note: Rules will be filled per-step later via rule selection.
"""


PLANNING_EXECUTION_PROMPT = """You are executing a 'planning' node to design the implementation strategy.

Requirements (from checking-with-user step):
{requirements}

Past similar tasks analysis:

GOOD TRAJECTORIES:
{good_tasks}

BAD TRAJECTORIES:
{bad_tasks}

Your job: Perform global codebase analysis and design implementation strategy.

Process:
1. List files that need to be read/modified
2. Read and analyze those files  
3. Understand dependencies and relationships
4. Design high-level implementation approach
5. Break down approach into 3-5 code-style steps (each with 2-4 substeps)
6. Present strategy to user for approval

Strategy output format:
{{
  "files_analyzed": ["file1.py", "file2.tsx"],
  "dependencies_identified": ["dep1", "dep2"],
  "implementation_strategy": "High-level description of approach",
  "code_style_steps": [
    {{
      "step_number": 3,
      "objective": "Update backend schema",
      "substeps": [
        "Add new field to User model",
        "Create migration file"
      ]
    }},
    {{
      "step_number": 4,
      "objective": "Implement API endpoint",
      "substeps": [
        "Add /api/validate route",
        "Wire validation logic",
        "Add error handling"
      ]
    }}
  ]
}}

After user approves strategy:
- Automatically run: zoro plan-iter "implement strategy" --from-step 3
- This will generate the code-style nodes in the plan
- Mark planning step as complete
"""


PLAN_STRUCTURE_PROMPT = """User wants to: {query}

Past similar tasks:

GOOD TRAJECTORIES:
{good_tasks}

BAD TRAJECTORIES:
{bad_tasks}

Analyze patterns and generate a near-future execution plan with modular steps. Each step cannot have more than 100 words.
They must have coherent sentences, be concise but specific, and be clear and easily comprehendable and readable as a standalone rule.
Do not strive for a perfect end to end product. Just strive for a plan with 2-4 for the near feature (aka you can omit testing, user studies, etc.). DO NOT BE OVEREAGER.
Most likely, step 2 will depend on step 1, and step 3 will depend on step 2. It needs to be flexible and indicate the knowledge gaps that exist. 
Clearly denote which steps are subjet to change. You should definitely have steps where it is purely commanding a CODE GENEERATION. 
Remember, the prompt can be very unspecified. You are just trying to create the best plan for the current trajectory that is 2-4 steps long, and then in the future, depending on the direction of the task we will create more steps. 
It is not a shot to the end.

Categorize what type of task the AI is doing for each step. It can only be one: [planning | code-style | testing | debugging | checking-with-user].
Checking with user - aligning intent with user to fully understand what they want. 
Planning - reflecting on what you know and what you don't know and figuring out the next steps for how to approach it. 
Code style - enforcing how the code should look or read, such as readability, naming conventions, documentation, consistency. 
Testing - verfiying correctness/robustness.
Debugging - identifying and fixing errors or broken logic.  


Return JSON matching this exact structure:
{{
  "task_query": "{query}",
  "good_trajectories": ["summary of good task 1", "summary of good task 2"],
  "bad_trajectories": ["summary of bad task 1", "summary of bad task 2"],
  "reasoning": "Overall pattern analysis of what works vs what fails",
  "steps": [
    {{
      "step_number": 1,
      "task_type": [planning | code-style | testing | debugging | checking-with-user],
      "objective": "Full, human-readable, sentence desription of what to do",
      "rules": [],
      "failure_point_watch": "Full, human-readable, What to watch out for",
      "substeps": [],
      "before_starting": "Instructions for before starting: check previous step dependencies, then run: zoro update-step step-1 in_progress",
      "after_completing": "After completing: 1) Add notes: zoro add-note step-1 'summary of what you learned'; 2) Complete: zoro complete-step step-1 --rules-used 'rule-ids'; 3) Re-read plan: read_file .rules/zoro_plan.md"
    }}
  ]
}}

Note: Leave rules empty - they will be filled per-step later.
For code-style steps ONLY, populate substeps with 3-5 incremental implementation steps (each implementing 1-2 features).
For other task types (planning, checking-with-user, testing, debugging), leave substeps as empty array [].

IMPORTANT: For each step, include workflow instructions:
- before_starting: What to check/verify before beginning + command to mark in-progress
- after_completing: Commands to run after finishing (add-note, complete-step with rule IDs, re-read plan)

For step 1: before_starting should be "Run: zoro update-step step-1 in_progress" (no dependencies)
For step N (N > 1): before_starting should reference previous step: "Review step-(N-1) for context/outputs; Run: zoro update-step step-N in_progress"

The after_completing instruction should ALWAYS be in this format:
"After completing: 1) Add notes: zoro add-note step-X 'what you learned'; 2) Complete: zoro complete-step step-X --rules-used 'rule-ids'; 3) Re-read plan: read_file .rules/zoro_plan.md" """


STEP_TASK_SELECTION_PROMPT = """Current step objective: {step_objective}

All available tasks (ID: description):
{task_descriptions}

Select task IDs with rules relevant to this step.

Return JSON format:
{{
  "task_ids": ["id1", "id2", "id3"]
}}"""


STEP_RULE_SELECTION_PROMPT = """Step objective: {step_objective}

Available rules from relevant tasks:
{rules}

Select MAXIMUM {limit} most relevant rules for this step. Only include relevant rules; if you cant fill it up to  {limit}, don't add it. 

Return JSON format:
{{
  "rule_ids": ["id1", "id2", "id3"]
}}"""
