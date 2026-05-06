# Zoro Visualization Plan Integration - Selective Verification Mode

## Quick Start (Read This First)

Selective verification means: verify only **strict** rules (⚡), but verify them strictly.

1. Activate environment first:
```bash
conda activate zoro
```

2. Execute Zoro writes sequentially only:
- No parallel/background Zoro write commands.
- Run one command, wait for completion, then run next.

3. Required order per item:
- `zoro update-step <item-id> in_progress`
- implement code
- `zoro prove-rule ...` for each strict (⚡) rule
- `zoro update-step <item-id> completed`

4. Hard stop rules:
- Never mark `completed` before required verify commands.
- Failed/missing strict verification is blocking.

5. Command formatting:
- Single-line commands only (no `\` continuations).
- Keep commands single-line; use escaped `\n` inside `--snippet` for multiline code evidence.

## Detailed Reference

This mode provides **selective verification**: only rules marked as strict (⚡) require CLI verification with code evidence. Non-strict rules are guidance and do not block completion.

## Complete Example

### Scenario: Step with Mixed Rules

**Step 1-1: "Create user service"**

Rules:
- ⚡ `[architecture] Use repository pattern` (STRICT - must verify)
- 📋 `[code-style] Remove inline comments` (optional - tracked only)

### Workflow:

```bash
# 1. Mark step in progress
zoro update-step step-1-1 in_progress

# 2. Do the work
# (create backend/services/user_service.py and backend/repositories/user_repository.py)

# 3. Prove the STRICT rule only (with optional test evidence)
zoro prove-rule step-1-1 --rule "[architecture] Use repository pattern" --explanation "Implemented repository pattern by creating UserRepository class at backend/repositories/user_repository.py with methods get(), create(), update(), delete() that encapsulate all database operations. UserService uses dependency injection to receive UserRepository instance and delegates all CRUD operations to the repository." --file "backend/repositories/user_repository.py" --snippet "class UserRepository: pass" --line-range "5-12" --file "backend/services/user_service.py" --snippet "class UserService: pass" --line-range "6-12" --test-name "test_repository_pattern" --test-command "pytest tests/temp/test_rule_step_1_1.py -k test_repository_pattern" --test-result pass --test-output "1 passed" --test-file "tests/temp/test_rule_step_1_1.py" --verdict pass

# 4. Mark complete (NOW ALLOWED - strict rule proved)
zoro update-step step-1-1 completed
✅ Updated step-1-1 to completed
```

**Note**: The optional `[code-style]` rule was NOT verified, but completion is still allowed because it's not marked strict.

**Multiline snippets:** keep the full command on one line and pass escaped newlines inside `--snippet`, for example `--snippet "def save():\n    return True"`. If the literal code contains `\n`, escape the backslash as `\\n`.

---

## How Rules Become Strict

### 1. Auto-included: Favorited KB Rules
Favorited KB rules are always included when rules are retrieved for a plan:

```
Rule is favorited → Included in plan retrieval
```

### 2. Manual Toggle in UI
Click the ⚡ toggle button next to any rule in the plan to mark/unmark it as strict.

### 3. Inheritance
If a parent has strict rules, children inherit them:

```
Parent Step has ⚡ Rule X
├─ Step 1-1 inherits ⚡ Rule X (must verify)
└─ Step 1-2 inherits ⚡ Rule X (must verify)
```

**Important**: Each child must prove inherited rules independently - proof records don't carry over between siblings.

---

## Step-by-Step Workflow

### Basic Step (No Substeps):

```bash
# 1. Mark in progress
zoro update-step step-1-1 in_progress

# 2. Do the work

# 3. Prove strict rules (if any) - REQUIRED before completion
zoro prove-rule step-1-1 --rule "..." --explanation "..." --file "..." --snippet "..."

# 4. Mark complete (only after successful prove-rule commands above)
zoro update-step step-1-1 completed
```

**Do not reorder these commands.** In particular, never call `completed` before running required verify commands.

### Step with Substeps:

```bash
# Start parent step
zoro update-step step-4-1 in_progress

# Substep 4.1.1
zoro update-step step-4-1-1 in_progress
# ... implement feature ...
zoro prove-rule step-4-1-1 --rule "text" --explanation "details" --file "file.py" --snippet "code"
zoro update-step step-4-1-1 completed

# Substep 4.1.2
zoro update-step step-4-1-2 in_progress
# ... implement feature ...
zoro prove-rule step-4-1-2 --rule "text" --explanation "details" --file "file.py" --snippet "code"
zoro update-step step-4-1-2 completed

# Complete parent step
zoro update-step step-4-1 completed
```

---

## UI Indicators

### Plan Tree
- ⚡ **Strict badge**: Rule will be verified by CLI
- 🌟 **Favorite badge**: Rule from KB favorites (auto-included in retrieval)
- **Toggle button**: Click to mark/unmark rule as strict
- **(from Parent)**: Shows inherited rules with source

### Enforcement Panel
**Top Section (Green Background)**:
- **⚡ Strictly Enforced Rules**
- CLI-verified with code evidence before completion
- Shows verification status with checkmarks

**Bottom Section (Grey Background)**:
- **📋 Other Rules**
- Not strictly enforced
- Optional "Enforce" button for transparency checks

---

## What Happens If You Skip?

```bash
$ zoro update-step step-1-1 completed

❌ Cannot mark complete. Missing strict rules:
  - Rule not verified [STRICT]: [architecture] Use repository pattern

Use these commands:
  zoro prove-rule step-1-1 --rule "[category] text" --explanation "..." --file "..." --snippet "..."

---

## ⚡ CRITICAL: Test Generation for Testable Strict Rules

When verifying a strict rule marked with 🧪 (`is_testable=true`), you MUST generate and run tests. **This is NOT OPTIONAL** - the CLI will BLOCK verification without test evidence.

### Enforcement

**THE CLI WILL REJECT YOUR VERIFICATION IF:**
- Rule has `is_testable=true` AND `needs_strict_enforcement=true`
- You don't provide ALL test flags: `--test-name`, `--test-command`, `--test-result`, `--test-file`

**Error you'll see:**
```
❌ ERROR: This rule is marked as 🧪 TESTABLE and requires test evidence!
```

**YOU CANNOT PROCEED WITHOUT TESTS!**

### Step 1: Identify Testable Rules

**Testable rule categories:**
- `[architecture]` - System structure, patterns (repository, dependency injection, etc.)
- `[api-design]` - API contracts, response structures, endpoint behavior
- `[code-style]` - Code organization, naming conventions
- `[data-model]` - Schema validation, field presence
- `[error-handling]` - Error scenarios, fallback behavior

**Non-testable rule categories:**
- `[workflow]` - Human interaction (e.g., "check with user")
- `[documentation]` - Manual review needed
- `[ui-ux]` - Visual appearance (use manual verification or visual testing tools)

### Step 2: Generate Test File

For testable rules, create a focused test that validates compliance:

**Test file location:**
```
.zoro/visualization/{chat-id}/tests/step_{step_id}/test_rule_{sanitized_category}.py
```

**Naming conventions:**
- File: `test_rule_{sanitized_category}.py` (e.g., `test_rule_architecture.py`)
- Function: `test_{sanitized_rule_concept}()` (e.g., `test_repository_pattern()`)

**Example for "[architecture] Use repository pattern":**

```python
# .zoro/visualization/abc123/tests/step_1_1/test_rule_architecture.py
import pytest
from pathlib import Path

def test_repository_pattern():
    """Verify UserService uses repository pattern."""
    # Check repository file exists
    repo_file = Path("backend/repositories/user_repository.py")
    assert repo_file.exists(), "Repository file should exist"
    
    # Check service file exists
    service_file = Path("backend/services/user_service.py")
    assert service_file.exists(), "Service file should exist"
    
    # Verify service imports repository
    service_content = service_file.read_text()
    assert "UserRepository" in service_content, "Service should import UserRepository"
    assert "def __init__" in service_content, "Service should have constructor for DI"
```

**Example for "[api-design] Parse nested API responses":**

```python
# .zoro/visualization/abc123/tests/step_2_3/test_rule_api_design.py
import pytest
import json

def test_nested_response_parsing():
    """Verify API client parses nested response fields."""
    # Mock response structure
    mock_response = {
        "supervision": {"status": "ok"},
        "token_stats": {"count": 100}
    }
    
    # Test parsing logic (adapt to your actual API client)
    from backend.services.api_client import parse_response
    
    result = parse_response(mock_response)
    assert "supervision" in result
    assert result["supervision"]["status"] == "ok"
    assert "token_stats" in result
    assert result["token_stats"]["count"] == 100
```

### Step 3: Run Test

```bash
pytest .zoro/visualization/{chat-id}/tests/step_X_Y/test_rule_{category}.py -v
```

Capture the output for inclusion in verification.

### Step 4: Verify with Test Evidence

```bash
zoro prove-rule step-X-Y --rule "[category] rule text" --explanation "Detailed explanation of implementation" --file "path/to/file.py" --snippet "relevant code" --line-range "10-25" --test-name "test_repository_pattern" --test-command "pytest .zoro/visualization/{chat-id}/tests/step_X_Y/test_rule_architecture.py -v" --test-result pass --test-output "1 passed in 0.5s" --test-file ".zoro/visualization/{chat-id}/tests/step_X_Y/test_rule_architecture.py"
```

**The test file will be automatically read and included in the verification for display in the UI.**

### Complete Workflow Example

```bash
# 1. Mark step in progress
zoro update-step step-1-1 in_progress

# 2. Implement the feature (e.g., create repository and service files)
# (create backend/repositories/user_repository.py)
# (create backend/services/user_service.py)

# 3. Generate test for strict rule
mkdir -p .zoro/visualization/abc123/tests/step_1_1
cat > .zoro/visualization/abc123/tests/step_1_1/test_rule_architecture.py << 'EOF'
import pytest
from pathlib import Path

def test_repository_pattern():
    repo_file = Path("backend/repositories/user_repository.py")
    assert repo_file.exists()
    
    service_file = Path("backend/services/user_service.py")
    assert service_file.exists()
    
    service_content = service_file.read_text()
    assert "UserRepository" in service_content
EOF

# 4. Run test
pytest .zoro/visualization/abc123/tests/step_1_1/test_rule_architecture.py -v

# 5. Prove rule with test evidence
zoro prove-rule step-1-1 --rule "[architecture] Use repository pattern" --explanation "Implemented repository pattern by creating UserRepository at backend/repositories/user_repository.py with get(), create(), update(), delete() methods. UserService at backend/services/user_service.py receives repository via dependency injection." --file "backend/repositories/user_repository.py" --snippet "class UserRepository: pass" --line-range "5-12" --file "backend/services/user_service.py" --snippet "class UserService: pass" --line-range "8-15" --test-name "test_repository_pattern" --test-command "pytest .zoro/visualization/abc123/tests/step_1_1/test_rule_architecture.py -v" --test-result pass --test-output "1 passed in 0.52s" --test-file ".zoro/visualization/abc123/tests/step_1_1/test_rule_architecture.py"

# 6. Mark complete
zoro update-step step-1-1 completed
```

### Test Lifecycle

**Keep test files** in the visualization directory - they serve as:
- Regression tests for future changes
- Documentation of what was verified
- Audit trail of compliance

Tests are organized by step, so they're easy to locate and maintain.

```

---

## Critical Rules

### 1. THE PLAN IS CANONICAL
- `.zoro/CURRENT_PLAN.md` is the **source of truth**
- Always read the plan at the start of each task
- Check which step you're on and what strict rules apply
- Review all rules (strict and optional) for guidance

### 2. NEVER SKIP SUBSTEPS
If a step has substeps, you MUST complete ALL substeps before marking the parent complete.

### 3. STEP-SPECIFIC VERIFICATIONS
Each step must prove its own strict rules - proof records don't carry over between sibling steps, even for inherited rules.

### 4. DESIGN SYSTEM COMPLIANCE
Always use design-system colors from `frontend/src/design-system/colors.ts`:

```typescript
colors.green     // #87ae73
colors.darkGreen // #6b8a5c  
colors.blue      // #5BB9C2
colors.red       // #9a4e4e
colors.gold      // #FDB813
colors.grey      // #9e9e9e
```

**NEVER hardcode hex values**.

---

## Benefits

### Strict Rules (Verified)
✓ Ensures critical architectural/style rules are followed
✓ Creates audit trail with code evidence
✓ Blocks completion until verified
✓ Supports multiple code blocks per rule

### Optional Rules (Tracked)
✓ Provides guidance without blocking progress
✓ Can be manually verified for transparency
✓ Reduces verification overhead for minor rules

### Combined Power
✓ Focus verification effort where it matters most
✓ Flexible - mark rules strict as needed
✓ Inherited strict rules ensure consistency
✓ Step-specific proof records prevent cross-contamination

---

## Config Setting

Ensure `.zoro/config.json` has:
```json
{
  "enforcement_mode": "selective-verification",
  "rule_test_evidence_enabled": true
}
