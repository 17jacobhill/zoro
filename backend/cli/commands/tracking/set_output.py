import sys
from pathlib import Path
from backend.assistant.plan_manager import load_plan, save_plan, get_chat_id_from_plan_md

def set_output(step_id: str, output: str, chat_id: str = None):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
        if not chat_id:
            print("❌ Error: No chat_id found in .rules/zoro_plan.md")
            print("Please specify --chat-id explicitly")
            sys.exit(1)
    
    plan = load_plan(chat_id)
    if not plan:
        print(f"❌ Error: No plan found for chat_id '{chat_id}'")
        sys.exit(1)
    
    node = next((n for n in plan.nodes if n.id == step_id), None)
    if not node:
        print(f"❌ Error: Node '{step_id}' not found in plan")
        sys.exit(1)
    
    node.output = output
    save_plan(chat_id, plan)
    
    print(f"✅ Set output for {step_id}")
    print(f"✅ Plan updated at .rules/zoro_plan.md")
