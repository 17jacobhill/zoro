TASK_LABELING_PROMPT = """You are analyzing a chat transcript to group messages into tasks.

Below are all the user messages from the conversation. Some are initial task requests, others are follow-ups.

Your job: Label each message with a task number (1, 2, 3, etc.).
- Messages that clarify/iterate on the current task should keep the same task number
- Messages that start a completely NEW request should get a new task number

Look for:
- Clarifications starting with "no", "actually", "wait"
- Topic changes (rules → schemas → environment setup)
- When the user asks for something completely different

There should be at least 10 tasks in there. If you only find one task, you are definitely doing something wrong.
User messages:
{messages}

Return ONLY a JSON array with this format:
[
  {{"message_num": 1, "task": 1}},
  {{"message_num": 2, "task": 1}},
  {{"message_num": 3, "task": 2}},
  ...
]

No explanation, just the JSON array."""
