"""Thin adapter for the `zoro.security-audit.verifier-result/v1` contract.

No scanner logic and no subprocess calls here — only request/argv
building and strict shape validation of what `security-audit verify`
reports. See ../../../sec-audit's own src/verify/envelope.ts for the
producer side of this exact contract.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.verifiers.schemas import VerifierCommandConfig, VerifierRequest

SECURITY_AUDIT_SCHEMA_ID = "zoro.security-audit.verifier-result/v1"
SECURITY_AUDIT_PRODUCER_NAME = "security-audit"


class SecurityAuditProducer(BaseModel):
    name: str
    version: str
    model_config = ConfigDict(extra="allow")


class SecurityAuditInvocation(BaseModel):
    id: str
    planId: Optional[str] = None
    stepId: str
    ruleIds: list[str]
    depth: str
    startedAt: str
    finishedAt: str
    model_config = ConfigDict(extra="allow")


class SecurityAuditGit(BaseModel):
    head: str
    branch: Optional[str] = None
    clean: bool
    sourceDigest: str
    model_config = ConfigDict(extra="allow")


class SecurityAuditSubject(BaseModel):
    repoRoot: str
    repository: Optional[str] = None
    git: SecurityAuditGit
    model_config = ConfigDict(extra="allow")


class SecurityAuditOutcome(BaseModel):
    status: Optional[str] = None
    coverage: str
    decision: str
    reasons: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


class SecurityAuditArtifact(BaseModel):
    kind: str
    path: str
    sha256: str
    model_config = ConfigDict(extra="forbid")


class SecurityAuditCheck(BaseModel):
    id: str
    componentId: Optional[str] = None
    requirement: str
    status: str
    version: Optional[str] = None
    exitCode: Optional[int] = None
    reason: Optional[str] = None
    model_config = ConfigDict(extra="allow")


class SecurityAuditFinding(BaseModel):
    fingerprint: str
    title: str
    severity: str
    status: str
    releaseBlocker: bool
    locations: Optional[list[dict]] = None
    model_config = ConfigDict(extra="allow")


class SecurityAuditError(BaseModel):
    stage: Optional[str] = None
    message: str
    model_config = ConfigDict(extra="allow")


class SecurityAuditEnvelope(BaseModel):
    schemaVersion: str
    producer: SecurityAuditProducer
    invocation: SecurityAuditInvocation
    subject: SecurityAuditSubject
    outcome: SecurityAuditOutcome
    checks: list[SecurityAuditCheck] = Field(default_factory=list)
    artifacts: list[SecurityAuditArtifact] = Field(default_factory=list)
    findings: Optional[list[SecurityAuditFinding]] = None
    summary: Optional[dict[str, Any]] = None
    error: Optional[SecurityAuditError] = None

    model_config = ConfigDict(extra="forbid")


def validate_envelope_shape(parsed: dict) -> SecurityAuditEnvelope:
    """Pure Pydantic validation — raises ValidationError on any shape mismatch."""
    return SecurityAuditEnvelope.model_validate(parsed)


def expected_exit_code(status: Optional[str], coverage: str) -> Optional[int]:
    """The exit code sec-audit's own src/verify/envelope.ts::computeExitCode
    would have produced for this (status, coverage) pair — recomputed here,
    independently, so ZORO never just trusts the producer's self-report
    (handoff 12-step import sequence, step 7)."""
    if coverage == "incomplete":
        return 30
    return {"PASS": 0, "PASS_WITH_RISK": 10, "DO_NOT_SHIP": 20}.get(status or "")


def compute_decision(status: Optional[str], coverage: str, *, require_complete_coverage: bool = True) -> str:
    """ZORO's own policy decision — recomputed rather than trusting the
    envelope's `outcome.decision` as-is (handoff step 11: "ZORO's
    recomputed value wins"). `require_complete_coverage` is a per-verifier
    config knob (`.zoro/config.json`'s `verifiers.<id>.require_complete_coverage`,
    default True per the PRD's recommended defaults for release gates) —
    when False, a step may accept an incomplete-coverage PASS (e.g. a
    looser dev-step policy). This is ZORO's own policy choice, independent
    of sec-audit's own exit-code mapping (expected_exit_code() below),
    which always treats incomplete coverage as exit 30 regardless — that
    one is a producer-integrity check, not a policy choice."""
    if coverage == "incomplete" and require_complete_coverage:
        return "incomplete"
    return {"PASS": "accept", "PASS_WITH_RISK": "review_required", "DO_NOT_SHIP": "reject"}.get(status or "", "error")


def build_argv(request: VerifierRequest, verifier_config: VerifierCommandConfig) -> list[str]:
    """Per-element template substitution — never a shell string. `{rule_id_args}`
    and `{plan_id_args}` are typed placeholders that each expand to zero or
    more complete argv elements (never a joined/interpolated string)."""
    rule_id_args: list[str] = []
    for rule_id in request.rule_ids:
        rule_id_args.extend(["--rule-id", rule_id])

    plan_id_args = ["--plan-id", request.plan_id] if request.plan_id else []

    substitutions: dict[str, list[str]] = {
        "{repo_root}": [request.repo_root],
        "{invocation_id}": [request.invocation_id],
        "{step_id}": [request.step_id],
        "{git_head}": [request.expected_head],
        "{result_file}": [request.result_path],
        "{rule_id_args}": rule_id_args,
        "{plan_id_args}": plan_id_args,
    }

    argv: list[str] = []
    for token in verifier_config.argv:
        argv.extend(substitutions.get(token, [token]))
    return argv
