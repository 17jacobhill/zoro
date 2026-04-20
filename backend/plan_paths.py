from pathlib import Path


PLAN_MARKDOWN_FILENAME = "zoro_plan.md"
PRIMARY_PLAN_DIRNAME = ".rules"
LEGACY_PLAN_DIRNAME = ".clinerules"


def get_plan_markdown_path(base: Path | None = None) -> Path:
    root = base or Path.cwd()
    return root / PRIMARY_PLAN_DIRNAME / PLAN_MARKDOWN_FILENAME


def get_legacy_plan_markdown_path(base: Path | None = None) -> Path:
    root = base or Path.cwd()
    return root / LEGACY_PLAN_DIRNAME / PLAN_MARKDOWN_FILENAME


def get_existing_plan_markdown_path(base: Path | None = None) -> Path:
    primary = get_plan_markdown_path(base)
    if primary.exists():
        return primary

    legacy = get_legacy_plan_markdown_path(base)
    if legacy.exists():
        return legacy

    return primary
