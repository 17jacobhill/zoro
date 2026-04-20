import sys
import json
from pathlib import Path
from backend.learner.chat_parser import ChatParser
from backend.learner.categorizer import TaskCategorizer
from backend.learner.learning import process_tasks_v3
from backend.globals.schemas import Task
from backend.cli.utils import resolve_file_path
from backend.utils import get_project_root


def cmd_process(args, load_config, mark_file_processed):
    try:
        user_name = args.user_name
        if not user_name:
            config = load_config()
            if not config or not config.get("user_name"):
                print("Error: No user name provided and no config found.")
                print("Run 'zoro init --user-name \"Your Name\"' first, or provide --user-name")
                sys.exit(1)
            user_name = config["user_name"]
        
        files_to_process = []
        
        if args.file_path:
            file_path = resolve_file_path(args.file_path)
            files_to_process = [file_path]
        else:
            chat_history_dir = get_project_root() / ".zoro/chat_history"
            if not chat_history_dir.exists():
                print("Error: .zoro/chat_history/ directory not found.")
                print("Run 'zoro init' first, or provide a file path.")
                sys.exit(1)
            
            md_files = list(chat_history_dir.glob("*.md"))
            json_files = list(chat_history_dir.glob("*.json"))
            all_files = md_files + json_files
            
            if not all_files:
                print("No .md or .json files found in .zoro/chat_history/")
                return
            
            config = load_config()
            processed_files = config.get("processed_files", []) if config else []
            
            files_to_process = [
                f for f in all_files 
                if f.name not in processed_files
            ]
            
            if not files_to_process:
                print("All files in .zoro/chat_history/ have been processed!")
                print(f"Processed files: {', '.join(processed_files)}")
                return
            
            print(f"Found {len(files_to_process)} unprocessed file(s):")
            for f in files_to_process:
                print(f"  - {f.name}")
            print()
        
        total_tasks = 0
        
        for file_path in files_to_process:
            chat_name = file_path.stem
            
            print("=" * 80)
            print(f"Processing: {file_path.name}")
            print(f"Chat: {chat_name}")
            print(f"User: {user_name}")
            print("=" * 80)
            
            parser = ChatParser(model='gpt-5', debug=False)
            task_dicts = parser.parse_file(str(file_path))
            
            if not task_dicts:
                print(f"No tasks generated from {file_path.name}\n")
                mark_file_processed(file_path.name)
                continue
            
            print(f"✓ Extracted {len(task_dicts)} task(s)\n")
            
            tasks = [Task(**task_dict) for task_dict in task_dicts]
            
            for i, task in enumerate(tasks, 1):
                desc_preview = task.description[:80] + '...' if len(task.description) > 80 else task.description
                print(f"  Task {i}: {desc_preview}")
            
            print(f"\nCategorizing {len(tasks)} task(s)...")
            categorizer = TaskCategorizer(model='gpt-5')
            categorized = categorizer.categorize_batch([t.model_dump() for t in tasks])
            
            for task, cat in zip(tasks, categorized):
                task.suggested_type = cat['type']
                task.description = cat['description']
            
            print(f"✓ Categorized {len(tasks)} task(s)")
            
            categorized_dir = get_project_root() / ".zoro" / "generated" / "categorized"
            categorized_dir.mkdir(parents=True, exist_ok=True)
            categorized_path = categorized_dir / f"{chat_name}.json"
            
            with open(categorized_path, 'w', encoding='utf-8') as f:
                json.dump({'tasks': [t.model_dump() for t in tasks]}, f, indent=2)
            
            print(f"✓ Saved categorized tasks to {categorized_path}")
            
            print(f"\nLearning from {len(tasks)} task(s)...")
            
            db = process_tasks_v3(tasks, user_name, chat_name, 'gpt-5')
            
            total_tasks += len(tasks)
            
            print(f"✓ Generated {len(tasks)} analyzed task(s)")
            
            mark_file_processed(file_path.name)
            print(f"✓ Marked {file_path.name} as processed\n")
        
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"Processed {len(files_to_process)} file(s)")
        print(f"✓ Saved {total_tasks} analyzed task(s) to .zoro/generated/analyzed/")
        print()
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
