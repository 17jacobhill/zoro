# ZORO Protocol
This file defines the required execution protocol for agents.

## Core Rule

Before starting work, read `.zoro/zoro_plan.md`.

For every plan step, the agent must:
1. Call `zoro update-step <step-id> in_progress` when work begins.
2. Call `zoro prove-rule <step-id> --rule "..." --evidence "..."` for each required rule.
3. Only after required rule evidence is submitted, call `zoro update-step <step-id> completed`.

The agent may not advance to the next step until the current step is marked `completed`.

## Required Command Order

Use this order for each step:

```bash
zoro update-step <step-id> in_progress
# implement changes
zoro prove-rule <step-id> --rule "<rule text>" --evidence "<what was implemented and where>"
zoro update-step <step-id> completed
```

## Literal `prove-rule` Command Shapes

Use the non-test form when test evidence is not required:

```bash
zoro prove-rule <step-id> --rule "<rule text>" --evidence "<what changed and why it satisfies the rule>"
```

Use the test-evidence form for testable rules:

```bash
zoro prove-rule <step-id> --rule "<rule text>" --evidence "<what changed and why it satisfies the rule>" --test-name "<test_name>" --test-command "<command>" --test-result pass --test-output "<summary>" --test-file "<path>"
```

## Hard Stops

- Do not mark a step `completed` before required `zoro prove-rule` calls.
- Do not start the next step while the current step is incomplete.
- If evidence is missing or weak, remain on the current step and add better proof.

## Evidence Guidance (Concise)

Evidence should be specific and audit-friendly:
- What changed
- Where it changed (file/component)
- Why it satisfies the rule
- Optional verification signal (test result, output, screenshot note)

## Example

```bash
zoro update-step step-1-1 in_progress
zoro prove-rule step-1-1 --rule "Use repository pattern" --evidence "Added UserRepository in backend/repositories/user_repository.py and refactored UserService to depend on it."
zoro update-step step-1-1 completed
```

### Example With Test Evidence

```bash
zoro update-step step-2-3 in_progress
zoro prove-rule step-2-3 --rule "Strict testable rule: API parsing must handle nested response fields" --evidence "Updated parser in frontend/src/services/api.ts to read supervision.status and token_stats safely." --test-name "test_nested_response_parsing" --test-command "pytest tests/backend/test_api_parsing.py -k test_nested_response_parsing" --test-result pass --test-output "1 passed" --test-file "tests/backend/test_api_parsing.py"
zoro update-step step-2-3 completed
```
