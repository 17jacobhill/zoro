# Visualization Plan: create rule in kb (df8bfd69-e219-44a5-84f1-34de5aecc9ff)

## Items

### 1: Frontend Components:
**Status:** completed

- `AddRuleModal.tsx` - Modal with form and refinement preview
- Update `RulesBrowserPanel.tsx` - Add "+ Add Rule" button
- Update `api.ts` - Add `refineRule()` and use existing `createItem()`

**Tracking:**
- Start: `zoro viz-update step-2 in_progress`
- Complete: `zoro viz-update step-2 completed`

**Rules:**
- [api-design] Use the centralized API client in frontend/src/services/api.ts (configured with API_BASE) for all HTTP calls. Add new endpoints as typed helper methods in api.ts, and never hardcode URLs or use axios directly in components.
- [ui-ux] Adopt project design-system components (Accordion, Button, etc.) and palette tokens (colors.green/gold/grey). Avoid MUI defaults and hardcoded colors. Remove MUI blue ripple/focus outlines across interactive elements (IconButtons, Buttons, headers/accordions) for a consistent theme in Monitoring, ExtractedPlanView, and related UIs.

---

  ### 1.1: Implement AddRuleModal.tsx with form and side-by-side preview
  **Status:** completed

  Use design-system TextField/Select/Button; show Original vs Refined panels and score badges.

  **Tracking:**
  - Start: `zoro viz-update step-2-1 in_progress`
  - Complete: `zoro viz-update step-2-1 completed`

  **Rules:**
  - [UI/Design System] Use the project’s custom design-system components (e.g., TextField, Select) and brand colors; avoid raw MUI defaults like blue outlines and ripples. Ensure green is used where expected (e.g., search) and remove MUI focus rings (disableRipple, no blue outline).

  ---

  ### 1.2: Add '+ Add Rule' trigger in RulesBrowserPanel.tsx
  **Status:** completed

  Place a DS Button that opens AddRuleModal; ensure consistent green styling and no blue focus.

  **Tracking:**
  - Start: `zoro viz-update step-2-2 in_progress`
  - Complete: `zoro viz-update step-2-2 completed`

  ---

  ### 1.3: Add api.ts::refineRule() and use createItem() to save
  **Status:** completed

  Add typed helper for POST /api/kb/items/refine and reuse existing createItem() for persistence.

  **Tracking:**
  - Start: `zoro viz-update step-2-3 in_progress`
  - Complete: `zoro viz-update step-2-3 completed`

  **Rules:**
  - [api-design] Parse data from structured API responses using nested fields (e.g., response.supervision, response.token_stats) rather than assuming a flat payload, and apply appropriate TypeScript types.
  - [workflow] Verify code correctness before asserting; double-check snippets and confirm accuracy when asked.

  ---

  ### 1.4: Handle alerts and clear modal state on success
  **Status:** completed

  Show success/error alert after saving; auto-dismiss; reset form fields and close modal.

  **Tracking:**
  - Start: `zoro viz-update step-2-4 in_progress`
  - Complete: `zoro viz-update step-2-4 completed`

  **Rules:**
  - [ui-ux] Provide user feedback via success/error alerts after async operations and auto-dismiss them after a short delay.

  ---

### 2: Backend Routes:
**Status:** completed

- **New**: `POST /api/kb/items/refine` - LLM refinement endpoint
- **Existing**: `POST /api/kb/items` - Save the final rule (already exists)

**Tracking:**
- Start: `zoro viz-update step-3 in_progress`
- Complete: `zoro viz-update step-3 completed`

**Rules:**
- [api-design] Use GET endpoints strictly for reading existing status without side effects and POST endpoints only to initiate actions; do not poll POST endpoints or trigger actions via GET.
- [data-model] Preserve confidence, decay, and their reasoning fields across all persistence paths (save → markdown → parser → schema → KB), and ensure all response/processing schemas include these fields so validation does not strip them.
- [tooling] Use the OpenAI gpt-5 model for the agents.

---

  ### 2.1: Implement POST /api/kb/items/refine for LLM refinement
  **Status:** completed

  Accept raw rule fields; return refined title/content, confidence/decay with reasoning, and echo context/evidence.

  **Tracking:**
  - Start: `zoro viz-update step-3-1 in_progress`
  - Complete: `zoro viz-update step-3-1 completed`

  **Rules:**
  - [workflow] Use deterministic, code-based cleanup (e.g., strip markdown code fences) to parse LLM JSON outputs instead of re-prompting the LLM.
  - [prompt-engineering] Escape JSON braces in Python format strings within prompt templates to prevent KeyError during .format() calls.

  ---

  ### 2.2: Ensure schemas include context/evidence and score fields
  **Status:** completed

  Validate request/response schemas to carry context, evidence, confidence, decay, and reasoning fields end-to-end.

  **Tracking:**
  - Start: `zoro viz-update step-3-2 in_progress`
  - Complete: `zoro viz-update step-3-2 completed`

  **Rules:**
  - [data-model] Ensure LLM outputs include a 'context' field describing what the user and LLM were trying to build, in addition to 'evidence', within the dynamic reflection output schema.

  ---

  ### 2.3: Persist manual items via POST /api/kb/items with source_file: 'manual'
  **Status:** completed

  Generate UUID and save refined fields to KB; ensure item_id naming and field integrity.

  **Tracking:**
  - Start: `zoro viz-update step-3-3 in_progress`
  - Complete: `zoro viz-update step-3-3 completed`

  **Rules:**
  - [API/Data Contract] Use the Knowledge Base item field name 'item_id' consistently across frontend and backend; do not use 'id' for KB items.

  ---

  ### 2.4: Honor HTTP semantics and add defensive error handling
  **Status:** completed

  Keep GETs side-effect free; POSTs initiate actions; gracefully handle partial LLM outputs without crashing.

  **Tracking:**
  - Start: `zoro viz-update step-3-4 in_progress`
  - Complete: `zoro viz-update step-3-4 completed`

  **Rules:**
  - [error-handling] Defensively handle partial LLM outputs and add targeted logging; never crash on missing fields—fallback with safe defaults and inspect returned payloads.

  ---

### 3: Backend Prompts:
**Status:** completed

- Create `backend/knowledge/prompts/refine_manual_rule.py` - LLM prompt for refinement

**Tracking:**
- Start: `zoro viz-update step-4 in_progress`
- Complete: `zoro viz-update step-4 completed`

**Rules:**
- [tooling] Use the OpenAI gpt-5 model for the agents.
- [prompt-engineering] Escape JSON braces in Python format strings within prompt templates to prevent KeyError during .format() calls.
- [parser-design] Preserve all original rule content during parsing; do not summarize or lose information.

---

  ### 3.1: Design refine_manual_rule prompt to clean title/content and output scores + reasoning
  **Status:** completed

  Instruct the LLM to: 5–8 word clear title, actionable content, confidence/decay with reasoning, and include context/evidence fields.

  **Tracking:**
  - Start: `zoro viz-update step-4-1 in_progress`
  - Complete: `zoro viz-update step-4-1 completed`

  **Rules:**
  - [knowledge-base-scoring] Use these definitions: Confidence = model certainty that the rule is relevant/well-founded; Decay = specificity to the current task (low for general rules, high for context-specific rules).
  - [data-model] Ensure LLM outputs include a 'context' field describing what the user and LLM were trying to build, in addition to 'evidence', within the dynamic reflection output schema.

  ---

  ### 3.2: Escape JSON braces and structure outputs for robust parsing
  **Status:** completed

  Embed JSON examples with doubled curly braces and strict required fields for safe .format() and parsing.

  **Tracking:**
  - Start: `zoro viz-update step-4-2 in_progress`
  - Complete: `zoro viz-update step-4-2 completed`

  ---

  ### 3.3: Require preservation of original content in refinements
  **Status:** completed

  Add guidance: retain all details, do not summarize away information when refining content.

  **Tracking:**
  - Start: `zoro viz-update step-4-3 in_progress`
  - Complete: `zoro viz-update step-4-3 completed`

  ---

  ### 3.4: Enforce output contract and field presence
  **Status:** completed

  Specify all required fields (title, content, confidence, decay, confidence_reasoning, decay_reasoning, context, evidence) and format as strict JSON.

  **Tracking:**
  - Start: `zoro viz-update step-4-4 in_progress`
  - Complete: `zoro viz-update step-4-4 completed`

  **Rules:**
  - [prompt-engineering-and-schemas] Ensure the LLM is provided all necessary inputs (e.g., per-item scores) and that prompts explicitly require all needed outputs; align schemas, prompts, and UI expectations.

  ---

