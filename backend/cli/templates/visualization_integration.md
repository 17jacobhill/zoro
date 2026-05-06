# ⚠️ CRITICAL: Rule Proof System

## Item ID Format
**IMPORTANT:** All commands use the format `step-X` or `step-X-Y` (e.g., `step-1`, `step-2-3`).  
Check `.zoro/CURRENT_PLAN.md` for the exact item IDs in your plan.

**Wrong formats that will fail:**
- `1` ❌
- `phase-1` ❌  
- `item-1` ❌

## YOU CANNOT MARK ANY STEP COMPLETE WITHOUT REQUIRED RULE PROOFS!

### Required for EVERY Step:
1. **Prove all required rules** (with detailed explanation and code evidence)
2. **Then mark complete**

---

## Core Principle: EXTREME GROUNDING

Every verification MUST be **extremely grounded in concrete evidence**. This is not optional.

**BAD (casual):**
"Step 1 complete - all schemas are done"

**GOOD (grounded):**
"Step 1 proof complete based on: (1) `backend/visualization/services/evidence_store.py` appends a canonical rule-proof record with file evidence and verdict, (2) `backend/visualization/services/plan_persistence.py` strips transient proof fields so `plan.json` stays plan-shaped, and (3) `frontend/src/components/Visualization/RuleReviewPanel.tsx` reads proof records from the evidence API instead of plan-embedded verification state."

---

## Proof Commands

**⚠️ CRITICAL: Terminal Command Format**

All commands MUST be written on a SINGLE LINE. DO NOT use backslashes (`\`) for line continuation - they cause terminal hangs.

- Maximum ~2000 characters per command
- If longer, split into multiple separate proof commands
- All parameters on one line

### 1. Prove a Specific Rule

```bash
zoro prove-rule <item-id> --rule "[category] rule text" --explanation "Detailed natural language explanation of HOW the rule was followed, grounded in specific file paths, line numbers, class names, method signatures, etc." --file "path/to/file1.py" --snippet "code snippet from file1" --line-range "10-25" --file "path/to/file2.py" --snippet "code snippet from file2" --line-range "45-60" --verdict pass
```

**Requirements:**
- `--rule`: Match the rule text (case-insensitive, partial match OK)
- `--explanation`: DETAILED natural language explanation. Must include:
  - Specific file paths
  - Line numbers or ranges
  - Class/function names
  - What was implemented and how
  - Why it satisfies the rule
- `--file` + `--snippet`: Can be repeated multiple times. Each occurrence requires:
  - File path (relative to project root)
  - Literal code snippet from that file. Keep the command itself single-line and use escaped `\n` for multiline evidence.
  - Optional line range (e.g., "10-25")
- `--verdict`: pass/fail/unclear (default: pass)

**Escaped multiline snippets:** use `--snippet "line 1\nline 2"` to store a multiline code block while keeping the terminal command on one line. If the code itself contains the literal characters `\n`, escape the backslash as `\\n`.

---

## Complete Example

### Leaf Step: "Create user service"
**Rules:**
- [architecture] Use repository pattern
- [code-style] Remove inline comments

### Workflow:

```bash
# 1. Do the work
# (create backend/services/user_service.py and backend/repositories/user_repository.py)

# 2. Prove EACH rule with detailed explanation
zoro prove-rule step-1-1 --rule "[architecture] Use repository pattern" --explanation "Implemented repository pattern by creating UserRepository class at backend/repositories/user_repository.py lines 5-30 with methods get(), create(), update(), delete() that encapsulate all database operations. Then injected UserRepository instance into UserService constructor at backend/services/user_service.py line 8 via dependency injection. All CRUD operations in UserService (lines 12-40) now delegate to the repository methods instead of direct database access, ensuring separation of concerns between business logic and data access." --file "backend/repositories/user_repository.py" --snippet "class UserRepository: pass" --line-range "5-18" --file "backend/services/user_service.py" --snippet "class UserService: pass" --line-range "6-12" --verdict pass

zoro prove-rule step-1-1 --rule "[code-style] Remove inline comments" --explanation "Verified no inline comments exist in user_service.py by reviewing entire file at backend/services/user_service.py lines 1-50. All code is self-documenting with clear variable names and type hints. Only module-level docstring at line 1 and class docstring at line 7 are present, both following PEP 257 standards." --file "backend/services/user_service.py" --snippet "class UserService: pass" --line-range "6-11" --verdict pass

# 3. Mark complete (NOW ALLOWED!)
zoro update-step step-1-1 completed
✅ Updated step-1-1 to completed
```

---

## What Happens If You Skip?

```bash
$ zoro update-step step-1-1 completed

❌ Cannot mark complete. Missing rule proofs:
  - Rule not verified: [architecture] Use repository pattern
  - Rule not verified: [code-style] Remove inline comments

Use these commands:
  zoro prove-rule step-1-1 --rule "[category] text" --explanation "detailed explanation" --file "path/to/file.py" --snippet "code"
```

---

## Benefits

### Rule Proof (Required)
✓ Proves you followed each architectural/style rule with concrete code
✓ Creates detailed audit trail with file paths and line numbers
✓ Forces explicit compliance checks with natural language explanations
✓ Supports multiple code blocks per rule for complex implementations

### Grounded Workflow
✓ Can't skip required rule proofs - enforcement is automatic
✓ Keeps the completion gate focused on concrete rule compliance
✓ Creates extremely detailed project documentation
✓ Enables precise tracking of what was actually built
✓ Every claim is backed by concrete file paths and code snippets
