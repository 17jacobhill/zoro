"""Atomic, fail-closed import of an external verifier's result.

Implements the 12-step validation sequence (handoff) as ONE linear
function — deliberately not a generic pluggable pipeline, so no step can
be silently skipped or reordered. No later step can turn an earlier
failure into accepted evidence: every early return here is terminal.

Deliberately does NOT reuse backend.visualization.services.evidence_store's
lenient "malformed JSON -> empty document" pattern — that is fine for
`prove-rule` evidence, but this path drives a security gate, so a
malformed or tampered result must fail closed with a clear reason, never
silently degrade to "no evidence".
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from backend.verifiers.schemas import VerifierCommandConfig, VerifierExecution, VerifierRequest
from backend.verifiers.security_audit import (
    SECURITY_AUDIT_PRODUCER_NAME,
    SECURITY_AUDIT_SCHEMA_ID,
    SecurityAuditEnvelope,
    compute_decision,
    expected_exit_code,
    validate_envelope_shape,
)
from backend.visualization.paths import get_verifier_dir

EVIDENCE_MANIFEST_SCHEMA_ID = "zoro.evidence-manifest/v1"


@dataclass
class ImportResult:
    accepted: bool
    decision: str
    reasons: list[str] = field(default_factory=list)
    manifest_path: Optional[Path] = None
    status: Optional[str] = None
    coverage: Optional[str] = None


class ArtifactPathError(Exception):
    pass


def _error(decision: str, reason: str) -> ImportResult:
    return ImportResult(accepted=False, decision=decision, reasons=[reason])


def _resolve_artifact_path(repo_root: Path, relative_path: str) -> Path:
    root_resolved = repo_root.resolve()
    candidate = (root_resolved / relative_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ArtifactPathError(f"artifact path escapes repository root: {relative_path}")
    return candidate


def import_verifier_result(
    request: VerifierRequest,
    execution: VerifierExecution,
    verifier_config: VerifierCommandConfig,
    chat_id: str,
    *,
    verifier_id: str,
    current_head: str,
    base: Path | None = None,
) -> ImportResult:
    # 1. Process termination/timeout.
    if execution.timed_out:
        return _error("error", "verifier process timed out")
    if execution.launch_error:
        return _error("error", f"verifier process failed to launch: {execution.launch_error}")
    if execution.process_exit_code is None:
        return _error("error", "verifier process did not report an exit code")

    # 2. Result file exists.
    result_path = Path(request.result_path)
    if not result_path.is_file():
        return _error("error", f"result file not found: {result_path}")

    # 3. Strict JSON parse — no empty-document fallback.
    try:
        raw_bytes = result_path.read_bytes()
        raw_text = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _error("error", f"result file is not valid JSON: {exc}")

    if not isinstance(parsed, dict):
        return _error("error", "result file JSON is not an object")

    # 4. Schema version.
    if parsed.get("schemaVersion") != SECURITY_AUDIT_SCHEMA_ID:
        return _error("error", f"unknown or missing schemaVersion: {parsed.get('schemaVersion')!r}")

    # 5. Producer identity.
    producer_name = (parsed.get("producer") or {}).get("name")
    if producer_name != SECURITY_AUDIT_PRODUCER_NAME:
        return _error("error", f"unexpected producer: {producer_name!r}")

    # 6. Full structural validation, then invocation/plan/step/rule ID match.
    try:
        envelope: SecurityAuditEnvelope = validate_envelope_shape(parsed)
    except ValidationError as exc:
        return _error("error", f"result envelope does not match the expected shape: {exc}")

    if envelope.invocation.id != request.invocation_id:
        return _error("error", "invocation id in result does not match the request")
    if envelope.invocation.stepId != request.step_id:
        return _error("error", "step id in result does not match the request")
    if request.plan_id is not None and envelope.invocation.planId != request.plan_id:
        return _error("error", "plan id in result does not match the request")
    if not set(request.rule_ids) <= set(envelope.invocation.ruleIds):
        return _error("error", "rule ids in result do not cover the requested rule ids")

    # 7. Exit code must agree with the envelope's own outcome/coverage.
    expected_code = expected_exit_code(envelope.outcome.status, envelope.outcome.coverage)
    if expected_code != execution.process_exit_code:
        return _error(
            "error",
            f"producer integrity: exit code {execution.process_exit_code} disagrees with "
            f"outcome status={envelope.outcome.status!r} coverage={envelope.outcome.coverage!r} "
            f"(expected {expected_code})",
        )

    # 8. HEAD must match what ZORO itself read immediately before launching
    # the subprocess (not a digest recomputed in Python — sec-audit's own
    # before/after digest check inside `verify` is what catches scan-time
    # drift; this is an independent, cross-process TOCTOU check).
    if envelope.subject.git.head != current_head:
        return _error("error", f"stale evidence: repository HEAD has moved since this verifier ran")

    # 9/10. Artifact path safety + hash recompute.
    repo_root = Path(request.repo_root)
    for artifact in envelope.artifacts:
        try:
            resolved = _resolve_artifact_path(repo_root, artifact.path)
        except ArtifactPathError as exc:
            return _error("error", str(exc))
        if not resolved.is_file():
            return _error("error", f"artifact not found: {artifact.path}")
        actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha256 != artifact.sha256:
            return _error("error", f"artifact hash mismatch: {artifact.path}")

    # 11. Policy decision recomputed independently — never trust the
    # envelope's own `decision` field as the final word.
    decision = compute_decision(
        envelope.outcome.status,
        envelope.outcome.coverage,
        require_complete_coverage=verifier_config.require_complete_coverage,
    )
    warnings: list[str] = []
    if decision != envelope.outcome.decision:
        warnings.append(
            f"producer reported decision={envelope.outcome.decision!r}; "
            f"ZORO recomputed {decision!r} and used its own value"
        )

    # 12. Atomic import: write to a sibling temp dir, then os.replace into place.
    final_dir = get_verifier_dir(chat_id, verifier_id, request.step_id, request.invocation_id, base)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = final_dir.parent / f".tmp-{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True)

    try:
        (tmp_dir / "envelope.json").write_text(raw_text, encoding="utf-8")

        copied_artifacts = []
        for artifact in envelope.artifacts:
            if artifact.kind != "report-json":
                # Default: copy the compact/primary artifact (report.json);
                # reference larger ones (report.md/report.html) by path+hash only.
                copied_artifacts.append({"kind": artifact.kind, "path": artifact.path, "sha256": artifact.sha256, "copied": False})
                continue
            resolved = _resolve_artifact_path(repo_root, artifact.path)
            (tmp_dir / "report.json").write_bytes(resolved.read_bytes())
            copied_artifacts.append({"kind": artifact.kind, "path": artifact.path, "sha256": artifact.sha256, "copied": True})

        manifest = {
            "schemaVersion": EVIDENCE_MANIFEST_SCHEMA_ID,
            "chatId": chat_id,
            "invocationId": request.invocation_id,
            "planId": request.plan_id,
            "stepId": request.step_id,
            "ruleIds": request.rule_ids,
            "verifier": {
                "id": verifier_id,
                "producerVersion": envelope.producer.version,
                "resultSchema": envelope.schemaVersion,
            },
            "source": {"head": envelope.subject.git.head, "sourceDigest": envelope.subject.git.sourceDigest},
            "execution": {
                "argv": execution.argv,
                "exitCode": execution.process_exit_code,
                "startedAt": execution.started_at,
                "finishedAt": execution.finished_at,
            },
            "result": {
                "status": envelope.outcome.status,
                "coverage": envelope.outcome.coverage,
                "decision": decision,
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            },
            "artifacts": copied_artifacts,
            "warnings": warnings,
            "importedAt": datetime.now(UTC).isoformat(),
        }
        (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    os.replace(tmp_dir, final_dir)

    return ImportResult(
        accepted=decision in {"accept", "review_required"},
        decision=decision,
        reasons=warnings,
        manifest_path=final_dir / "manifest.json",
        status=envelope.outcome.status,
        coverage=envelope.outcome.coverage,
    )
