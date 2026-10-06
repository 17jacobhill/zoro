import json
import subprocess

import click

from backend.visualization.services.evidence_store import (
    get_external_verifier_records_for_item,
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
from backend.utils import get_enforcement_mode, get_project_root, get_verifiers_config
from backend.verifiers.schemas import VerifierConfigError


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

    issues.extend(check_external_verifier_requirements(chat_id, plan_data, item_id, evidence_doc))

    return issues


def _current_head_or_none() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(get_project_root()),
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def check_external_verifier_requirements(chat_id, plan_data, item_id, evidence_doc):
    """Security-gated rules (Rule.requires_verifier, or category listed in a
    verifier's gated_rule_categories) additionally require CURRENT accepted
    external-verifier evidence before a step may complete. This NEVER
    executes a verifier — it only reads evidence `verify-step` already
    wrote (backend/cli/commands/verify_step.py is the sole place that
    launches one). A `prove-rule` (`source: "rule-verification"`) record
    structurally cannot satisfy this check — get_external_verifier_records_for_item
    only ever matches `source: "external-verifier"` records.
    """
    issues = []

    try:
        verifiers_config = get_verifiers_config()
    except VerifierConfigError as exc:
        # Fail closed: a broken verifier config must block completion,
        # never silently skip gating because the config couldn't be read.
        issues.append({'type': 'verifier_config_error', 'message': str(exc)})
        return issues

    if not verifiers_config.verifiers:
        return issues

    all_rules = collect_rules_for_item(plan_data, item_id)
    current_head = _current_head_or_none()

    for rule_info in all_rules:
        rule = rule_info['rule']
        for verifier_id, verifier_config in verifiers_config.verifiers.items():
            is_gated = (
                rule.get('requires_verifier') == verifier_id
                or rule.get('category') in verifier_config.gated_rule_categories
            )
            if not is_gated:
                continue

            records = get_external_verifier_records_for_item(evidence_doc, item_id, verifier_id)
            if not records:
                issues.append({'type': 'external_verifier_missing', 'rule': rule, 'verifier_id': verifier_id})
                continue

            latest = records[-1]
            raw = latest.get('raw_rule_result') or {}
            decision = raw.get('decision')
            invocation_id = raw.get('invocation_id')
            manifest_path = raw.get('manifest_path')

            if current_head and manifest_path:
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    recorded_head = (manifest.get('source') or {}).get('head')
                except (OSError, ValueError):
                    recorded_head = None
                if recorded_head and recorded_head != current_head:
                    issues.append({'type': 'external_verifier_stale', 'rule': rule, 'verifier_id': verifier_id})
                    continue

            if decision == 'accept':
                continue
            if decision == 'review_required':
                accepted = any(
                    r.get('source') == 'human-risk-acceptance'
                    and (r.get('raw_rule_result') or {}).get('invocation_id') == invocation_id
                    for r in evidence_doc.get('records', [])
                )
                if not accepted:
                    issues.append({
                        'type': 'external_verifier_risk_not_accepted',
                        'rule': rule,
                        'verifier_id': verifier_id,
                        'invocation_id': invocation_id,
                    })
                continue
            # 'reject' (DO_NOT_SHIP), 'incomplete' (coverage), or 'error'
            # (verifier failure/stale/malformed) — all block, distinctly
            # labeled so update-step's output can tell a security
            # rejection apart from a verifier-operational failure.
            issues.append({
                'type': 'external_verifier_blocked',
                'rule': rule,
                'verifier_id': verifier_id,
                'decision': decision,
            })

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
                if issue['type'] == 'verifier_config_error':
                    click.echo(f"Verifier configuration error: {issue['message']}\n")
                    click.echo("Zoro: Fix .zoro/config.json's \"verifiers\" block before this step can complete.")
                    click.echo()
                    continue

                rule = issue['rule']
                rule_text = f"[{rule['category']}] {rule['text']}"

                if issue['type'] == 'not_verified':
                    click.echo(f"Rule NOT PROVED: {rule_text}\n")
                    click.echo("Zoro: Prove this rule before completing the step.")
                elif issue['type'] == 'verification_failed':
                    click.echo(f"Rule proof {issue['verdict'].upper()}: {rule_text}\n")
                    click.echo("Zoro: Complete this step following this rule, then prove it again.")
                elif issue['type'] == 'external_verifier_missing':
                    click.echo(f"Rule requires verifier '{issue['verifier_id']}', not yet run: {rule_text}\n")
                    click.echo(f"Zoro: Run `zoro verify-step {step_id} --verifier {issue['verifier_id']}` before completing the step.")
                elif issue['type'] == 'external_verifier_stale':
                    click.echo(f"Rule's '{issue['verifier_id']}' evidence is STALE (source changed since it ran): {rule_text}\n")
                    click.echo(f"Zoro: Re-run `zoro verify-step {step_id} --verifier {issue['verifier_id']}`.")
                elif issue['type'] == 'external_verifier_risk_not_accepted':
                    click.echo(f"Rule's '{issue['verifier_id']}' result is PASS WITH RISK, not yet accepted: {rule_text}\n")
                    click.echo(
                        f"Zoro: Run `zoro accept-risk {step_id} --invocation-id {issue['invocation_id']} "
                        f"--reason \"<text>\"` (a named human must do this)."
                    )
                elif issue['type'] == 'external_verifier_blocked':
                    click.echo(f"Rule's '{issue['verifier_id']}' result is {issue['decision'].upper()}: {rule_text}\n")
                    click.echo("Zoro: This is a verifier block, not a missing-proof issue — remediate and re-run verify-step.")

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
