import click
from backend.visualization.services.visualization_manager import update_item_status, _load_metadata
from backend.visualization.services.plan_tracker import get_chat_id_from_plan_md, load_plan_data, find_item_by_id, collect_rules_for_item
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

def check_verification_requirements(item, plan_data, item_id, mode='verification'):
    issues = []
    
    all_rules = collect_rules_for_item(plan_data, item_id)
    
    if mode == 'selective-verification':
        all_rules = [r for r in all_rules if r['rule'].get('needs_strict_enforcement', False)]
    
    for rule_info in all_rules:
        rule = rule_info['rule']
        verifications = rule.get('verifications', [])
        
        step_verifications = [v for v in verifications if v.get('item_id') == item_id]
        
        if not step_verifications:
            source_label = f" (from {rule_info['source_title']})" if rule_info['source'] == 'parent' else ""
            strict_label = " [STRICT]" if rule.get('needs_strict_enforcement', False) else ""
            issues.append({
                'type': 'not_verified',
                'rule': rule,
                'source': rule_info['source_title'] if rule_info['source'] == 'parent' else None,
                'strict': rule.get('needs_strict_enforcement', False)
            })
        else:
            # Check if any verification has failed or unclear verdict
            for v in step_verifications:
                verdict = v.get('verdict', '').lower()
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
@click.argument('item_id')
@click.argument('status', type=click.Choice(['in_progress', 'completed', 'pending']))
@click.option('--chat-id', default=None, help='Chat ID (auto-detect if not provided)')
def viz_update(item_id, status, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
        
    if not chat_id:
        click.echo("❌ No active visualization plan found in .rules/zoro_plan.md")
        click.echo("   Provide --chat-id explicitly or extract a plan first")
        return
    
    # Validate conflicts before allowing status changes
    if status == 'in_progress':
        ok, message = validate_item_can_start(chat_id, item_id)
        if not ok:
            click.echo(message)
            return
    
    if status == 'completed':
        ok, message = validate_item_can_complete(chat_id, item_id)
        if not ok:
            click.echo(message)
            return
    
    if status == 'completed':
        plan_data = load_plan_data(chat_id)
        metadata = _load_metadata(chat_id)
        
        if plan_data and metadata:
            item = find_item_by_id(plan_data['plan']['items'], item_id)
            
            if item and not item.get('children'):
                prev_leaf = get_previous_leaf_item(plan_data, item_id)
                
                if prev_leaf:
                    prev_id = prev_leaf.get('id')
                    prev_title = prev_leaf.get('title', prev_id)
                    tracking = metadata.get('plan_tracking', {})
                    prev_status = tracking.get(prev_id, 'pending')
                    
                    if prev_status != 'completed':
                        click.echo(f"❌ Cannot mark complete. Previous step must be completed first:")
                        click.echo(f"   {prev_id}: {prev_title} (status: {prev_status})")
                        click.echo(f"\n   Run: zoro viz-update {prev_id} completed")
                        return
    
    # Check enforcement mode
    mode = get_enforcement_mode()
    
    # If marking as completed and in verification mode, enforce required rule proofs
    if status == 'completed' and mode in ['verification', 'selective-verification']:
        plan_data = load_plan_data(chat_id)
        if not plan_data:
            click.echo(f"❌ No plan found for chat ID: {chat_id}")
            return
            
        item = find_item_by_id(plan_data['plan']['items'], item_id)
        if not item:
            click.echo(f"❌ Item {item_id} not found")
            return
            
        issues = check_verification_requirements(item, plan_data, item_id, mode)
    
        if issues:
            click.echo(f"❌ Cannot complete {item_id}\n")
            
            for issue in issues:
                rule = issue['rule']
                rule_text = f"[{rule['category']}] {rule['text']}"
                
                if issue['type'] == 'not_verified':
                    click.echo(f"Rule NOT PROVED: {rule_text}\n")
                    click.echo("Cline: Prove this rule before completing the step.")
                elif issue['type'] == 'verification_failed':
                    click.echo(f"Rule proof {issue['verdict'].upper()}: {rule_text}\n")
                    click.echo("Cline: Complete this step following this rule, then prove it again.")
                
                click.echo()  # Blank line between issues
            
            return

    click.echo(f"📍 Chat ID: {chat_id}")
    click.echo(f"📝 Updating item {item_id} → {status}")
    
    metadata, error = update_item_status(chat_id, item_id, status)
    
    if error:
        click.echo(f"❌ {error}")
        return
    
    click.echo(f"✅ Updated {item_id} to {status}")
    click.echo(f"📄 Markdown refreshed: .rules/zoro_plan.md")
