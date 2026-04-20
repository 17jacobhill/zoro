# ⚠️ CRITICAL: Rule Proof System

## Item ID Format
**IMPORTANT:** All commands use the format `step-X` or `step-X-Y` (e.g., `step-1`, `step-2-3`).  
Check `.rules/zoro_plan.md` for the exact item IDs in your plan.

**Wrong formats that will fail:**
- `1` ❌
- `phase-1` ❌  
- `item-1` ❌

## YOU CANNOT MARK ANY STEP COMPLETE WITHOUT REQUIRED RULE PROOFS!

### Required for EVERY Step:
1. **Prove all required rules** (with detailed explanation and code evidence)
2. **Then mark complete**
3. **Optional:** record extra step/item evidence with `zoro viz-verify-step`

---

## Core Principle: EXTREME GROUNDING

Every verification MUST be **extremely grounded in concrete evidence**. This is not optional.

**BAD (casual):**
"Phase 1 complete - all schemas are done"

**GOOD (grounded):**
"Phase 1 verified complete based on: (1) RuleVerification schema at backend/visualization/schemas.py lines 6-15 defines required fields file_path, code_snippet, verdict, description, timestamp with proper Pydantic types, (2) StepVerification schema at lines 18-25 includes description, evidence, output, verdict, timestamp fields, (3) Rule.verifications field at line 33 typed as List[RuleVerification] with default_factory=list, (4) PlanItem.step_verifications at line 43 similarly typed. Confirmed all schemas serialize/deserialize correctly by checking model_config includes extra='forbid' constraint."

---

## Proof Commands

**⚠️ CRITICAL: Terminal Command Format**

All commands MUST be written on a SINGLE LINE. DO NOT use backslashes (`\`) for line continuation - they cause terminal hangs.

- Maximum ~2000 characters per command
- If longer, split into multiple separate verifications
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

### 2. Optional: Record Extra Step/Item Evidence

```bash
zoro viz-verify-step <item-id> --explanation "Extremely detailed explanation of what was accomplished, with concrete evidence from multiple files showing the work was completed" --file "path/to/file1.py" --snippet "code snippet" --line-range "10-25" --file "path/to/file2.py" --snippet "code snippet" --line-range "45-60" --output "path/to/result.py" --verdict pass
```

**Requirements:**
- `--explanation`: DETAILED accomplishment statement. Helpful when you want extra audit trail, but it is **not required for completion**.
- If you include code evidence, ground it in:
  - Multiple specific files created/modified
  - Exact features implemented
  - How they work together
  - Tests passing (if applicable)
  - Concrete proof of functionality
- `--file` + `--snippet`: (optional) Multiple code blocks showing key work
  - Keep the command itself single-line and use escaped `\n` inside snippets when you need multiple lines
- `--output`: (optional) File/URL showing final result
- `--verdict`: pass/fail/unclear (default: pass)

**Escaped multiline snippets:** use `--snippet "line 1\nline 2"` to store a multiline code block while keeping the terminal command on one line. If the code itself contains the literal characters `\n`, escape the backslash as `\\n`.

**Note:** For non-leaf items (phases, high-level steps with children), this command stores verification in `item_verifications`. For leaf items, it stores in `step_verifications`.

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
zoro viz-update step-1-1 completed
✅ Updated step-1-1 to completed
```

---

## Optional Extra Evidence Example

If you want extra audit trail for a phase or leaf step, you can still record it explicitly:

```bash
zoro viz-verify-step step-1 --explanation "Backend schema design phase complete. Verified by: (1) CodeBlock model at backend/visualization/schemas.py lines 5-9 provides file_path, code_snippet, line_range fields for multi-file evidence, (2) RuleVerification at lines 12-17 includes explanation and code_blocks array for detailed rule compliance tracking, (3) StepVerification at lines 20-26 supports both code evidence and optional output location, (4) PlanItem at lines 41-49 includes both step_verifications for leaves and item_verifications for non-leaves." --file "backend/visualization/schemas.py" --snippet "class CodeBlock(BaseModel): pass" --line-range "5-9" --file "backend/visualization/schemas.py" --snippet "class RuleVerification(BaseModel): pass" --line-range "12-16" --verdict pass
```

---

## What Happens If You Skip?

```bash
$ zoro viz-update step-1-1 completed

❌ Cannot mark complete. Missing verifications:
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

### Optional Step Evidence
✓ Proves the entire feature works with comprehensive evidence
✓ Documents what was built in extreme detail
✓ Links to output artifacts and test results
✓ Works for both leaf steps and high-level phases

### Combined Power
✓ Can't skip required rule proofs - enforcement is automatic
✓ Keeps the completion gate focused on concrete rule compliance
✓ Creates extremely detailed project documentation
✓ Enables precise tracking of what was actually built
✓ Every claim is backed by concrete file paths and code snippets
