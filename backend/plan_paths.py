"""Path helpers for the canonical shared plan markdown file.

`backend/plan_paths.py` is intentionally small and only covers:
- `.zoro/CURRENT_PLAN.md` (project-level plan markdown shown to agents)

Per-visualization JSON artifacts (session/runtime/plan/evidence) live in:
- `backend/visualization/paths.py`
"""

from pathlib import Path


PLAN_MARKDOWN_FILENAME = "CURRENT_PLAN.md"
PRIMARY_PLAN_DIRNAME = ".zoro"


def get_plan_markdown_path(base: Path | None = None) -> Path:
    root = base or Path.cwd()
    return root / PRIMARY_PLAN_DIRNAME / PLAN_MARKDOWN_FILENAME


def get_existing_plan_markdown_path(base: Path | None = None) -> Path:
    return get_plan_markdown_path(base)
