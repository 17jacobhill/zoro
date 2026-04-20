from pathlib import Path
from backend.globals.tag_registry import TagRegistry
from backend.utils import get_project_root


def cmd_tag_chat(args):
    chat_name = args.chat
    add_tags = [t.strip() for t in args.add.split(',') if t.strip()] if args.add else []
    remove_tags = [t.strip() for t in args.remove.split(',') if t.strip()] if args.remove else []
    
    if not add_tags and not remove_tags:
        print("❌ Error: Must specify --add or --remove (or both)")
        return
    
    root = get_project_root()
    categorized_path = root / ".zoro" / "generated" / "categorized" / f"{chat_name}.json"
    analyzed_path = root / ".zoro" / "generated" / "analyzed" / f"{chat_name}.json"
    
    if not categorized_path.exists() and not analyzed_path.exists():
        print(f"❌ Error: Chat '{chat_name}' not found")
        print(f"   Expected: {categorized_path} or {analyzed_path}")
        return
    
    registry = TagRegistry('learner_tags.json')
    
    if add_tags:
        registry.add_tags(chat_name, add_tags)
        print(f"✅ Added {len(add_tags)} tag{'s' if len(add_tags) > 1 else ''} to '{chat_name}':")
        for tag in add_tags:
            print(f"   + {tag}")
    
    if remove_tags:
        registry.remove_tags(chat_name, remove_tags)
        print(f"✅ Removed {len(remove_tags)} tag{'s' if len(remove_tags) > 1 else ''} from '{chat_name}':")
        for tag in remove_tags:
            print(f"   - {tag}")
    
    current_tags = registry.get_tags(chat_name)
    print(f"\n📋 Current tags for '{chat_name}': {', '.join(current_tags) if current_tags else '(none)'}")
