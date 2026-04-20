
from pathlib import Path
import sys
from backend.utils import get_project_root
from backend.plan_paths import get_existing_plan_markdown_path

def resolve_file_path(file_path_str, default_dir=".zoro/chat_history"):
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
        root / ".zoro/chat_history",
        root / ".zoro/generated",
        root / ".zoro/generated/assistant",
        root / ".zoro/chat_visualizations",
        root / ".zoro/rules",
        root / ".zoro/rules/unstructured",
        root / ".zoro/rules/structured",
        root / ".rules",
        root / ".clinerules"
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
        ".rules/",
        ".clinerules/",
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
        return "default"
    
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
