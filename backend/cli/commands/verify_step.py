"""`zoro verify-step <step-id> --verifier <id>` — the ONLY ZORO code path
that ever launches an external verifier process and imports its result.

`update-step --state completed` (backend/cli/commands/update_step.py)
only ever CONSUMES evidence this command already wrote; it never runs a
verifier itself.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import click

from backend.utils import get_project_root, get_verifiers_config
from backend.verifiers.command import run_command_verifier
from backend.verifiers.schemas import VerifierConfigError, VerifierRequest
from backend.verifiers.security_audit import build_argv
from backend.visualization.services.evidence_store import append_external_verifier_reference
from backend.visualization.services.external_verifier_store import import_verifier_result
from backend.visualization.services.plan_tracker import (
    collect_rules_for_item,
    find_item_by_id,
    get_chat_id_from_plan_md,
    load_plan_data,
)


def _read_current_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not read git HEAD in {repo_root}: {result.stderr.strip()}")
    return result.stdout.strip()


def _derive_rule_id(rule: dict, item_id: str) -> str:
    kb_item_id = rule.get("kb_item_id")
    if kb_item_id:
        return str(kb_item_id)
    text = str(rule.get("text", ""))
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{item_id}-{digest}"


def _gated_rule_ids_for_step(plan_data: dict, item_id: str, verifier_id: str, gated_categories: list[str]) -> list[str]:
    rule_ids = []
    for rule_info in collect_rules_for_item(plan_data, item_id):
        rule = rule_info["rule"]
        is_gated = rule.get("requires_verifier") == verifier_id or rule.get("category") in gated_categories
        if is_gated:
            rule_ids.append(_derive_rule_id(rule, item_id))
    return rule_ids


@click.command()
@click.argument("step_id")
@click.option("--verifier", required=True, help="Verifier id from .zoro/config.json's \"verifiers\" block")
@click.option("--chat-id", default=None, help="Chat ID (auto-detect from .zoro/CURRENT_PLAN.md if not provided)")
@click.option("--plan-id", default=None, help="Plan id, if the active plan has a stable one")
def verify_step(step_id, verifier, chat_id, plan_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
    if not chat_id:
        click.echo("❌ No active visualization plan found in .zoro/CURRENT_PLAN.md")
        click.echo("   Provide --chat-id explicitly or extract a plan first")
        sys.exit(1)

    try:
        verifiers_config = get_verifiers_config()
    except VerifierConfigError as exc:
        click.echo(f"❌ Invalid verifier configuration: {exc}")
        sys.exit(50)

    verifier_config = verifiers_config.verifiers.get(verifier)
    if not verifier_config:
        click.echo(f"❌ No verifier named '{verifier}' configured in .zoro/config.json")
        sys.exit(50)

    plan_data = load_plan_data(chat_id)
    if not plan_data:
        click.echo(f"❌ No plan found for chat ID: {chat_id}")
        sys.exit(1)

    item = find_item_by_id(plan_data["plan"]["items"], step_id)
    if not item:
        click.echo(f"❌ Item {step_id} not found")
        sys.exit(1)

    rule_ids = _gated_rule_ids_for_step(plan_data, step_id, verifier, verifier_config.gated_rule_categories)
    if not rule_ids:
        click.echo(f"⊗ No rules on {step_id} are gated behind verifier '{verifier}' — nothing to verify.")
        click.echo(
            "   Mark a rule as gated by setting requires_verifier "
            f"to '{verifier}', or add its category to that verifier's gated_rule_categories."
        )
        sys.exit(1)

    repo_root = get_project_root()
    try:
        current_head = _read_current_head(repo_root)
    except RuntimeError as exc:
        click.echo(f"❌ {exc}")
        sys.exit(50)

    invocation_id = uuid.uuid4().hex
    result_dir = Path(tempfile.mkdtemp(prefix="zoro-verifier-result-"))
    result_path = result_dir / "result.json"

    try:
        request = VerifierRequest(
            invocation_id=invocation_id,
            plan_id=plan_id,
            step_id=step_id,
            rule_ids=rule_ids,
            repo_root=str(repo_root),
            expected_head=current_head,
            result_path=str(result_path),
            timeout_seconds=verifier_config.timeout_seconds,
        )

        argv = build_argv(request, verifier_config)

        click.echo(f"🔎 Running verifier '{verifier}' for step {step_id} (invocation {invocation_id})...")
        execution = run_command_verifier(argv, cwd=str(repo_root), timeout_seconds=verifier_config.timeout_seconds)

        import_result = import_verifier_result(
            request,
            execution,
            verifier_config,
            chat_id,
            verifier_id=verifier,
            current_head=current_head,
        )
    finally:
        shutil.rmtree(result_dir, ignore_errors=True)

    if import_result.manifest_path:
        append_external_verifier_reference(
            chat_id,
            item_id=step_id,
            rule_ids=rule_ids,
            verifier_id=verifier,
            invocation_id=invocation_id,
            manifest_path=str(import_result.manifest_path),
            status=import_result.status,
            coverage=import_result.coverage,
            decision=import_result.decision,
        )

    reasons = "; ".join(import_result.reasons) if import_result.reasons else ""

    if import_result.decision == "accept":
        click.echo(f"✅ {verifier}: PASS — evidence recorded for {step_id} (invocation {invocation_id})")
        sys.exit(0)
    if import_result.decision == "review_required":
        click.echo(f"⚠️  {verifier}: PASS WITH RISK — requires human review.")
        click.echo(f"   Run: zoro accept-risk {step_id} --invocation-id {invocation_id} --reason \"<text>\"")
        sys.exit(1)
    if import_result.decision == "reject":
        click.echo(f"❌ {verifier}: DO NOT SHIP{f' — {reasons}' if reasons else ''}")
        sys.exit(1)
    if import_result.decision == "incomplete":
        click.echo(f"❌ {verifier}: coverage incomplete{f' — {reasons}' if reasons else ''}")
        sys.exit(1)
    click.echo(f"❌ {verifier}: verifier error{f' — {reasons}' if reasons else ''}")
    sys.exit(1)
