import click
from backend.assistant.plan_manager import load_plan, save_plan
from backend.cli.utils import detect_active_chat
from backend.globals.schemas import AuditEntry
from datetime import datetime


@click.command()
@click.argument('step_id')
@click.argument('substep_id')
@click.argument('status', type=click.Choice(['pending', 'completed']))
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .clinerules if not provided)')
def update_substep(step_id, substep_id, status, chat_id):
    if not chat_id:
        chat_id = detect_active_chat()
    
    plan_path = f".zoro/generated/assistant/{chat_id}/plan.json"
    click.echo(f"📍 Chat ID: {chat_id}")
    click.echo(f"📄 Updating: {plan_path}")
    
    plan = load_plan(chat_id)
    if not plan:
        click.echo(f"❌ No plan found for chat: {chat_id}")
        return
    
    node = next((n for n in plan.nodes if n.id == step_id), None)
    if not node:
        click.echo(f"❌ Step {step_id} not found")
        return
    
    if not node.substeps:
        click.echo(f"❌ Step {step_id} has no substeps")
        return
    
    substep = next((s for s in node.substeps if s.get('id') == substep_id), None)
    if not substep:
        click.echo(f"❌ Substep {substep_id} not found in {step_id}")
        return
    
    substep['completed'] = (status == 'completed')

    node.audit.append(AuditEntry(
        at=datetime.now().isoformat(),
        who="ai",
        action=f"substep_changed: {substep_id} → {status}",
        details=""
    ))
    
    save_plan(chat_id, plan)
    
    click.echo(f"✅ Updated substep {substep_id} in {step_id}: {status}")
