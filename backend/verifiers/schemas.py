"""Pydantic models for the generic external-verifier framework.

These are intentionally generic (not security-audit-specific — see
backend/verifiers/security_audit.py for the strict adapter that validates
against the actual `zoro.security-audit.verifier-result/v1` envelope
shape). Keeping this layer generic is what lets a second verifier kind
be added later as its own sibling module, without touching command.py or
external_verifier_store.py.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class VerifierRequest(BaseModel):
    invocation_id: str
    plan_id: Optional[str] = None
    step_id: str
    rule_ids: list[str] = Field(..., min_length=1)
    repo_root: str
    expected_head: str
    expected_source_digest: Optional[str] = None
    result_path: str
    timeout_seconds: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class VerifierExecution(BaseModel):
    argv: list[str]
    # Only the allowlisted environment actually passed to the subprocess —
    # never the caller's full os.environ (backend/verifiers/command.py).
    sanitized_environment: dict[str, str] = Field(default_factory=dict)
    working_directory: str
    started_at: str
    finished_at: Optional[str] = None
    process_exit_code: Optional[int] = None
    bounded_stdout: str = ""
    bounded_stderr: str = ""
    timed_out: bool = False
    # Set when the process never ran at all (e.g. the binary doesn't
    # exist) — distinct from a normal nonzero exit, which is a real
    # verifier outcome, not an execution failure.
    launch_error: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


VerifierDecision = Literal["accept", "review_required", "reject", "incomplete", "error"]
VerifierCoverage = Literal["complete", "incomplete"]


class VerifierCheck(BaseModel):
    id: str
    status: str
    reason: Optional[str] = None

    # Adapter-specific check shapes vary (e.g. sec-audit's checks[] carry
    # componentId/requirement/version/exitCode) — this generic layer only
    # requires the fields ZORO's own policy/display logic needs.
    model_config = ConfigDict(extra="allow")


class VerifierArtifact(BaseModel):
    kind: str
    path: str
    sha256: str

    model_config = ConfigDict(extra="forbid")


class NormalizedVerifierResult(BaseModel):
    schema_version: str
    producer_name: str
    producer_version: str
    native_status: Optional[str] = None
    coverage: VerifierCoverage
    decision: VerifierDecision
    reasons: list[str] = Field(default_factory=list)
    checks: list[VerifierCheck] = Field(default_factory=list)
    artifacts: list[VerifierArtifact] = Field(default_factory=list)
    error: Optional[dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class VerifierCommandConfig(BaseModel):
    """One entry in `.zoro/config.json`'s `"verifiers"` object."""

    kind: Literal["command"]
    argv: list[str] = Field(..., min_length=1)
    schema_: str = Field(..., alias="schema")
    timeout_seconds: int = Field(default=1800, gt=0)
    # Literal, not bool/str — there is no documented alternative to
    # "require a human" for a PASS_WITH_RISK result in this v1, so a
    # typo'd or invented value is a hard config error rather than a
    # silently-ignored setting.
    pass_with_risk: Literal["require_human"] = "require_human"
    require_complete_coverage: bool = True
    # Rule categories always treated as security-gated, in addition to
    # any Rule.requires_verifier match (backend/visualization/schemas.py).
    gated_rule_categories: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VerifiersConfig(BaseModel):
    verifiers: dict[str, VerifierCommandConfig] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class VerifierConfigError(Exception):
    """`.zoro/config.json`'s `"verifiers"` block is missing or malformed.

    Deliberately NOT swallowed into an empty/default config the way
    `backend.utils._load_config()` treats a malformed general config file
    (bare `except Exception: return {}`) — this block drives literal
    subprocess argv for a security gate, so a typo here must fail loudly
    before any process is launched, not silently disable the gate it
    configures. See `backend.utils.get_verifiers_config()`.
    """
