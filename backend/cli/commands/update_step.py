import click

from backend.visualization.services.evidence_store import (
    get_rule_verification_records_for_item,
    load_evidence_document,
)
from backend.visualization.services.visualization_manager import update_item_status, _load_metadata
from backend.visualization.services.plan_tracker import (
    collect_rules_for_item,
    find_item_by_id,
    get_chat_id_from_plan_md,
    get_next_pending_leaf_item,
    load_plan_data,
)
from backend.visualization.services.plan_validator import validate_item_can_start, validate_item_can_complete
from backend.utils import get_enforcement_mode


def get_previous_leaf_item(plan_data, target_item_id):
    def get_all_leaf_items(items, leaves=None):
        if leaves is None:
            leaves = []

        for item in items:
            if item.get('children'):
                get_all_leaf_items(item['children'], leaves)
            else:
                leaves.append(item)

        return leaves

    items = plan_data.get('plan', {}).get('items', [])
    all_leaves = get_all_leaf_items(items)

    for idx, item in enumerate(all_leaves):
        if item.get('id') == target_item_id:
            if idx == 0:
                return None
            return all_leaves[idx - 1]

    return None


def check_verification_requirements(chat_id, plan_data, item_id, mode='verification'):
    issues = []

    all_rules = collect_rules_for_item(plan_data, item_id)
    evidence_doc = load_evidence_document(chat_id)

    if mode == 'selective-verification':
        all_rules = [r for r in all_rules if r['rule'].get('needs_strict_enforcement', False)]

    for rule_info in all_rules:
        rule = rule_info['rule']
        step_verifications = get_rule_verification_records_for_item(evidence_doc, item_id, rule)

        if not step_verifications:
            issues.append({
                'type': 'not_verified',
                'rule': rule,
                'source': rule_info['source_title'] if rule_info['source'] == 'parent' else None,
                'strict': rule.get('needs_strict_enforcement', False)
            })
        else:
            for v in step_verifications:
                verdict = str(v.get('verdict', '')).lower()
                if verdict in ['fail', 'unclear']:
                    issues.append({
                        'type': 'verification_failed',
                        'rule': rule,
                        'verdict': verdict,
                        'source': rule_info['source_title'] if rule_info['source'] == 'parent' else None,
                        'strict': rule.get('needs_strict_enforcement', False)
                    })
                    break

    return issues


@click.command()
@click.argument('step_id')
@click.argument('status', type=click.Choice(['pending', 'in_progress', 'completed', 'blocked']))
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .zoro/CURRENT_PLAN.md if not provided)')
def update_step(step_id, status, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()

    if not chat_id:
        click.echo("❌ No active visualization plan found in .zoro/CURRENT_PLAN.md")
        click.echo("   Provide --chat-id explicitly or extract a plan first")
        return

    if status == 'in_progress':
        ok, message = validate_item_can_start(chat_id, step_id)
        if not ok:
            click.echo(message)
            return

    if status == 'completed':
        ok, message = validate_item_can_complete(chat_id, step_id)
        if not ok:
            click.echo(message)
            return

    if status == 'completed':
        plan_data = load_plan_data(chat_id)
        metadata = _load_metadata(chat_id)

        if plan_data and metadata:
            item = find_item_by_id(plan_data['plan']['items'], step_id)

            if item and not item.get('children'):
                prev_leaf = get_previous_leaf_item(plan_data, step_id)

                if prev_leaf:
                    prev_id = prev_leaf.get('id')
                    prev_title = prev_leaf.get('title', prev_id)
                    tracking = metadata.get('plan_tracking', {})
                    prev_status = tracking.get(prev_id, 'pending')

                    if prev_status != 'completed':
                        click.echo(f"❌ Cannot mark complete. Previous step must be completed first:")
                        click.echo(f"   {prev_id}: {prev_title} (status: {prev_status})")
                        click.echo(f"\n   Run: zoro update-step {prev_id} completed")
                        return

    mode = get_enforcement_mode()

    if status == 'completed' and mode in ['verification', 'selective-verification']:
        plan_data = load_plan_data(chat_id)
        if not plan_data:
            click.echo(f"❌ No plan found for chat ID: {chat_id}")
            return

        item = find_item_by_id(plan_data['plan']['items'], step_id)
        if not item:
            click.echo(f"❌ Item {step_id} not found")
            return

        issues = check_verification_requirements(chat_id, plan_data, step_id, mode)

        if issues:
            click.echo(f"❌ Cannot complete {step_id}\n")

            for issue in issues:
                rule = issue['rule']
                rule_text = f"[{rule['category']}] {rule['text']}"

                if issue['type'] == 'not_verified':
                    click.echo(f"Rule NOT PROVED: {rule_text}\n")
                    click.echo("Zoro: Prove this rule before completing the step.")
                elif issue['type'] == 'verification_failed':
                    click.echo(f"Rule proof {issue['verdict'].upper()}: {rule_text}\n")
                    click.echo("Zoro: Complete this step following this rule, then prove it again.")

                click.echo()

            return

    click.echo(f"📍 Chat ID: {chat_id}")
    click.echo(f"📝 Updating item {step_id} → {status}")

    metadata, error = update_item_status(chat_id, step_id, status)

    if error:
        click.echo(f"❌ {error}")
        return

    click.echo(f"✅ Updated {step_id} to {status}")
    click.echo("📄 Markdown refreshed: .zoro/CURRENT_PLAN.md")

    if status == 'in_progress':
        click.echo(f"➡ When this step is ready, run: zoro update-step {step_id} completed")
        return

    if status == 'completed':
        refreshed_plan = load_plan_data(chat_id)
        refreshed_metadata = _load_metadata(chat_id)
        if refreshed_plan and refreshed_metadata:
            tracking = refreshed_metadata.get('plan_tracking', {})
            next_item = get_next_pending_leaf_item(refreshed_plan, tracking, after_item_id=step_id)
            if next_item:
                next_id = next_item.get('id', '')
                next_title = next_item.get('title', next_id)
                next_number = next_item.get('number', '')
                next_status = tracking.get(next_id, 'pending')
                click.echo(f"➡ Next step: {next_number} {next_id} - {next_title} ({next_status})")
                click.echo(f"   Run: zoro update-step {next_id} in_progress")
            else:
                click.echo("✅ No remaining incomplete leaf steps in the active plan.")
