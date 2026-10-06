"""`zoro accept-risk <step-id> --invocation-id <id> --reason <text> [--expires-at <timestamp>]`

Writes a separate, explicit human risk-acceptance record. Never rewrites
the verifier's own PASS_WITH_RISK result — it remains visible as risk —
and is never callable implicitly from `update-step`; a human must run
this command themselves, with an interactive confirmation of who they
are. Stronger organizational authorization (SSO identity, approval
workflow, etc.) can replace this confirmation seam later without
changing the evidence shape it writes.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import click

from backend.visualization.services.evidence_store import (
    load_evidence_document,
    normalize_evidence_record,
    save_evidence_document,
)
from backend.visualization.services.plan_tracker import get_chat_id_from_plan_md


@click.command()
@click.argument("step_id")
@click.option("--invocation-id", required=True, help="The verify-step invocation id whose PASS_WITH_RISK result is being accepted")
@click.option("--reason", required=True, help="Why this risk is being accepted")
@click.option("--expires-at", default=None, help="Optional ISO timestamp after which this acceptance no longer applies")
@click.option("--chat-id", default=None, help="Chat ID (auto-detect if not provided)")
def accept_risk(step_id, invocation_id, reason, expires_at, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
    if not chat_id:
        click.echo("❌ No active visualization plan found in .zoro/CURRENT_PLAN.md")
        click.echo("   Provide --chat-id explicitly or extract a plan first")
        sys.exit(1)

    evidence_doc = load_evidence_document(chat_id)
    matching = [
        record
        for record in evidence_doc.get("records", [])
        if record.get("source") == "external-verifier"
        and str(record.get("item_id") or "") == str(step_id)
        and (record.get("raw_rule_result") or {}).get("invocation_id") == invocation_id
    ]
    if not matching:
        click.echo(f"❌ No external-verifier evidence found for step {step_id} with invocation {invocation_id}")
        click.echo("   Run `zoro verify-step` first.")
        sys.exit(1)

    matched = matching[-1]
    raw = matched.get("raw_rule_result") or {}
    status = raw.get("status")
    if status != "PASS_WITH_RISK":
        click.echo(f"❌ Invocation {invocation_id} is not a PASS_WITH_RISK result (status: {status}); nothing to accept.")
        sys.exit(1)

    approver = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    click.echo(f"Step:       {step_id}")
    click.echo(f"Invocation: {invocation_id}")
    click.echo(f"Reason:     {reason}")
    if not click.confirm(f"Confirm you ({approver}) are accepting this risk?"):
        click.echo("Aborted — risk not accepted.")
        sys.exit(1)

    now_iso = datetime.now(UTC).isoformat()
    records = evidence_doc.setdefault("records", [])
    record = normalize_evidence_record(
        chat_id,
        {
            "item_id": step_id,
            "rule_text": reason,
            "source": "human-risk-acceptance",
            "verdict": "pass",
            "timestamp": now_iso,
            "record_index": len(records),
            "raw_rule_result": {
                "invocation_id": invocation_id,
                "approver": approver,
                "reason": reason,
                "expires_at": expires_at,
                "manifest_path": raw.get("manifest_path"),
            },
        },
        now_iso,
    )
    records.append(record)
    evidence_doc["chat_id"] = chat_id
    evidence_doc["created_at"] = evidence_doc.get("created_at") or now_iso
    evidence_doc["updated_at"] = now_iso
    save_evidence_document(chat_id, evidence_doc)

    click.echo(f"✅ Risk accepted for {step_id} (invocation {invocation_id}) by {approver}")
    click.echo("   This does NOT rewrite the verifier's PASS_WITH_RISK result — it remains visible as risk.")
