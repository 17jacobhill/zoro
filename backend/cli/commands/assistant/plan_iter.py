import sys
import json
from datetime import datetime

from backend.assistant.plan_manager import load_metadata, save_metadata, load_plan, save_plan
from backend.assistant.planner import load_task_descriptions, load_tasks_by_ids, select_tasks_for_step, select_rules_for_step
from backend.globals.models import get_default_provider
from backend.globals.schemas import HistoryEntry, Node, get_schema
from backend.assistant.prompts.plan_iter import GENERATE_CODE_STYLE_STEPS_PROMPT


def generate_code_style_steps(query, strategy, from_step, model='gpt-5'):
    provider = get_default_provider()
    
    # Get good/bad trajectory analysis
    from backend.assistant.planner import select_relevant_tasks_for_analysis, load_all_analyzed_tasks
    
    task_descriptions = load_task_descriptions()
    if not task_descriptions:
        print("⚠️  Warning: No tasks found in database for trajectory analysis")
        good_text = "None"
        bad_text = "None"
    else:
        relevant_task_ids = select_relevant_tasks_for_analysis(query, task_descriptions, model)
        relevant_tasks = load_tasks_by_ids(relevant_task_ids)
        
        good_tasks = [t for t in relevant_tasks if t.type == "good"]
        bad_tasks = [t for t in relevant_tasks if t.type == "bad"]
        
        good_summaries = []
        for t in good_tasks:
            summary = f"Task: {t.task}\nDescription: {t.description}\nReasoning: {t.reasoning}"
            good_summaries.append(summary)
        
        bad_summaries = []
        for t in bad_tasks:
            summary = f"Task: {t.task}\nDescription: {t.description}\nProblem: {t.problem}\nFailure Point: {t.failure_point}\nGuardrail: {t.guardrail}"
            bad_summaries.append(summary)
        
        good_text = "\n\n".join(good_summaries) if good_summaries else "None"
        bad_text = "\n\n".join(bad_summaries) if bad_summaries else "None"
    
    # Format prompt with dynamic step numbers
    prev_step = from_step - 1
    prompt = GENERATE_CODE_STYLE_STEPS_PROMPT.format(
        query=query,
        strategy=strategy,
        good_tasks=good_text,
        bad_tasks=bad_text,
        start_step_number=from_step,
        prev_step=prev_step
    )
    
    # Call LLM with structured output
    from backend.globals.schemas import Plan
    response = provider.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        response_format=get_schema(Plan.model_json_schema())
    )
    
    plan_data = json.loads(response)
    return plan_data


def cmd_plan_iter(args):
    try:
        query = args.query
        chat_id = args.chat_id
        
        metadata = load_metadata()
        chat = next((c for c in metadata.chats if c.chat_id == chat_id), None)
        
        if not chat:
            print(f"❌ Error: Chat ID '{chat_id}' not found")
            print("Run 'zoro plan' first to create a plan for this chat")
            sys.exit(1)
        
        print(f"Generating code-style steps for chat: {chat.title}")
        
        plan = load_plan(chat_id)
        if not plan:
            print(f"❌ Error: No existing plan found for chat ID '{chat_id}'")
            sys.exit(1)

        from_step = getattr(args, "from_step", None)
        if from_step is None:
            print("❌ Error: Missing --from-step")
            print(f"\nUsage:\n  zoro plan-iter 'implement strategy' --chat-id {chat_id} --from-step 3")
            sys.exit(1)
        
        # Check if step already exists
        existing_ids = {node.id for node in plan.nodes}
        if f"step-{from_step}" in existing_ids:
            print(f"❌ Error: step-{from_step} already exists in plan")
            print(f"Use 'zoro plan-edit' to modify existing steps")
            sys.exit(1)
        
        print(f"\n🔧 Generating code-style steps starting from step-{from_step}...")
        
        planning_node = next((n for n in plan.nodes if n.type == "planning"), None)
        if planning_node and planning_node.output:
            strategy = planning_node.output
            print(f"  📝 Using strategy from planning node:")
            print(f"     {strategy[:200]}...")
        else:
            strategy = f"Strategy from CLI: {query}"
            print(f"  ⚠️  No planning output found, using CLI query")
        
        # Generate steps using LLM
        plan_data = generate_code_style_steps(
            query=query,
            strategy=strategy,
            from_step=from_step,
            model='gpt-5'
        )
        
        print(f"  ✅ Generated {len(plan_data['steps'])} code-style steps")
        
        # Convert steps to PlanNode objects
        task_descriptions = load_task_descriptions()
        new_nodes = []
        
        for step_data in plan_data['steps']:
            # Convert substeps from strings to objects
            substeps_objs = []
            if step_data.get('substeps'):
                for i, substep_text in enumerate(step_data['substeps'], 1):
                    if isinstance(substep_text, str):
                        substeps_objs.append({
                            "id": f"substep-{i}",
                            "text": substep_text,
                            "completed": False
                        })
                    elif isinstance(substep_text, dict):
                        substeps_objs.append(substep_text)
            
            node = Node(
                id=f"step-{step_data['step_number']}",
                type=step_data['task_type'],
                title=step_data['objective'][:100],  # Use first 100 chars of objective as title
                description=step_data['objective'],
                status="pending",
                rules=[],  # Will be filled below
                substeps=substeps_objs,
                before_starting=step_data.get('before_starting', ''),
                after_completing=step_data.get('after_completing', '')
            )
            
            new_nodes.append(node)
        
        # Stage 2: Add rules to each new step
        print("\n🔍 Adding rules to generated steps...")
        for node in new_nodes:
            print(f"  {node.id}: {node.description[:60]}...")
            
            step_task_ids = select_tasks_for_step(node.description, task_descriptions, model='gpt-5')
            print(f"    Found {len(step_task_ids)} relevant tasks")
            
            step_tasks = load_tasks_by_ids(step_task_ids)
            all_step_rules = [rule for task in step_tasks for rule in task.rules]
            print(f"    Total {len(all_step_rules)} rules available")
            
            if all_step_rules:
                selected_rules_v2 = select_rules_for_step(node.description, all_step_rules, limit=10, model='gpt-5')
                # Convert RuleV2 to RuleRef
                from backend.globals.schemas import RuleRef
                node.rules = [
                    RuleRef(
                        rule_id=r.rule_id,
                        name=r.rule,  # Use full rule text as name
                        description=r.rule,
                        source=r.reasoning
                    )
                    for r in selected_rules_v2
                ]
                print(f"    Selected {len(node.rules)} rules")
            else:
                print(f"    No rules available")
        
        # Add new nodes to plan
        plan.nodes.extend(new_nodes)
        
        # Generate edges connecting new steps
        from backend.globals.schemas import PlanEdge
        for i, node in enumerate(new_nodes):
            if i == 0:
                # Connect previous step to first new step
                prev_step_id = f"step-{from_step - 1}"
                edge_id = f"edge-{from_step - 1}-{from_step}"
                plan.edges.append(PlanEdge(
                    id=edge_id,
                    from_node=prev_step_id,
                    to_node=node.id,
                    type="sequence"
                ))
            if i < len(new_nodes) - 1:
                # Connect consecutive new steps
                current_num = from_step + i
                next_num = from_step + i + 1
                edge_id = f"edge-{current_num}-{next_num}"
                plan.edges.append(PlanEdge(
                    id=edge_id,
                    from_node=node.id,
                    to_node=new_nodes[i+1].id,
                    type="sequence"
                ))
        
        # Update plan metadata
        now = datetime.now().isoformat()
        plan.updated_at = now
        plan.history.append(HistoryEntry(
            at=now,
            action="extended",
            details=f"Added {len(new_nodes)} code-style steps starting from step-{from_step}: {query}"
        ))
        
        # Save plan
        save_plan(chat_id, plan)
        
        print(f"\n✅ Added {len(new_nodes)} code-style steps to plan")
        print(f"✅ Plan saved to .zoro/generated/assistant/{chat_id}/plan.json")
        print(f"✅ Markdown updated at .rules/zoro_plan.md")
        
        # Update chat metadata
        chat.updated_at = now
        save_metadata(metadata)
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
