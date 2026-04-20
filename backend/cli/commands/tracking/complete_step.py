import click
from backend.assistant.plan_manager import load_plan, save_plan
from backend.globals.schemas import AuditEntry
from backend.cli.utils import detect_active_chat
from datetime import datetime


@click.command()
@click.argument('step_id')
@click.option('--rules-used', default="", help='Comma-separated rule IDs')
@click.option('--note', default="", help='Optional note to add')
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .clinerules if not provided)')
def complete_step(step_id, rules_used, note, chat_id):
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
    node.status = "completed"
    
    if note:
        node.notes.append(note)
    
    details = ""
    if rules_used:
        rule_ids = [r.strip() for r in rules_used.split(',')]
        details = f"Rules applied: {', '.join(rule_ids)}"
    
    node.audit.append(AuditEntry(
        at=datetime.now().isoformat(),
        who="ai",
        action=f"completed (was {old_status})",
        details=details
    ))
    
    save_plan(chat_id, plan)
    
    click.echo(f"✅ Completed {step_id}")
    if note:
        click.echo(f"   Note added: {note}")
    if rules_used:
        click.echo(f"   Rules used: {rules_used}")
