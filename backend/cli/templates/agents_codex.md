# AGENTS.md

Follow the Zoro workflow defined in `ZORO.md`.

Read these files before acting:

- `ZORO.md`
- `.zoro/CURRENT_PLAN.md`

Session-start requirement:
- On the first user message in a new coding session, respond in plan mode only.
- Output only the implementation plan and wait for explicit approval before doing any implementation work.

If you are running Codex, ensure `.zoro/config.json` contains:

```json
{
  "chat_history_source": "codex"
}
```
