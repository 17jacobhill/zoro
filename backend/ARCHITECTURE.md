# Backend Architecture

This document describes both the current architecture and the target
architecture so we can make intentional refactors without drifting behavior.

## Current Architecture

### 1) App bootstrap layer
- `api.py`
- Builds Flask app, configures CORS/logging, and registers API blueprints.

### 2) HTTP route layer
- `routes/visualization_api/*`
- `routes/knowledge_api/*`
- Handles request parsing, orchestration, and response formatting.

### 3) Domain/service layer
- `visualization/services/*`
- `knowledge/services/*`
- Contains persistence utilities and business workflows used by routes.

### 4) Prompt/schema layer
- `visualization/prompts/*`, `knowledge/prompts/*`
- `visualization/schemas.py`, `knowledge/schemas.py`, `globals/schemas.py`
- LLM prompt contracts and typed data structures.

### 5) Path helper layer
- `plan_paths.py`
  - canonical project-level markdown: `.zoro/CURRENT_PLAN.md`
- `visualization/paths.py`
  - per-chat JSON artifacts under `.zoro/visualization/<chat_id>/...`
- `knowledge/paths.py`
  - knowledge artifact paths under `.zoro/rules/...`

### 6) CLI layer
- `cli/cli.py`
- `cli/commands/*`
- `cli/templates/*`
- Initializes protocol files/config and drives step/rule verification workflow.

## Why `plan_paths.py` and `visualization/paths.py` both exist

- `plan_paths.py` handles one shared, human-facing markdown file.
- `visualization/paths.py` handles per-session machine state.

This keeps global state and session state separate.

## Known Exceptions (Current Reality)

These are intentional technical-debt notes, not failures:

1. `routes/visualization_api/plans.py` is still a large orchestration module.
2. Some route files still contain non-trivial workflow logic.
3. Compatibility shims remain during migrations
   (example: `routes/knowledge_api/storage.py` re-exports from
   `knowledge/services/storage.py`).

## Target Architecture

1. Route modules are thin transport adapters:
- parse request
- call service/orchestrator
- shape response

2. Business logic lives in service/orchestrator modules:
- visualization orchestration in `visualization/services/*`
- knowledge orchestration in `knowledge/services/*`

3. All filesystem paths are centralized through path helper modules.

4. Backward-compatibility shims are removed after downstream imports are
updated and covered by tests.

## Conventions

1. Add new endpoints in `routes/*_api/*`.
2. Put non-trivial logic in `visualization/services/*` or `knowledge/services/*`.
3. Keep route modules deterministic and focused on HTTP concerns.
4. Add/adjust path helpers instead of hardcoding `.zoro/...` paths.
5. Add tests for behavior before and after structural refactors.

## Migration Plan

### Completed
1. Removed blueprint shim indirection from `api.py` to route shim modules.
2. Introduced `knowledge/services/storage.py`.
3. Added `knowledge/paths.py`.
4. Kept `routes/knowledge_api/storage.py` as a compatibility re-export shim.

### Next
1. Split `routes/visualization_api/plans.py` into focused route modules:
- extraction/enrichment/prepare-play
- plan CRUD/mutations
- rule operations

2. Extract shared orchestration helpers into
`visualization/services/plan_orchestrator.py`.

3. Add explicit response builders (or DTO helpers) for visualization endpoints.

### Finalize
1. Remove compatibility shims once imports are migrated and tests are stable.
2. Lock architecture expectations with focused module-boundary tests.
