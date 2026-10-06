import pytest
from pydantic import ValidationError

from backend.verifiers.schemas import VerifierCommandConfig, VerifierRequest
from backend.verifiers.security_audit import (
    build_argv,
    compute_decision,
    expected_exit_code,
    validate_envelope_shape,
)


def _request(**overrides):
    defaults = dict(
        invocation_id="inv-1",
        step_id="STEP-1",
        rule_ids=["RULE-1", "RULE-2"],
        repo_root="/repo",
        expected_head="a" * 40,
        result_path="/tmp/result.json",
        timeout_seconds=60,
    )
    defaults.update(overrides)
    return VerifierRequest(**defaults)


def _config(**overrides):
    defaults = dict(
        kind="command",
        argv=[
            "node",
            "/sec-audit/dist/cli/index.js",
            "verify",
            "--repo",
            "{repo_root}",
            "--depth",
            "deep",
            "--invocation-id",
            "{invocation_id}",
            "--step-id",
            "{step_id}",
            "{plan_id_args}",
            "{rule_id_args}",
            "--expected-head",
            "{git_head}",
            "--result-file",
            "{result_file}",
        ],
        schema="zoro.security-audit.verifier-result/v1",
    )
    defaults.update(overrides)
    return VerifierCommandConfig(**defaults)


def test_build_argv_substitutes_every_placeholder_as_separate_elements():
    argv = build_argv(_request(), _config())

    assert "--repo" in argv and argv[argv.index("--repo") + 1] == "/repo"
    assert "--invocation-id" in argv and argv[argv.index("--invocation-id") + 1] == "inv-1"
    assert "--expected-head" in argv and argv[argv.index("--expected-head") + 1] == "a" * 40
    assert "--result-file" in argv and argv[argv.index("--result-file") + 1] == "/tmp/result.json"
    # repeated --rule-id pairs, never joined into one string
    rule_id_positions = [i for i, token in enumerate(argv) if token == "--rule-id"]
    assert len(rule_id_positions) == 2
    assert argv[rule_id_positions[0] + 1] == "RULE-1"
    assert argv[rule_id_positions[1] + 1] == "RULE-2"


def test_plan_id_args_expands_to_nothing_when_plan_id_is_absent():
    argv = build_argv(_request(plan_id=None), _config())
    assert "--plan-id" not in argv
    assert "None" not in argv  # the exact bug this placeholder exists to avoid


def test_plan_id_args_expands_to_a_real_pair_when_present():
    argv = build_argv(_request(plan_id="PLAN-1"), _config())
    assert "--plan-id" in argv
    assert argv[argv.index("--plan-id") + 1] == "PLAN-1"


def test_expected_exit_code_prioritizes_incomplete_coverage_over_native_status():
    assert expected_exit_code("PASS", "incomplete") == 30
    assert expected_exit_code("DO_NOT_SHIP", "incomplete") == 30
    assert expected_exit_code("PASS", "complete") == 0
    assert expected_exit_code("PASS_WITH_RISK", "complete") == 10
    assert expected_exit_code("DO_NOT_SHIP", "complete") == 20


def test_compute_decision_matches_the_status_table():
    assert compute_decision("PASS", "complete") == "accept"
    assert compute_decision("PASS_WITH_RISK", "complete") == "review_required"
    assert compute_decision("DO_NOT_SHIP", "complete") == "reject"
    assert compute_decision("PASS", "incomplete") == "incomplete"
    assert compute_decision(None, "complete") == "error"


def _valid_envelope():
    return {
        "schemaVersion": "zoro.security-audit.verifier-result/v1",
        "producer": {"name": "security-audit", "version": "0.1.0"},
        "invocation": {
            "id": "inv-1",
            "stepId": "STEP-1",
            "ruleIds": ["RULE-1"],
            "depth": "fast",
            "startedAt": "2026-01-01T00:00:00.000Z",
            "finishedAt": "2026-01-01T00:01:00.000Z",
        },
        "subject": {
            "repoRoot": "/repo",
            "git": {"head": "a" * 40, "clean": True, "sourceDigest": "sha256:" + "b" * 64},
        },
        "outcome": {"status": "PASS", "coverage": "complete", "decision": "accept", "reasons": []},
        "checks": [],
        "artifacts": [],
        "error": None,
    }


def test_validate_envelope_shape_accepts_a_well_formed_envelope():
    envelope = validate_envelope_shape(_valid_envelope())
    assert envelope.outcome.status == "PASS"


def test_validate_envelope_shape_rejects_a_missing_required_field():
    payload = _valid_envelope()
    del payload["subject"]["git"]["head"]
    with pytest.raises(ValidationError):
        validate_envelope_shape(payload)


def test_validate_envelope_shape_rejects_an_unknown_top_level_field():
    payload = _valid_envelope()
    payload["unexpectedField"] = "should not be here"
    with pytest.raises(ValidationError):
        validate_envelope_shape(payload)
