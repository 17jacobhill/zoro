import hashlib
import json
from pathlib import Path

from backend.verifiers.schemas import VerifierCommandConfig, VerifierExecution, VerifierRequest
from backend.verifiers.security_audit import SECURITY_AUDIT_SCHEMA_ID, expected_exit_code
from backend.visualization.services.external_verifier_store import import_verifier_result

HEAD = "a" * 40
CHAT_ID = "chat-1"
VERIFIER_ID = "security-audit"


def _write_report(repo_root: Path) -> tuple[str, str]:
    report_dir = repo_root / ".security-audit" / "history" / "run-1" / "reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report.json"
    report_path.write_text("{}", encoding="utf-8")
    sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    return str(report_path.relative_to(repo_root)), sha256


def _envelope(repo_root: Path, *, status="PASS", coverage="complete", head=HEAD, invocation_id="inv-1",
              step_id="STEP-1", plan_id=None, rule_ids=("RULE-1",), bad_artifact_hash=False,
              artifact_outside_repo=False) -> dict:
    rel_path, sha256 = _write_report(repo_root)
    decision = {"PASS": "accept", "PASS_WITH_RISK": "review_required", "DO_NOT_SHIP": "reject"}.get(status, "incomplete")
    if coverage == "incomplete":
        decision = "incomplete"
    artifacts = [{"kind": "report-json", "path": rel_path, "sha256": "0" * 64 if bad_artifact_hash else sha256}]
    if artifact_outside_repo:
        artifacts = [{"kind": "report-json", "path": "../../etc/passwd", "sha256": "0" * 64}]
    return {
        "schemaVersion": SECURITY_AUDIT_SCHEMA_ID,
        "producer": {"name": "security-audit", "version": "0.1.0"},
        "invocation": {
            "id": invocation_id,
            "planId": plan_id,
            "stepId": step_id,
            "ruleIds": list(rule_ids),
            "depth": "fast",
            "startedAt": "2026-01-01T00:00:00.000Z",
            "finishedAt": "2026-01-01T00:01:00.000Z",
        },
        "subject": {
            "repoRoot": str(repo_root),
            "git": {"head": head, "clean": True, "sourceDigest": "sha256:" + "b" * 64},
        },
        "outcome": {"status": status, "coverage": coverage, "decision": decision, "reasons": []},
        "checks": [],
        "artifacts": artifacts,
        "error": None,
    }


def _write_result_file(tmp_path: Path, envelope: dict) -> Path:
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(envelope), encoding="utf-8")
    return result_path


def _request(tmp_path: Path, result_path: Path, **overrides) -> VerifierRequest:
    defaults = dict(
        invocation_id="inv-1",
        step_id="STEP-1",
        rule_ids=["RULE-1"],
        repo_root=str(tmp_path),
        expected_head=HEAD,
        result_path=str(result_path),
        timeout_seconds=60,
    )
    defaults.update(overrides)
    return VerifierRequest(**defaults)


def _execution(exit_code, **overrides) -> VerifierExecution:
    defaults = dict(
        argv=["node", "verify"],
        working_directory="/repo",
        started_at="2026-01-01T00:00:00.000Z",
        finished_at="2026-01-01T00:01:00.000Z",
        process_exit_code=exit_code,
        timed_out=False,
        launch_error=None,
    )
    defaults.update(overrides)
    return VerifierExecution(**defaults)


def _config(**overrides) -> VerifierCommandConfig:
    defaults = dict(kind="command", argv=["node", "verify"], schema=SECURITY_AUDIT_SCHEMA_ID)
    defaults.update(overrides)
    return VerifierCommandConfig(**defaults)


def test_happy_path_imports_and_writes_an_atomic_manifest(tmp_path):
    envelope = _envelope(tmp_path, status="PASS", coverage="complete")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is True
    assert result.decision == "accept"
    assert result.manifest_path.is_file()
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["schemaVersion"] == "zoro.evidence-manifest/v1"
    assert manifest["chatId"] == CHAT_ID
    assert manifest["result"]["status"] == "PASS"
    assert (result.manifest_path.parent / "envelope.json").is_file()
    assert (result.manifest_path.parent / "report.json").is_file()
    # No stray temp directories left behind.
    stray = list(result.manifest_path.parent.parent.glob(".tmp-*"))
    assert stray == []


def test_timed_out_execution_is_rejected_as_verifier_error(tmp_path):
    envelope = _envelope(tmp_path)
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(None, timed_out=True)

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert result.decision == "error"
    assert "timed out" in result.reasons[0]


def test_missing_result_file_is_rejected(tmp_path):
    request = _request(tmp_path, tmp_path / "does-not-exist.json")
    execution = _execution(0)

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "not found" in result.reasons[0]


def test_malformed_json_fails_closed_no_empty_document_fallback(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text("{not valid json", encoding="utf-8")
    request = _request(tmp_path, result_path)
    execution = _execution(0)

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert result.decision == "error"
    assert "not valid JSON" in result.reasons[0]


def test_wrong_schema_version_is_rejected(tmp_path):
    envelope = _envelope(tmp_path)
    envelope["schemaVersion"] = "some.other.schema/v1"
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(0)

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "schemaVersion" in result.reasons[0]


def test_invocation_id_mismatch_is_rejected(tmp_path):
    envelope = _envelope(tmp_path, invocation_id="some-other-invocation")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "invocation id" in result.reasons[0]


def test_exit_code_disagreement_with_outcome_is_rejected(tmp_path):
    envelope = _envelope(tmp_path, status="PASS", coverage="complete")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(99)  # should have been 0

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "producer integrity" in result.reasons[0]


def test_stale_head_is_rejected(tmp_path):
    envelope = _envelope(tmp_path, head=HEAD)
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head="c" * 40, base=tmp_path
    )

    assert result.accepted is False
    assert "stale evidence" in result.reasons[0]


def test_artifact_path_escape_is_rejected(tmp_path):
    envelope = _envelope(tmp_path, artifact_outside_repo=True)
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "escapes repository root" in result.reasons[0]


def test_bad_artifact_hash_is_rejected(tmp_path):
    envelope = _envelope(tmp_path, bad_artifact_hash=True)
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.accepted is False
    assert "artifact hash mismatch" in result.reasons[0]


def test_pass_with_risk_is_accepted_but_flagged_as_review_required(tmp_path):
    envelope = _envelope(tmp_path, status="PASS_WITH_RISK", coverage="complete")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS_WITH_RISK", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.decision == "review_required"
    assert result.accepted is True  # "accepted" here means "imported"; update_step.py still requires accept-risk separately


def test_do_not_ship_is_rejected_as_a_security_decision_not_a_verifier_error(tmp_path):
    envelope = _envelope(tmp_path, status="DO_NOT_SHIP", coverage="complete")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("DO_NOT_SHIP", "complete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.decision == "reject"
    assert result.accepted is False


def test_incomplete_coverage_forces_incomplete_decision_even_for_pass(tmp_path):
    envelope = _envelope(tmp_path, status="PASS", coverage="incomplete")
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "incomplete"))

    result = import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    assert result.decision == "incomplete"
    assert result.accepted is False


def test_no_partial_state_left_behind_on_a_late_failure(tmp_path):
    # Bad artifact hash fails AFTER schema/ID/exit-code checks pass, i.e.
    # late in the sequence — confirms no manifest dir is created at all.
    envelope = _envelope(tmp_path, bad_artifact_hash=True)
    result_path = _write_result_file(tmp_path, envelope)
    request = _request(tmp_path, result_path)
    execution = _execution(expected_exit_code("PASS", "complete"))

    import_verifier_result(
        request, execution, _config(), CHAT_ID, verifier_id=VERIFIER_ID, current_head=HEAD, base=tmp_path
    )

    from backend.visualization.paths import get_verifier_dir

    final_dir = get_verifier_dir(CHAT_ID, VERIFIER_ID, "STEP-1", "inv-1", tmp_path)
    assert not final_dir.exists()
    assert list(final_dir.parent.parent.glob(".tmp-*") if final_dir.parent.parent.exists() else []) == []
