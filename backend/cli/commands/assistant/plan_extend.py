import sys
import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.assistant.plan_manager import load_plan, save_plan, load_metadata, save_metadata
from backend.globals.models import get_default_provider
from backend.globals.schemas import Node, PlanEdge, AuditEntry, HistoryEntry, RuleRef
from backend.assistant.prompts.planning import PLAN_STRUCTURE_PROMPT
from backend.assistant.planner import (
    load_task_descriptions,
    load_tasks_by_ids,
    select_relevant_tasks_for_analysis,
    select_tasks_for_step,
    select_rules_for_step,
)
from backend.globals.schemas import Plan, get_schema


def strip_markdown_json(text):
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join([l for l in lines if not l.strip().startswith('```')])
    return text.strip()


def build_plan_summary(plan):
    summary_parts = []
    summary_parts.append(f"Total steps: {len(plan.nodes)}")
    
    if plan.nodes:
        last_step = max(plan.nodes, key=lambda n: int(n.id.split('-')[1]) if n.id.startswith('step-') else 0)
        summary_parts.append(f"Last step: {last_step.id} - {last_step.title}")
    
    node_types = {}
    for node in plan.nodes:
        node_types[node.type] = node_types.get(node.type, 0) + 1
    if node_types:
        summary_parts.append(f"Node types: {', '.join([f'{k}({v})' for k, v in node_types.items()])}")
    
    return "\n".join(summary_parts)


def build_good_bad_summaries(relevant_tasks):
    good_tasks = [t for t in relevant_tasks if getattr(t, "type", None) == "good"]
    bad_tasks = [t for t in relevant_tasks if getattr(t, "type", None) == "bad"]

    good_summaries = []
    for t in good_tasks:
        summary = f"Task: {t.task}\nDescription: {t.description}\nReasoning: {t.reasoning}"
        good_summaries.append(summary)

    bad_summaries = []
    for t in bad_tasks:
        summary = (
            f"Task: {t.task}\nDescription: {t.description}\nProblem: {t.problem}"
            f"\nFailure Point: {t.failure_point}\nGuardrail: {t.guardrail}"
        )
        bad_summaries.append(summary)

    good_text = "\n\n".join(good_summaries) if good_summaries else "None"
    bad_text = "\n\n".join(bad_summaries) if bad_summaries else "None"
    return good_text, bad_text


def build_recent_plan_context(plan, max_nodes: int = 5) -> str:
    numeric_nodes: list[tuple[int, object]] = []
    for n in plan.nodes:
        if isinstance(getattr(n, "id", None), str) and n.id.startswith("step-"):
            try:
                numeric_nodes.append((int(n.id.split("-")[1]), n))
            except Exception:
                continue

    numeric_nodes.sort(key=lambda t: t[0])
    recent = [n for _, n in numeric_nodes[-max_nodes:]]
    if not recent:
        return "None"

    parts = []
    for n in recent:
        parts.append(
            "\n".join(
                [
                    f"ID: {n.id}",
                    f"Type: {n.type}",
                    f"Title: {n.title}",
                    f"Description: {n.description}",
                ]
            )
        )
    return "\n\n".join(parts)


def cmd_plan_extend(args):
    try:
        feature_request = args.feature_request
        chat_id = args.chat_id
        
        metadata = load_metadata()
        chat = next((c for c in metadata.chats if c.chat_id == chat_id), None)
        
        if not chat:
            print(f"❌ Error: Chat ID '{chat_id}' not found")
            print("Run 'zoro plan' first to create a plan for this chat")
            sys.exit(1)
        
        plan = load_plan(chat_id)
        if not plan:
            print(f"❌ Error: No existing plan found for chat ID '{chat_id}'")
            sys.exit(1)
        
        print(f"🔧 Extending plan for: {chat.title}")
        print(f"📝 Feature request: {feature_request}")
        
        plan_summary = build_plan_summary(plan)
        print(f"\n📊 Current plan summary:")
        print(plan_summary)
        
        print(f"\n🤖 Calling LLM to generate new steps...")
        
        provider = get_default_provider()
        
        task_descriptions = load_task_descriptions()
        good_text = "None"
        bad_text = "None"
        if task_descriptions:
            try:
                relevant_task_ids = select_relevant_tasks_for_analysis(feature_request, task_descriptions, model='gpt-5')
                relevant_tasks = load_tasks_by_ids(relevant_task_ids)
                good_text, bad_text = build_good_bad_summaries(relevant_tasks)
            except Exception as e:
                print(f"⚠️  Warning: Could not load GOOD/BAD trajectories: {e}")

        recent_plan_context = build_recent_plan_context(plan, max_nodes=5)

        query_with_context = (
            f"{feature_request}\n\n"
            f"Current plan summary:\n{plan_summary}\n\n"
            f"Most recent existing steps (avoid duplicating these):\n{recent_plan_context}"
        )

        prompt = PLAN_STRUCTURE_PROMPT.format(
            query=query_with_context,
            good_tasks=good_text,
            bad_tasks=bad_text,
        )

        response = provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model='gpt-5',
            response_format=get_schema(Plan.model_json_schema()),
        )

        response_text = strip_markdown_json(response)

        try:
            plan_data = json.loads(response_text)
            generated_plan = Plan(**plan_data)
        except Exception as e:
            print("❌ Error: Failed to parse LLM plan JSON")
            print(f"Error: {e}")
            print(f"Response: {response_text[:200]}...")
            sys.exit(1)

        new_steps = []
        for s in generated_plan.steps:
            new_steps.append(
                {
                    "type": s.task_type,
                    "title": s.objective[:100],
                    "description": s.objective,
                    "rules": [],
                    "substeps": s.substeps or [],
                }
            )

        if not new_steps:
            print("❌ Error: LLM returned 0 steps")
            sys.exit(1)
        
        print(f"✅ Generated {len(new_steps)} new steps")
        
        # Stage 2: Per-step rule retrieval (same as zoro plan)
        print(f"\n🔍 Stage 2: Retrieving relevant rules for each step...")
        
        current_max_step = max(
            [int(n.id.split('-')[1]) for n in plan.nodes if n.id.startswith('step-')],
            default=0
        )
        
        last_node = next((n for n in plan.nodes if n.id == f"step-{current_max_step}"), None)
        
        now = datetime.now().isoformat()
        
        for i, step_data in enumerate(new_steps):
            new_step_num = current_max_step + i + 1
            new_node_id = f"step-{new_step_num}"
            
            # Select relevant rules for this step (2-stage approach)
            step_description = step_data['description']
            rule_refs = []
            
            if task_descriptions:
                # Stage 2a: Select relevant tasks for this step
                step_task_ids = select_tasks_for_step(step_description, task_descriptions, model='gpt-5')
                print(f"  Step {new_step_num}: Found {len(step_task_ids)} relevant tasks")
                
                # Stage 2b: Load tasks and extract all their rules
                step_tasks = load_tasks_by_ids(step_task_ids)
                all_step_rules = [rule for task in step_tasks for rule in task.rules]
                print(f"  Step {new_step_num}: Total {len(all_step_rules)} rules available")
                
                # Stage 2c: Select top rules for this step
                if all_step_rules:
                    selected_rules = select_rules_for_step(step_description, all_step_rules, limit=10, model='gpt-5')
                    # Convert RuleV2 to RuleRef
                    rule_refs = [
                        RuleRef(
                            rule_id=r.rule_id,
                            name=r.rule,
                            description=r.rule,
                            source=r.reasoning
                        ) for r in selected_rules
                    ]
                    print(f"  Step {new_step_num}: Selected {len(rule_refs)} rules")
            
            # Build workflow instructions
            prev_step_id = f"step-{current_max_step + i}" if i > 0 else f"step-{current_max_step}"
            before_starting = f"Review {prev_step_id} for context/outputs; Run: zoro update-step {new_node_id} in_progress"
            
            after_completing = (
                f"After completing: 1) Add notes: zoro add-note {new_node_id} 'what you learned'; "
                f"2) Complete: zoro complete-step {new_node_id} --rules-used 'rule-ids'; "
                f"3) Re-read plan: read_file .rules/zoro_plan.md\n\n"
                f"**⏸️ PAUSE HERE**\n"
                f"- Present results to user with attempt_completion\n"
                f"- Wait for explicit approval before proceeding to next step\n"
                f"- Do NOT automatically continue to the next step"
            )

            substeps_data = None
            if step_data.get("type") == "code-style":
                raw_substeps = step_data.get("substeps") or []
                if raw_substeps:
                    substeps_data = [
                        {"id": f"substep-{j}", "text": text, "completed": False}
                        for j, text in enumerate(raw_substeps, 1)
                    ]
            
            new_node = Node(
                id=new_node_id,
                type=step_data['type'],
                title=step_data['title'],
                description=step_data['description'],
                status="pending",
                rules=rule_refs,
                notes=[],
                substeps=substeps_data,
                before_starting=before_starting,
                after_completing=after_completing,
                audit=[
                    AuditEntry(
                        at=now,
                        who="ai",
                        action="created",
                        details=f"Generated by plan-extend for: {feature_request}"
                    )
                ]
            )
            
            plan.nodes.append(new_node)
            
            if i == 0 and last_node:
                new_edge = PlanEdge(
                    id=f"edge-{uuid.uuid4().hex[:8]}",
                    from_node=last_node.id,
                    to_node=new_node_id,
                    type="sequence"
                )
                plan.edges.append(new_edge)
            elif i > 0:
                prev_node_id = f"step-{current_max_step + i}"
                new_edge = PlanEdge(
                    id=f"edge-{uuid.uuid4().hex[:8]}",
                    from_node=prev_node_id,
                    to_node=new_node_id,
                    type="sequence"
                )
                plan.edges.append(new_edge)
            
            print(f"  ✓ {new_node_id}: [{step_data['type']}] {step_data['title']}")
        
        plan.updated_at = now
        plan.history.append(HistoryEntry(
            at=now,
            action="extended",
            details=f"Added {len(new_steps)} steps via plan-extend: {feature_request}"
        ))
        
        save_plan(chat_id, plan)
        
        chat.updated_at = now
        save_metadata(metadata)
        
        print(f"\n✅ Plan extended with {len(new_steps)} new steps")
        print(f"✅ Plan saved to .zoro/generated/assistant/{chat_id}/plan.json")
        print(f"✅ Markdown updated at .rules/zoro_plan.md")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
