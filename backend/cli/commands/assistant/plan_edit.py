import sys
import re
import json
from pathlib import Path
from datetime import datetime

from backend.assistant.plan_manager import load_metadata, save_metadata, load_plan, save_plan
from backend.globals.models import get_default_provider
from backend.globals.schemas import HistoryEntry
from backend.assistant.prompts.plan_iter import REWRITE_STEP_PROMPT, REWRITE_SUBSTEPS_PROMPT, CREATE_SUBSTEPS_PROMPT


NUMERIC_STEP_ID_RE = re.compile(r"^step-(\d+)$")


def rewrite_step_with_llm(original_description, user_query, model='gpt-5'):
    provider = get_default_provider()
    
    prompt = REWRITE_STEP_PROMPT.format(
        original_description=original_description,
        user_query=user_query
    )
    
    try:
        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model
        )
        return response.strip()
    except Exception as e:
        print(f"      ⚠️  Warning: Could not rewrite step via LLM: {e}")
        return original_description


def rewrite_substeps_with_llm(substeps, new_description, user_query, model='gpt-5'):
    provider = get_default_provider()

    completed_by_id = {s.get('id'): bool(s.get('completed')) for s in substeps if isinstance(s, dict)}
    ordered_ids = [s.get('id') for s in substeps if isinstance(s, dict) and s.get('id')]
    
    substeps_text = "\n".join([
        f"{s.get('id', f'substep-{i+1}')}: {s.get('text', '')}" for i, s in enumerate(substeps)
    ])
    
    prompt = REWRITE_SUBSTEPS_PROMPT.format(
        substeps_text=substeps_text,
        new_description=new_description,
        user_query=user_query
    )
    
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )
    
    response_text = response.strip()
    if response_text.startswith('```'):
        lines = response_text.split('\n')
        response_text = '\n'.join([l for l in lines if not l.strip().startswith('```')])
    
    new_substeps_raw = json.loads(response_text.strip())
    
    # Transform to proper {id, text, completed} format.
    # Preserve completion state where possible.
    if isinstance(new_substeps_raw, list):
        new_substeps = []
        for i, substep_item in enumerate(new_substeps_raw):
            # Handle both string and dict formats
            if isinstance(substep_item, str):
                stable_id = ordered_ids[i] if i < len(ordered_ids) else f"substep-{i+1}"
                new_substeps.append({
                    "id": stable_id,
                    "text": substep_item,
                    "completed": completed_by_id.get(stable_id, False)
                })
            elif isinstance(substep_item, dict):
                # Already has correct structure or partial structure
                if 'text' in substep_item:
                    stable_id = substep_item.get("id")
                    if not stable_id:
                        stable_id = ordered_ids[i] if i < len(ordered_ids) else f"substep-{i+1}"
                    new_substeps.append({
                        "id": stable_id,
                        "text": substep_item["text"],
                        "completed": completed_by_id.get(stable_id, bool(substep_item.get("completed", False)))
                    })
        return new_substeps
    
    return []


def create_substeps_with_llm(description, model='gpt-5'):
    provider = get_default_provider()

    prompt = CREATE_SUBSTEPS_PROMPT.format(description=description)

    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model
    )

    response_text = response.strip()
    if response_text.startswith('```'):
        lines = response_text.split('\n')
        response_text = '\n'.join([l for l in lines if not l.strip().startswith('```')])

    raw = json.loads(response_text.strip())

    if not isinstance(raw, list):
        return []

    substeps = []
    for i, item in enumerate(raw, 1):
        if isinstance(item, str):
            substeps.append({"id": f"substep-{i}", "text": item, "completed": False})
        elif isinstance(item, dict) and 'text' in item:
            substeps.append({
                "id": item.get('id', f"substep-{i}"),
                "text": item['text'],
                "completed": item.get('completed', False)
            })

    return substeps


def create_substeps_fallback(description: str) -> list[dict]:
    return [
        {"id": "substep-1", "text": "Implement the smallest core change needed for this step.", "completed": False},
        {"id": "substep-2", "text": "Handle edge cases / backward compatibility.", "completed": False},
        {"id": "substep-3", "text": "Add a quick smoke test and verify output artifacts.", "completed": False},
    ]


def cmd_plan_edit(args):
    try:
        query = args.query
        chat_id = args.chat_id
        
        metadata = load_metadata()
        chat = next((c for c in metadata.chats if c.chat_id == chat_id), None)
        
        if not chat:
            print(f"❌ Error: Chat ID '{chat_id}' not found")
            print("Run 'zoro plan' first to create a plan for this chat")
            sys.exit(1)
        
        print(f"Refining plan for chat: {chat.title}")
        
        plan = load_plan(chat_id)
        if not plan:
            print(f"❌ Error: No existing plan found for chat ID '{chat_id}'")
            sys.exit(1)

        from_step = getattr(args, "from_step", None)
        if from_step is None:
            print("❌ Error: Missing --from-step")
            print(f"\nUsage:\n  zoro plan-iter 'refine steps' --chat-id {chat_id} --from-step 4")
            sys.exit(1)

        numeric_nodes: list[tuple[int, object]] = []
        for n in plan.nodes:
            m = NUMERIC_STEP_ID_RE.match(n.id)
            if not m:
                continue
            numeric_nodes.append((int(m.group(1)), n))

        targets = [(num, n) for num, n in numeric_nodes if num >= from_step]
        targets.sort(key=lambda t: t[0])

        if not targets:
            print(f"❌ Error: No numeric steps found >= {from_step}")
            sys.exit(1)

        max_rewrites = 10
        if len(targets) > max_rewrites:
            print(f"❌ Error: Refusing to rewrite {len(targets)} steps (cap={max_rewrites}).")
            print("Split into multiple runs or raise the cap in code if truly needed.")
            sys.exit(1)

        print(f"🔧 Rewriting steps step-{from_step} → step-{targets[-1][0]} ({len(targets)} step(s))")

        step_nums = [str(num) for num, _ in targets]
        
        modified_count = 0
        for num, node in targets:
            step_id = f"step-{num}"
            print(f"  ✏️  Rewriting {step_id}...")
            new_description = rewrite_step_with_llm(node.description, query)
            node.description = new_description
            
            if node.type == "code-style":
                if node.substeps and len(node.substeps) > 0:
                    print(f"      🔧 Updating {len(node.substeps)} substeps...")
                    try:
                        new_substeps = rewrite_substeps_with_llm(node.substeps, new_description, query)
                        node.substeps = new_substeps
                        print(f"      ✅ Substeps updated")
                    except Exception as e:
                        print(f"      ⚠️  Warning: Could not update substeps: {e}")
                else:
                    print("      🧩 No substeps found; generating substeps...")
                    try:
                        generated_substeps = create_substeps_with_llm(new_description)
                        if generated_substeps:
                            node.substeps = generated_substeps
                            print(f"      ✅ Generated {len(generated_substeps)} substeps")
                        else:
                            print("      ⚠️  Warning: LLM returned 0 substeps")
                    except Exception as e:
                        print(f"      ⚠️  Warning: Could not generate substeps: {e}")
                        node.substeps = create_substeps_fallback(new_description)
                        print(f"      ✅ Fallback: created {len(node.substeps)} generic substeps")
            
            modified_count += 1
            print(f"  ✅ {step_id} updated")
        
        if modified_count == 0:
            print(f"❌ Error: No steps were rewritten")
            sys.exit(1)
        
        now = datetime.now().isoformat()
        plan.updated_at = now
        plan.history.append(HistoryEntry(
            at=now,
            action="modified",
            details=f"Updated steps {', '.join(step_nums)} based on: {query}"
        ))
        
        save_plan(chat_id, plan)
        
        print(f"\n✅ Modified {modified_count} step(s)")
        print(f"✅ Plan saved to .zoro/generated/assistant/{chat_id}/plan.json")
        print(f"✅ Markdown updated at .rules/zoro_plan.md")
        
        now = datetime.now().isoformat()
        chat.updated_at = now
        save_metadata(metadata)
        
        if args.output:
            plan_for_markdown = load_plan(chat_id)
            markdown = f"# Modified Steps: {', '.join(step_nums)}\n\n{query}\n\n"
            for num_str in step_nums:
                step_id = f"step-{num_str}"
                node = next((n for n in plan_for_markdown.nodes if n.id == step_id), None)
                if node:
                    markdown += f"## {step_id}\n\n{node.description}\n\n"
            
            output_path = Path(args.output)
            
            if output_path.exists():
                with open(output_path, 'a', encoding='utf-8') as f:
                    f.write("\n\n---\n\n")
                    f.write(f"# Refinement: {query}\n\n")
                    f.write(markdown)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown)
            
            print(f"✅ Plan markdown written to {args.output}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
