import sys
from pathlib import Path
from datetime import datetime

from backend.assistant.planner import generate_plan
from backend.assistant.plan_manager import load_metadata, save_metadata, save_plan
from backend.globals.schemas import (
    Plan,
    PlanModel,
    Node,
    PlanEdge,
    ChatMetadata,
    HistoryEntry,
    RuleRef
)


def format_plan_as_markdown(plan: Plan) -> str:
    md = f"# Plan: {plan.task_query}\n\n"
    
    if plan.good_trajectories or plan.bad_trajectories:
        md += "## Analysis of Past Similar Tasks\n\n"
        
        if plan.good_trajectories:
            md += "### Good Trajectories\n"
            for i, traj in enumerate(plan.good_trajectories, 1):
                md += f"{i}. {traj}\n\n"
        
        if plan.bad_trajectories:
            md += "### Bad Trajectories\n"
            for i, traj in enumerate(plan.bad_trajectories, 1):
                md += f"{i}. {traj}\n\n"
    
    if plan.reasoning:
        md += "## Reasoning\n\n"
        md += f"{plan.reasoning}\n\n"
    
    if plan.steps:
        md += "---\n\n## Execution Plan\n\n"
        
        for step in plan.steps:
            md += f"### Step {step.step_number}: [{step.task_type}] {step.objective}\n\n"
            
            if step.substeps:
                md += "**Substeps:**\n"
                for i, substep in enumerate(step.substeps, 1):
                    md += f"{i}. {substep}\n"
                md += "\n"
            
            if step.rules:
                md += "**Rules to follow:**\n"
                for rule in step.rules:
                    md += f"- **[{rule.rule_id}]** {rule.rule}\n"
                    md += f"  Reasoning: {rule.reasoning}\n"
                md += "\n"
            
            if step.failure_point_watch:
                md += f"**Failure point watch:**\n⚠️ {step.failure_point_watch}\n\n"
            
            md += "---\n\n"
    
    return md


def convert_plan_to_model(plan: Plan) -> PlanModel:
    now = datetime.now().isoformat()
    
    nodes = []
    edges = []
    
    for i, step in enumerate(plan.steps):
        node_id = f"step-{step.step_number}"
        
        # Convert rules to RuleRef objects
        rule_refs = [
            RuleRef(
                rule_id=rule.rule_id,
                name=rule.rule,
                description=rule.rule,
                source=rule.reasoning
            )
            for rule in step.rules
        ]
        
        # Convert substeps to dict format if they exist
        substeps_data = None
        if step.substeps:
            substeps_data = [
                {"id": f"substep-{i}", "text": substep, "completed": False}
                for i, substep in enumerate(step.substeps, 1)
            ]
        
        # Build after_completing with pause instruction
        after_text = step.after_completing or ""
        if after_text and not after_text.endswith('\n'):
            after_text += "\n\n"
        
        pause_instruction = (
            "**⏸️ PAUSE HERE**\n"
            "- Present results to user with attempt_completion\n"
            "- Wait for explicit approval before proceeding to next step\n"
            "- Do NOT automatically continue to the next step"
        )
        
        after_text += pause_instruction
        
        node = Node(
            id=node_id,
            type=step.task_type if step.task_type in ["checking-with-user", "planning", "code-style", "debugging", "testing"] else "code-style",
            title=step.objective[:100],
            description=step.objective,
            status="pending",
            rules=rule_refs,
            notes=[],
            substeps=substeps_data,
            audit=[],
            before_starting=step.before_starting,
            after_completing=after_text
        )
        
        nodes.append(node)
        
        if i > 0:
            edge = PlanEdge(
                id=f"edge-{i}",
                from_node=f"step-{plan.steps[i-1].step_number}",
                to_node=node_id,
                type="sequence"
            )
            edges.append(edge)
    
    plan_model = PlanModel(
        created_at=now,
        updated_at=now,
        nodes=nodes,
        edges=edges,
        history=[
            HistoryEntry(
                at=now,
                action="created",
                details=f"Plan generated for: {plan.task_query}"
            )
        ]
    )
    
    return plan_model


def cmd_plan(args):
    try:
        query = args.query
        chat_id = args.chat_id
        
        tags = None
        match_mode = 'any'
        
        if hasattr(args, 'tags') and args.tags:
            tags_str = args.tags
            if '+' in tags_str:
                tags = [t.strip() for t in tags_str.split('+') if t.strip()]
                match_mode = 'all'
            elif ',' in tags_str:
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                match_mode = 'any'
            else:
                tags = [tags_str.strip()]
                match_mode = 'any'
        
        plan = generate_plan(query, model='gpt-5', tags=tags, match_mode=match_mode)
        
        markdown = format_plan_as_markdown(plan)
        
        output_path = args.output
        if not output_path and chat_id:
            output_path = ".rules/zoro_plan.md"
        
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"\n✓ Plan markdown written to {output_path}")
        
        if chat_id:
            metadata = load_metadata()
            
            existing_chat = next((c for c in metadata.chats if c.chat_id == chat_id), None)
            
            now = datetime.now().isoformat()
            
            if existing_chat:
                existing_chat.title = query[:100]
                existing_chat.updated_at = now
            else:
                new_chat = ChatMetadata(
                    chat_id=chat_id,
                    title=query[:100],
                    created_at=now,
                    updated_at=now
                )
                metadata.chats.append(new_chat)
            
            save_metadata(metadata)
            
            plan_model = convert_plan_to_model(plan)
            save_plan(chat_id, plan_model)
            
            print(f"✓ Plan saved to .zoro/generated/assistant/{chat_id}/plan.json")
            print(f"✓ Metadata updated")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
