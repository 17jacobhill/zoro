
LEARNING_PROMPT_v3 = """You are a helpful assistant tasked with analyzing concrete user thought process based on transcribed activity.
# Analysis

I'm going to give you a series of messages {user_name} sent during a chat task chain, along with a chronological description of what happened.
You are to produce a structured and insightful analysis that is generalizable to how {user_name} works and not overfit to the task at hand. 
Do not give a literal summary — you are trying to understand {user_name}'s thinking and behavior. 

------
For each task, follow this structure: 

## Task: 
Categorize what it falls into [planning | code-style | testing | debugging | checking-with-user], can be more than one. and also a Short description of the user's goal

## User Messages [Line range]: User Message X to User Message Y
Good Example: user message 1 "i want to build x" to user message 4 "sure, build it now"

## Description (PROVIDED):
{task_description}
Good Examples:
"Jenny started by framing the initial problem, and followed up with AI to clarify details like LLM model, UI/UX, data linking, etc. As AI started building, she clarified more things she didn’t like (such as what port to use, what model, packages)." - Describes what happened in very easy to understand language that is accurate.
Bad Examples:
"Started with vision, clarified storage and AI, simplified schemas, chose one-way task\u2192note links, CRA, port 5000, approved Blueprints, disliked docstrings." - Is way too concise, hard to interpret out of context.

## Type
Detect whether this was an optimal interaction trajectory between {user_name} and the chatbot, or whether or not the interaction had friction and was prolonged more than it should have been. 
If it was a good, interaction, return "good", otherwise, return "bad". CASE SENSITIVE.

## Reasoning
In one sentence, describe why it was good, and why it was bad. 

## Problem
If bad, explain in one sentence the ROOT CAUSE of the issue. Otherwise, return an empty string. 
Good Example:
"AI was overeager and started building out details before Jenny solidified details, causing her to go backwards constantly to fix what AI was building." - Isolates the core problem well.

## Failure Point
In one sentence, describe at what point in the interaction did the workflow trajectory go awry, and how you would spot it next time.
If the type was "good", then return an empty string.

## Guardrail
In one sentence, describe how you would bring the interaction back on course next time the the failure point is hit. 
Good Example:
"Get the exact user flow/narrative straight, because that's how {user_name} thinks, before designing the UI and implementation plan."
Bad Example:
"First align on additive scope and storage/versioning plan, then present minimal, inline, approval-ready change proposals and confirm they append to existing specs/steps before any build actions." - this is too use-case specific and also doesn't explain things well, the jargon sucks.
"Confirm preferred file organization and testing hooks upfront, then propose minimal diffs that preserve those anchors and validate curl-based testing before changes." This is super convoluted phrasing, and uses weird phrasing that is hard to understand.
"Before building, confirm storage location, model choice, linking direction, planner views, frontend tooling, port, and code style, then propose the smallest workable schema and UI flow for approval." - this is almost good, but could be better by stating "Get approval for every package used, UI design, schema, port and flesh it out fully before implemntation".
If the type was "good", then return an empty string. 

## Rules: 
List at most 5 explicit or implicit rules {user_name} had that denotes their style in planning, code style, testing, debugging, or how the AI and when the AI shoudl check in with the user. 
THE RULES CANNOT BE OVERLAPPING. BE CONSERVATIVE ABOUT THE RULES THAT YOU CREATE. IT NEEDS TO BE WELL-WRITTEN AND EASY TO UNDERSTAND.
Make sure that they are not overfit to the problem at hand and can be generalized to other problems. Do not include any specific business logic to the particular task that the user was doing - aim for generalizable rules.
Each rule must be split into a specific categories: [planning], [code-style], [testing], [debugging], [checking-with-user]
Planning - how should AI defining what to build and how to approach it based on how the user operates?
Code style - how does {user_name} enforce how the code should look or read, such as readability, naming conventions, documentation, consistency?
Testing - how does the user prefer to test their code (aka their specific flow)?
Debugging - how can AI be better at identifying and fixing errors or broken logic.
Checking with user - when is best to align with {user_name}'s intent before acting?

Good Examples:
"[code-style] Jenny has specific /frontend and /backend directories, and uses MUI and flask." - targeted in package and structure. 
"[planning] Jenny prefers to scope out edge cases, like rate limit issues, before implementing the API" - clearly targeting one rule. 
"[planning] Jenny does not like convoluted solutions but prefers simple, modular solutions that build on the existing structure" - clear targeting one thing.
Bad Examples:
"Make core behaviors automatic rather than optional flags; defaults should enforce desired workflows" - This is very nonsensical out of context.
"Keep data models minimal and flexible; rely on tags over rigid categories and avoid premature fields like status, priority, or recurrence." - The first sentence is good, the second sentence is way too specific and it is not a complete sentence.
"Use one-way linking from planner tasks to notes; let notes remain free-floating." - This rule is way too speciifc to the task at hand.
"Standardize backend conventions: Flask with Blueprints for modular routing, running on port 5000." - This should be split into two rules - together, it is hard to read. 
"Surface matrix edits per cell with approve/reject; avoid side\u2011by\u2011side diffs." - This is too specific to the product at hand and fundamentally the rule is not generalizable.
"Keep the /set_globals_for_uuid endpoint at the very bottom of backend/server.py, directly above the if __name__ == \"__main__\": block." -  A better rule is "Keep testing APIs at the end of the file.", because it is much more generalizable.
"Use a hybrid approach for inspiration categories: start fixed but allow new categories to emerge." - this is feature specific to the product we are building.
"Allow creating notes from within a specific day in the planner while keeping the notes centralized." - this is feature especific.

THERE CAN ONLY BE MAXIMUM 5 RULES PER TASK. SO CHOOSE WISELY.

Evaluation Criteria
For each task data you generate, evaluate its strength using two scales:
1. Confidence Scale
Rate your confidence based on how clearly the evidence supports your claim. Consider:
- **Direct Evidence**: Is there direct feedback about a certain response?
- **Relevance**: Is the evidence clearly tied to the learning rule that you propose?
- **Engagement Level**: Was the interaction meaningful or sustained?
Score: **1 (weak support)** to **10 (explicit, strong support)**. High scores require specific named references.
2. Decay Scale
Rate how long the learning is likely to stay relevant. Consider:
- **Urgency**: Does the task or interest have clear time pressure?
- **Durability**: Will this matter 24 hours later or more?
Score: **1 (short-lived)** to **10 (long-lasting insight or pattern)**.
Be conservative in your confidence estimates. Just because something appears as a response by the AI assistant in the chat does not mean they have deeply engaged with it. They may have only glanced at it for a second, making it difficult to draw strong conclusions.
Assign high confidence scores (e.g., 8-10) only when the transcriptions provide explicit, direct evidence that {user_name} is actively engaging with the content in a meaningful way.
Generate learning rules across the scale to get a wide range of inferences about {user_name}. 

--

When generating text:
1. Make sure that text does not just give the "answer" to the prolem we want to solve, is not overfit to the transcript at hand, and instead conducts a deep user analysis.
2. Make sure that all the analysis is generalizable to another problem. 
3. Make sure that the the wording is concise and human-readable and can stand alone if I were to read it out of context. 
4. At the end, I want the analysis to feel like you truly understood how I think.


-------

# Input
Below is the raw chat logs that {user_name} had with an AI assitant:

##  Chat Transcriptions
{inputs}

# Task

Return your results in this exact JSON format (NOTE: description is provided above, do NOT generate it):
{{
 "task": "[planning | code-style | testing | debugging | checking-with-user][Insert brief description of what user was trying to do. 10 WORDS. USER READABLE.]",
 "messages": ["user message 1 content", "user message 3 content", ... ],
 "type": "good" or "bad",
 "reasoning": "[One sentence concise analysis of how {user_name} thinks about tasks grounded in the workflow_trajectory and in the evidence]",
 "problem": "[Determine if there is a problem. If there is, then describe in one sentence the core issue, otherwise return an empty string.]",
 "failure_point": "[If there is a problem, provide a one sentence description of the root cause. Otherwise return an empty string]",
 "guardrail": "[If there is a problem, provide a one sentence concise description of how AI should guide {user_name} next time they were to do this task better knowing how the user works. Otherwise return an empty string]",
 "rules": [
   {{
     "rule": "[planning | code-style | testing | debugging | checking-with-user][Insert your 1-2-sentence description of the rule here/]",
     "reasoning": "[Provide EXTREMLEY detailed evidence AND DESCRIPTIVE examples from specific parts of the transcriptions to clearly justify this rule. Refer explicitly to named entities where applicable.]",
     "confidence": "[Confidence score (1–10)]",
     "decay": "[Decay score (1–10)]"
   }},
   ...
 ]
}}"""

LEARNING_PROMPT_v3_NO_EVIDENCE = """You are a helpful assistant tasked with analyzing concrete user thought process based on transcribed activity.
# Analysis

I'm going to give you a series of messages {user_name} sent during a chat task chain, along with a chronological description of what happened.
You are to produce a structured and insightful analysis that is generalizable to how {user_name} works and not overfit to the task at hand. 
Do not give a literal summary — you are trying to understand {user_name}'s thinking and behavior. 

------
For each task, follow this structure: 

## Task: 
Categorize what it falls into [planning | code-style | testing | debugging | checking-with-user], can be more than one. and also a Short description of the user's goal

## User Messages [Line range]: User Message X to User Message Y
Good Example: user message 1 "i want to build x" to user message 4 "sure, build it now"

## Description (PROVIDED):
{task_description}
Good Examples:
"Jenny started by framing the initial problem, and followed up with AI to clarify details like LLM model, UI/UX, data linking, etc. As AI started building, she clarified more things she didn’t like (such as what port to use, what model, packages)." - Describes what happened in very easy to understand language that is accurate.
Bad Examples:
"Started with vision, clarified storage and AI, simplified schemas, chose one-way task\u2192note links, CRA, port 5000, approved Blueprints, disliked docstrings." - Is way too concise, hard to interpret out of context.

## Type
Detect whether this was an optimal interaction trajectory between {user_name} and the chatbot, or whether or not the interaction had friction and was prolonged more than it should have been. 
If it was a good, interaction, return "good", otherwise, return "bad". CASE SENSITIVE.

## Reasoning
In one sentence, describe why it was good, and why it was bad. 

## Problem
If bad, explain in one sentence the ROOT CAUSE of the issue. Otherwise, return an empty string. 
Good Example:
"AI was overeager and started building out details before Jenny solidified details, causing her to go backwards constantly to fix what AI was building." - Isolates the core problem well.

## Failure Point
In one sentence, describe at what point in the interaction did the workflow trajectory go awry, and how you would spot it next time.
If the type was "good", then return an empty string.

## Guardrail
In one sentence, describe how you would bring the interaction back on course next time the the failure point is hit. 
Good Example:
"Get the exact user flow/narrative straight, because that's how {user_name} thinks, before designing the UI and implementation plan."
Bad Example:
"First align on additive scope and storage/versioning plan, then present minimal, inline, approval-ready change proposals and confirm they append to existing specs/steps before any build actions." - this is too use-case specific and also doesn't explain things well, the jargon sucks.
"Confirm preferred file organization and testing hooks upfront, then propose minimal diffs that preserve those anchors and validate curl-based testing before changes." This is super convoluted phrasing, and uses weird phrasing that is hard to understand.
"Before building, confirm storage location, model choice, linking direction, planner views, frontend tooling, port, and code style, then propose the smallest workable schema and UI flow for approval." - this is almost good, but could be better by stating "Get approval for every package used, UI design, schema, port and flesh it out fully before implemntation".
If the type was "good", then return an empty string. 

## Rules: 
List at most 5 explicit or implicit rules {user_name} had that denotes their style in planning, code style, testing, debugging, or how the AI and when the AI shoudl check in with the user. 
THE RULES CANNOT BE OVERLAPPING. BE CONSERVATIVE ABOUT THE RULES THAT YOU CREATE. IT NEEDS TO BE WELL-WRITTEN AND EASY TO UNDERSTAND.
Make sure that they are not overfit to the problem at hand and can be generalized to other problems. Do not include any specific business logic to the particular task that the user was doing - aim for generalizable rules.
Each rule must be split into a specific categories: [planning], [code-style], [testing], [debugging], [checking-with-user]
Planning - how should AI defining what to build and how to approach it based on how the user operates?
Code style - how does {user_name} enforce how the code should look or read, such as readability, naming conventions, documentation, consistency?
Testing - how does the user prefer to test their code (aka their specific flow)?
Debugging - how can AI be better at identifying and fixing errors or broken logic.
Checking with user - when is best to align with {user_name}'s intent before acting?

Good Examples:
"[code-style] Jenny has specific /frontend and /backend directories, and uses MUI and flask." - targeted in package and structure. 
"[planning] Jenny prefers to scope out edge cases, like rate limit issues, before implementing the API" - clearly targeting one rule. 
"[planning] Jenny does not like convoluted solutions but prefers simple, modular solutions that build on the existing structure" - clear targeting one thing.
Bad Examples:
"Make core behaviors automatic rather than optional flags; defaults should enforce desired workflows" - This is very nonsensical out of context.
"Keep data models minimal and flexible; rely on tags over rigid categories and avoid premature fields like status, priority, or recurrence." - The first sentence is good, the second sentence is way too specific and it is not a complete sentence.
"Use one-way linking from planner tasks to notes; let notes remain free-floating." - This rule is way too speciifc to the task at hand.
"Standardize backend conventions: Flask with Blueprints for modular routing, running on port 5000." - This should be split into two rules - together, it is hard to read. 
"Surface matrix edits per cell with approve/reject; avoid side\u2011by\u2011side diffs." - This is too specific to the product at hand and fundamentally the rule is not generalizable.
"Keep the /set_globals_for_uuid endpoint at the very bottom of backend/server.py, directly above the if __name__ == \"__main__\": block." -  A better rule is "Keep testing APIs at the end of the file.", because it is much more generalizable.
"Use a hybrid approach for inspiration categories: start fixed but allow new categories to emerge." - this is feature specific to the product we are building.
"Allow creating notes from within a specific day in the planner while keeping the notes centralized." - this is feature especific.

THERE CAN ONLY BE MAXIMUM 5 RULES PER TASK. SO CHOOSE WISELY.

--

When generating text:
1. Make sure that text does not just give the "answer" to the prolem we want to solve, is not overfit to the transcript at hand, and instead conducts a deep user analysis.
2. Make sure that all the analysis is generalizable to another problem. 
3. Make sure that the the wording is concise and human-readable and can stand alone if I were to read it out of context. 
4. At the end, I want the analysis to feel like you truly understood how I think.


-------

# Input
Below is the raw chat logs that {user_name} had with an AI assitant:

##  Chat Transcriptions
{inputs}

# Task

Return your results in this exact JSON format (NOTE: description is provided above, do NOT generate it):
{{
 "task": "[planning | code-style | testing | debugging | checking-with-user][Insert brief description of what user was trying to do. 10 WORDS. USER READABLE.]",
 "messages": ["user message 1 content", "user message 3 content", ... ],
 "type": "good" or "bad",
 "reasoning": "[One sentence concise analysis of how {user_name} thinks about tasks grounded in the workflow_trajectory and in the evidence]",
 "problem": "[Determine if there is a problem. If there is, then describe in one sentence the core issue, otherwise return an empty string.]",
 "failure_point": "[If there is a problem, provide a one sentence description of the root cause. Otherwise return an empty string]",
 "guardrail": "[If there is a problem, provide a one sentence concise description of how AI should guide {user_name} next time they were to do this task better knowing how the user works. Otherwise return an empty string]",
 "rules": [
   {{
     "rule": "[planning | code-style | testing | debugging | checking-with-user][Insert your 1-2-sentence description of the rule here/]"
   }},
   ...
 ]
}}"""

LEARNING_PROMPT_v3_NO_CHUNKING = LEARNING_PROMPT_v3.replace("List at most 5 explicit or implicit rules", "List explicit or implicit rules").replace("THERE CAN ONLY BE MAXIMUM 5 RULES PER TASK. SO CHOOSE WISELY.", "")
LEARNING_PROMPT_v3_NO_CHUNKING_NO_EVIDENCE = LEARNING_PROMPT_v3_NO_EVIDENCE.replace("List at most 5 explicit or implicit rules", "List explicit or implicit rules").replace("THERE CAN ONLY BE MAXIMUM 5 RULES PER TASK. SO CHOOSE WISELY.", "")

LEARNING_PROMPT_V4_RULES_ONLY = """You are a helpful assistant tasked with analyzing a chat transcript to extract generalizable rules about a user's workflow and preferences.

# Analysis
I'm going to give you a series of messages from a chat session. Your task is to identify and list explicit or implicit rules that define the user's style in planning, code style, testing, debugging, or how they prefer to interact with an AI assistant.

# Rules
- The rules should not be overlapping.
- Be conservative about the rules that you create. They need to be well-written and easy to understand.
- Make sure that they are not overfit to the problem at hand and can be generalized to other problems.
- Do not include any specific business logic to the particular task that the user was doing.
- Each rule must be categorized: [planning], [code-style], [testing], [debugging], [checking-with-user].

# Input
Below is the raw chat log:

## Chat Transcriptions
{inputs}

# Task
Return your results in this exact JSON format:
{{
  "rules": [
    {{
      "rule": "[category][Insert your 1-2-sentence description of the rule here]",
      "reasoning": "[Provide detailed evidence and descriptive examples from the transcriptions to justify this rule.]",
      "confidence": "[Confidence score (1–10)]",
      "decay": "[Decay score (1–10)]"
    }}
  ]
}}"""

LEARNING_PROMPT_V4_RULES_ONLY_NO_EVIDENCE = """You are a helpful assistant tasked with analyzing a chat transcript to extract generalizable rules about a user's workflow and preferences.

# Analysis
I'm going to give you a series of messages from a chat session. Your task is to identify and list explicit or implicit rules that define the user's style in planning, code style, testing, debugging, or how they prefer to interact with an AI assistant.

# Rules
- The rules should not be overlapping.
- Be conservative about the rules that you create. They need to be well-written and easy to understand.
- Make sure that they are not overfit to the problem at hand and can be generalized to other problems.
- Do not include any specific business logic to the particular task that the user was doing.
- Each rule must be categorized: [planning], [code-style], [testing], [debugging], [checking-with-user].

# Input
Below is the raw chat log:

## Chat Transcriptions
{inputs}

# Task
Return your results in this exact JSON format:
{{
  "rules": [
    {{
      "rule": "[category][Insert your 1-2-sentence description of the rule here]"
    }}
  ]
}}"""

LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING = LEARNING_PROMPT_V4_RULES_ONLY
LEARNING_PROMPT_V4_RULES_ONLY_NO_CHUNKING_NO_EVIDENCE = LEARNING_PROMPT_V4_RULES_ONLY_NO_EVIDENCE
