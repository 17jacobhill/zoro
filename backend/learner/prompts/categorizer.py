BATCH_CATEGORIZER_PROMPT = """
Categorize ALL these tasks in ONE pass. Look at the full context of the raw chat data to understand each task better.

## Available Task Types:
{type_list}

## Tasks to Categorize (raw chat data for each task):
{tasks_json}

Instructions:
1. For EACH task, analyze the full raw chat conversation to understand what the user was trying to accomplish
2. Match each task to the MOST appropriate type from the available types
3. Generate TWO descriptions for each task:
   - task: A brief 1-sentence summary (e.g., "fix navbar alignment issue")
   - description: A chronological narrative of what happened:
     * Start with what the user initially requested
     * Include key decision points, clarifications, or changes in direction
     * Note any corrections or iterations
     * Keep it factual and concise (2-4 sentences)
     * Example: "User requested adding a login form, then specified validation requirements and error handling approach, and approved the final design before implementation."
4. Be CONSISTENT - similar tasks should get similar types
5. Consider the progression and relationship between tasks
6. If a task doesn't fit any type well, use "uncategorized"

Return a JSON object with a "suggestions" array containing one entry per task (maintain the same order):
{{
  "suggestions": [
    {{
      "task_id": "...",
      "task": "fix navbar alignment",
      "type": "bug fix",
      "confidence": 8,
      "description": "User reported navbar misalignment on mobile, discussed root cause in CSS flexbox, approved fix after testing."
    }},
    {{
      "task_id": "...",
      "task": "debug API timeout error",
      "type": "debugging",
      "confidence": 9,
      "description": "User encountered timeout errors in production, traced to database connection pool, implemented retry logic."
    }},
    ...
  ]
}}

IMPORTANT: Return EXACTLY one categorization per task in the same order they were provided. Each entry MUST include task_id, task, type, confidence, and description.
"""
