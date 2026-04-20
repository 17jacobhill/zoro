import click
from backend.assistant.plan_manager import load_plan, save_plan
from backend.globals.schemas import AuditEntry
from backend.cli.utils import detect_active_chat
from datetime import datetime


@click.command()
@click.argument('step_id')
@click.argument('status', type=click.Choice(['pending', 'in_progress', 'completed', 'blocked']))
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .clinerules if not provided)')
def update_step(step_id, status, chat_id):
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
    
    old_status = node.status
    node.status = status
    
    node.audit.append(AuditEntry(
        at=datetime.now().isoformat(),
        who="ai",
        action=f"status_changed: {old_status} → {status}",
        details=""
    ))
    
    save_plan(chat_id, plan)
    
    click.echo(f"✅ Updated {step_id}: {old_status} → {status}")
