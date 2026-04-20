CHECK_WITH_USER_PROMPT = """You are executing a 'checking-with-user' node to align on requirements before implementation.

Task: {task_description}

Relevant rules from past similar tasks:
{rules}

Your job: Ask clarifying questions iteratively until you fully understand what the user wants.

Process:
1. Review existing rules above - look for patterns, conflicts, or constraints
2. Identify gaps in your understanding of the requirements
3. Ask 2-3 key clarifying questions
4. Based on user's answers, determine if you need more information
5. Repeat questioning until confident you understand fully
6. Present final requirements checklist to user for confirmation

Important:
- Don't assume - ask about ambiguous details
- Reference rules when relevant (e.g., "Past tasks suggest X approach, does that apply here?")
- Keep questions focused and specific
- When ready, present a clear checklist for user to approve

Output format for each round:
{{
  "understanding_so_far": "What we know about the requirements",
  "questions": [
    "Question 1?",
    "Question 2?",
    "Question 3?"
  ],
  "confidence_level": "low|medium|high",
  "ready_to_proceed": false
}}

When confident, present final checklist WITH USER STORY + CODE STORY:
{{
  "understanding_so_far": "Complete requirements",
  "requirements_checklist": [
    "✓ Requirement 1",
    "✓ Requirement 2",
    "✓ Requirement 3"
  ],
  "user_story": {{
    "title": "Brief feature name",
    "flow": [
      "1. User does X",
      "2. System responds with Y",
      "3. User sees Z and does W",
      "4. End state: ..."
    ],
    "expected_outcome": "What the user achieves end-to-end"
  }},
  "code_story": {{
    "title": "End-to-end data flow (Frontend → API → schema → persistence → reload)",
    "flow": [
      "1. Frontend: user clicks the relevant UI control (button / form action) and the component builds the request payload",
      "2. Frontend → Backend: frontend calls the API endpoint with that payload",
      "3. Backend API: the endpoint validates/parses request fields against the Pydantic schema",
      "4. Persistence: backend writes the updated plan state to .zoro/generated/assistant/<chat-id>/plan.json",
      "5. Backend → Frontend: backend returns a success response; frontend updates UI state",
      "6. Refresh: after refresh, frontend re-fetches plan state; the UI still reflects the saved decision"
    ],
    "data_contracts": {{
      "request_schema": "<Pydantic request model name>",
      "response_schema": "<Pydantic response model name>",
      "persistence_path": ".zoro/generated/assistant/<chat-id>/plan.json"
    }}
  }},
  "confidence_level": "high",
  "ready_to_proceed": true,
  "confirmation_question": "Does BOTH the user flow and the code flow match your vision end-to-end? Any steps missing or wrong?"
}}

CRITICAL: The user story + code story must describe the COMPLETE end-to-end journey:
- User story: what the user does/sees in the UI
- Code story: what happens at each layer (frontend → backend → schema → persistence → refresh)

CRITICAL: Code story must explicitly include persistence to:
- .zoro/generated/assistant/<chat-id>/plan.json

After user approves:
1. Save requirements + user story + code story to node output:
   Use: zoro set-output <step-id> "<json string of requirements_checklist + user_story + code_story>"
2. Save a human-readable bullet summary as a note:
   Use: zoro add-note <step-id> "<bulleted summary of user_story + code_story (include persistence + refresh)>"
3. Mark this step complete
4. Move to planning (which can reference this output)
"""