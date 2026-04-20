# Zoro Visualization Plan Integration - No Verification Mode

## Item ID Format
**IMPORTANT:** All commands use the format `step-X` or `step-X-Y` (e.g., `step-1`, `step-2-3`).  
Check `.rules/zoro_plan.md` for the exact item IDs in your plan.

**Wrong formats that will fail:**
- `1` ❌
- `phase-1` ❌  
- `item-1` ❌

## Overview
This mode allows you to work through visualization plans with **simple status tracking only**. No verification commands are required - just mark items as in_progress or completed as you work.

## Core Workflow

**⚠️ CRITICAL: Terminal Command Format**

All commands MUST be written on a SINGLE LINE. DO NOT use backslashes (`\`) for line continuation - they cause terminal hangs.

- Maximum ~2000 characters per command
- All parameters on one line

When working on ANY item:

```bash
# BEFORE starting work:
zoro viz-update <item-id> in_progress

# AFTER completing work:
zoro viz-update <item-id> completed
```

That's it! No verification steps required.

---

## Step-by-Step Workflow

### Phase Work:
1. Read `.rules/zoro_plan.md` to understand the phase scope
2. Mark phase as `in_progress`
3. Work through all steps in the phase
4. Mark phase as `completed`

### Step Work:
1. Mark step as `in_progress`
2. If substeps exist, work through each one (in_progress → completed)
3. Verify all substeps are complete
4. Mark step as `completed`

### Example Complete Workflow:

```bash
# Starting Phase 4
zoro viz-update phase-4 in_progress

# Step 4.1 (has substeps)
zoro viz-update step-4-1 in_progress

# Substep 4.1.1
zoro viz-update step-4-1-1 in_progress
# ... do the work (implement feature) ...
zoro viz-update step-4-1-1 completed

# Substep 4.1.2
zoro viz-update step-4-1-2 in_progress  
# ... do the work (implement feature) ...
zoro viz-update step-4-1-2 completed

# ... continue for all substeps ...

# Complete parent step after all substeps done
zoro viz-update step-4-1 completed

# Complete phase after all steps done
zoro viz-update phase-4 completed
```

---

## Critical Rules

### 1. THE PLAN IS CANONICAL
- `.rules/zoro_plan.md` is the **source of truth**
- Always read the plan at the start of each task
- Check which step you're on and what's required
- Grab all the rules needed to execute this step (including inherited rules) and make sure to generate code following these rules
- Understand parent/child relationships (phases → steps → substeps)

### 2. NEVER SKIP SUBSTEPS
If a step has substeps, you MUST complete ALL substeps before marking the parent step complete:
- Read the plan to see all substeps
- Mark each substep in_progress → completed
- Only then mark the parent step completed

### 3. DESIGN SYSTEM COMPLIANCE
**RULE**: Always use design-system colors from `frontend/src/design-system/colors.ts`

```typescript
// Available colors:
colors.green     // #87ae73
colors.darkGreen // #6b8a5c  
colors.blue      // #5BB9C2
colors.red       // #9a4e4e
colors.gold      // #FDB813
colors.grey      // #9e9e9e
```

**NEVER hardcode hex values**. Always reference the design system.

---

## Common Mistakes to Avoid

❌ **DON'T**:
- Skip marking items as in_progress
- Mark parent steps complete before substeps
- Ignore the plan structure

✅ **DO**:
- Always mark in_progress before starting
- Complete all substeps before parent step
- Use design-system colors
- Check the plan frequently
- Follow the hierarchical structure

---

## Config Setting

Ensure `.zoro/config.json` has:
```json
{
  "enforcement_mode": "no-verification"
}
```

---

## Notes

- Rules are still tracked in the plan for reference
- You can use the frontend UI to see rule conflicts and suggestions
- The Supervisor Agent may still provide recommendations
- This mode is useful for rapid prototyping or when working on trusted code
