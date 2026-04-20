from __future__ import annotations

from datetime import datetime
import uuid

import click

from backend.assistant.plan_manager import load_plan, save_plan
from backend.cli.utils import detect_active_chat
from backend.globals.schemas import AuditEntry, RuleRef


@click.command()
@click.argument('step_id')
@click.argument('description')
@click.option('--name', default=None, help='Short rule name/label (defaults to "manual")')
@click.option('--source', default=None, help='Where rule came from (defaults to "manual")')
@click.option('--rule-id', default=None, help='Optional explicit rule_id (defaults to auto-generated)')
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .clinerules if not provided)')
def add_manual_rule(step_id, description, name, source, rule_id, chat_id):
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

    desc = (description or '').strip()
    if not desc:
        click.echo("❌ Rule description is empty")
        return

    rule_name = (name or '').strip() or "manual"
    rule_source = (source or '').strip() or "manual"

    # Generate id if not provided.
    rid = (rule_id or '').strip()
    if not rid:
        rid = str(uuid.uuid4())

    existing_ids = {r.rule_id for r in (node.rules or [])}
    if rid in existing_ids:
        click.echo(f"❌ Rule id already exists on {step_id}: {rid}")
        return

    node.rules.append(RuleRef(
        rule_id=rid,
        name=rule_name,
        description=desc,
        source=rule_source,
    ))

    node.audit.append(AuditEntry(
        at=datetime.now().isoformat(),
        who="ai",
        action="rule_added",
        details=f"{rid}: {rule_name}",
    ))

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)

    click.echo(f"✅ Added rule to {step_id}: {rid}")
