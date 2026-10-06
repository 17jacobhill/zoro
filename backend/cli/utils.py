
from pathlib import Path
import sys
from backend.utils import get_project_root
from backend.plan_paths import get_existing_plan_markdown_path


AGENTS_PROTOCOL_START = "<!-- ZORO-PROTOCOL:START -->"
AGENTS_PROTOCOL_END = "<!-- ZORO-PROTOCOL:END -->"


def resolve_file_path(file_path_str, default_dir="."):
    file_path = Path(file_path_str)
    
    # If just filename, look in default directory
    if not file_path.parent or file_path.parent == Path('.'):
        file_path = Path(default_dir) / file_path
    
    return file_path

def print_section(title, width=80):
    print("\n" + "=" * width)
    print(title)
    print("=" * width)

def create_zoro_directories():
    root = get_project_root()
    dirs = [
        root / ".zoro/visualization",
        root / ".zoro/rules",
        root / ".zoro/rules/unstructured",
        root / ".zoro/rules/structured",
    ]
    
    print("Creating directories...")
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created {dir_path}/")
    
    return dirs

def setup_gitignore():
    gitignore_path = Path(".gitignore")
    
    zoro_patterns = [
        "\n# Zoro learning system - user-specific data",
        ".zoro/",
        ".env"
    ]
    
    print("\nUpdating .gitignore...")
    
    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        patterns_to_add = [p for p in zoro_patterns if p.strip() and p not in existing]
        
        if patterns_to_add:
            with open(gitignore_path, 'a') as f:
                f.write('\n'.join(patterns_to_add) + '\n')
            print(f"  ✓ Updated .gitignore ({len(patterns_to_add)} patterns added)")
            return len(patterns_to_add)
        else:
            print("  ⊗ .gitignore already contains zoro patterns")
            return 0
    else:
        gitignore_path.write_text('\n'.join(zoro_patterns) + '\n')
        print("  ✓ Created .gitignore")
        return len(zoro_patterns)

def detect_active_chat():
    plan_path = get_existing_plan_markdown_path(Path.cwd())
    if not plan_path.exists():
        return None
    
    with open(plan_path) as f:
        first_line = f.readline()
        
        if '(' in first_line and ')' in first_line:
            chat_id = first_line.split('(')[-1].split(')')[0].strip()
            return chat_id
        
        title = first_line.replace('# Plan:', '').strip()
        chat_id = title.lower().replace(' ', '-').replace('_', '-')
        return chat_id


def load_template(template_name):
    template_path = Path(__file__).parent / "templates" / template_name
    
    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        sys.exit(1)
    
    return template_path.read_text()


def _extract_agents_guidance_body(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines).strip()


def render_agents_protocol_block() -> str:
    body = _extract_agents_guidance_body(load_template("agents_codex.md"))
    return "\n".join(
        [
            AGENTS_PROTOCOL_START,
            "## Zoro Workflow",
            "",
            body,
            AGENTS_PROTOCOL_END,
        ]
    ).strip()


def render_claude_protocol_block() -> str:
    return "\n".join(
        [
            AGENTS_PROTOCOL_START,
            "See @ZORO.md for the full Zoro workflow protocol.",
            AGENTS_PROTOCOL_END,
        ]
    )


def _ensure_marker_block_file(file_path, *, managed_block: str, fresh_content: str, legacy_template: str | None = None):
    """Shared idempotent marker-block insertion, extracted from
    ensure_agents_protocol_file's original body so ensure_claude_protocol_file
    can reuse the exact same START/END-marker logic with a different
    (much shorter) managed block and no legacy-template migration path —
    there was never a legacy CLAUDE.md template to migrate away from."""
    path = Path(file_path)

    if not path.exists():
        path.write_text(fresh_content, encoding="utf-8")
        print(f"  ✓ Created {file_path}")
        return True

    existing = path.read_text(encoding="utf-8")
    updated = existing

    if AGENTS_PROTOCOL_START in existing and AGENTS_PROTOCOL_END in existing:
        before, _, remainder = existing.partition(AGENTS_PROTOCOL_START)
        _, _, after = remainder.partition(AGENTS_PROTOCOL_END)
        separator = "\n\n" if before.strip() and not before.endswith("\n\n") else ""
        updated = f"{before.rstrip()}{separator}{managed_block}{after}"
    elif legacy_template and existing.strip() == legacy_template:
        updated = fresh_content
    elif legacy_template and existing.lstrip().startswith(legacy_template):
        suffix = existing.lstrip()[len(legacy_template):].lstrip("\n")
        updated = f"{managed_block}\n\n{suffix}" if suffix else f"{managed_block}\n"
    else:
        updated = f"{managed_block}\n\n{existing.lstrip()}"

    if updated != existing:
        path.write_text(updated, encoding="utf-8")
        print(f"  ✓ Updated {file_path} with Zoro protocol guidance")
        return True

    print(f"  ⊗ {file_path} already contains the Zoro protocol guidance")
    return False


def ensure_agents_protocol_file(file_path="AGENTS.md"):
    managed_block = render_agents_protocol_block()
    legacy_template = load_template("agents_codex.md").strip()
    fresh_content = f"# AGENTS.md\n\n{managed_block}\n"
    return _ensure_marker_block_file(file_path, managed_block=managed_block, fresh_content=fresh_content, legacy_template=legacy_template)


def ensure_claude_protocol_file(file_path="CLAUDE.md"):
    """Preserves an existing CLAUDE.md's content and inserts one short,
    idempotent managed block pointing to @ZORO.md — zoro init never
    touched CLAUDE.md before this (confirmed by reading the pre-change
    init.py and by direct testing in a disposable fixture). Unlike
    AGENTS.md there is no legacy template to migrate from, so this is a
    thin wrapper with no legacy_template argument."""
    managed_block = render_claude_protocol_block()
    fresh_content = f"# CLAUDE.md\n\n{managed_block}\n"
    return _ensure_marker_block_file(file_path, managed_block=managed_block, fresh_content=fresh_content)

def create_template_file(file_path, template_name, overwrite=False):
    path = Path(file_path)
    existed_before = path.exists()
    
    if overwrite or not existed_before:
        content = load_template(template_name)
        path.write_text(content)
        print(f"  ✓ {'Updated' if overwrite and existed_before else 'Created'} {file_path}")
        return True
    else:
        print(f"  ⊗ {file_path} already exists (skipped)")
        return False
