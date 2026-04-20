from backend.globals.tag_registry import TagRegistry


def cmd_list_tags(args):
    registry = TagRegistry('learner_tags.json')
    tag_counts = registry.list_all_tags()
    
    if not tag_counts:
        print("No tags found.")
        return
    
    print("\n📋 Tags (alphabetically):\n")
    for tag, count in tag_counts.items():
        print(f"  • {tag} ({count} chat{'s' if count > 1 else ''})")
    
    print(f"\nTotal: {len(tag_counts)} tag{'s' if len(tag_counts) > 1 else ''}")
