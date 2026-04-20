
import sys
import json
import uuid
from pathlib import Path
from backend.learner.chat_parser import ChatParser
from backend.learner.learning import process_tasks_v3
from backend.globals.schemas import Task
from backend.cli.utils import resolve_file_path
from backend.utils import get_project_root

def cmd_observation_eval(args, load_config):
    try:
        user_name = args.user_name
        if not user_name:
            config = load_config()
            if not config or not config.get("user_name"):
                print("Error: No user name provided and no config found.")
                print("Run 'zoro init --user-name \"Your Name\"' first, or provide --user-name")
                sys.exit(1)
            user_name = config["user_name"]
        
        file_path = resolve_file_path(args.file_path)
        chat_name = file_path.stem

        # Determine output directory based on flags
        base_output_dir = get_project_root() / ".zoro/generated/observation_eval"
        dir_name = ""
        if args.rules_only:
            dir_name += "rules_only"
        else:
            dir_name += "trajectory"
        
        if args.no_task_chunking:
            dir_name += "_no_chunking"
        else:
            dir_name += "_chunking"

        if args.no_evidence:
            dir_name += "_no_evidence"
        elif not args.rules_only:
            dir_name += "_evidence"
        
        output_dir = base_output_dir / dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 80)
        print(f"Running Observation Evaluation")
        print(f"File: {file_path.name}")
        print(f"Chat: {chat_name}")
        print(f"User: {user_name}")
        print(f"No Task Chunking: {args.no_task_chunking}")
        print(f"No Evidence: {args.no_evidence}")
        print(f"Rules Only: {args.rules_only}")
        print(f"Output Directory: {output_dir}")
        print("=" * 80)

        tasks = []
        if args.no_task_chunking:
            print("Processing file as a single task (no task chunking)...")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tasks.append(Task(
                task_id=str(uuid.uuid4()),
                description=f"Full analysis of {chat_name}",
                raw_data=content
            ))
        else:
            print("Parsing file into tasks (task chunking enabled)...")
            parser = ChatParser(model='gpt-5', debug=False)
            task_dicts = parser.parse_file(str(file_path))
            if not task_dicts:
                print(f"No tasks generated from {file_path.name}")
                return
            tasks = [Task(**task_dict) for task_dict in task_dicts]

        print(f"✓ Extracted {len(tasks)} task(s)\n")
        
        # Override the db_path in the learner to save to our custom location
        original_learner_init = __import__('backend.learner.learning').learner.learning.TaskLearner.__init__
        
        def custom_init(self, user_name, chat_name, model='gpt-5', use_evidence_prompt=True, no_task_chunking=False, rules_only=False):
            original_learner_init(self, user_name, chat_name, model, use_evidence_prompt, no_task_chunking, rules_only)
            self._analyzed_dir = output_dir
            self._db_path = self._analyzed_dir / f"{chat_name}.json"

        __import__('backend.learner.learning').learner.learning.TaskLearner.__init__ = custom_init

        print(f"Learning from {len(tasks)} task(s)...")
        db = process_tasks_v3(tasks, user_name, chat_name, 'gpt-5', use_evidence_prompt=not args.no_evidence, no_task_chunking=args.no_task_chunking, rules_only=args.rules_only)
        
        # Restore original init
        __import__('backend.learner.learning').learner.learning.TaskLearner.__init__ = original_learner_init

        print(f"✓ Generated {len(db.analyzed_tasks)} analyzed task(s)")
        print(f"✓ Saved results to {output_dir / f'{chat_name}.json'}")
        print("\nEvaluation complete.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
