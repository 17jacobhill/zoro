import json
import subprocess
import sys
import textwrap

import pytest

from backend.cli.commands.verify_step import verify_step
from backend.cli.commands.accept_risk import accept_risk
from backend.visualization.services.evidence_store import load_evidence_document
from backend.visualization.services.plan_persistence import save_plan_document

FAKE_VERIFIER_SCRIPT = textwrap.dedent(
    """
    import sys, json, os, hashlib

    def arg(name, default=None):
        if name in sys.argv:
            return sys.argv[sys.argv.index(name) + 1]
        return default

    repo = arg("--repo")
    invocation_id = arg("--invocation-id")
    step_id = arg("--step-id")
    head = arg("--expected-head")
    result_file = arg("--result-file")
    status = arg("--fake-status", "PASS")

    rule_ids = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--rule-id"]

    report_dir = os.path.join(repo, ".security-audit")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "report.json")
    with open(report_path, "w") as f:
        f.write("{}")
    with open(report_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    decision = {"PASS": "accept", "PASS_WITH_RISK": "review_required", "DO_NOT_SHIP": "reject"}[status]
    exit_code = {"PASS": 0, "PASS_WITH_RISK": 10, "DO_NOT_SHIP": 20}[status]

    envelope = {
        "schemaVersion": "zoro.security-audit.verifier-result/v1",
        "producer": {"name": "security-audit", "version": "0.1.0"},
        "invocation": {
            "id": invocation_id, "stepId": step_id, "ruleIds": rule_ids, "depth": "fast",
            "startedAt": "2026-01-01T00:00:00.000Z", "finishedAt": "2026-01-01T00:01:00.000Z",
        },
        "subject": {"repoRoot": repo, "git": {"head": head, "clean": True, "sourceDigest": "sha256:" + "0" * 64}},
        "outcome": {"status": status, "coverage": "complete", "decision": decision, "reasons": []},
        "checks": [],
        "artifacts": [{"kind": "report-json", "path": ".security-audit/report.json", "sha256": sha256}],
        "error": None,
    }
    with open(result_file, "w") as f:
        json.dump(envelope, f)
    sys.exit(exit_code)
    """
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _setup_project(tmp_path, monkeypatch, *, fake_status="PASS", rule_category="security", gated_category="security"):
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("hello")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    fake_script = tmp_path / "fake_verifier.py"
    fake_script.write_text(FAKE_VERIFIER_SCRIPT, encoding="utf-8")

    config_dir = tmp_path / ".zoro"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "verifiers": {
                    "security-audit": {
                        "kind": "command",
                        "argv": [
                            sys.executable,
                            str(fake_script),
                            "--repo",
                            "{repo_root}",
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
                            "--fake-status",
                            fake_status,
                        ],
                        "schema": "zoro.security-audit.verifier-result/v1",
                        "gated_rule_categories": [gated_category],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    chat_id = "chat-1"
    plan_data = {
        "plan": {
            "items": [
                {
                    "id": "step-1",
                    "children": [],
                    "rules": [{"category": rule_category, "text": "No hardcoded secrets"}],
                }
            ]
        }
    }
    save_plan_document(chat_id, plan_data)
    return chat_id


def test_verify_step_runs_the_fake_verifier_and_records_accepted_evidence(tmp_path, monkeypatch, capsys):
    chat_id = _setup_project(tmp_path, monkeypatch, fake_status="PASS")

    with pytest.raises(SystemExit) as exc_info:
        verify_step.callback("step-1", "security-audit", chat_id, None)
    assert exc_info.value.code == 0

    evidence = load_evidence_document(chat_id)
    records = [r for r in evidence["records"] if r.get("source") == "external-verifier"]
    assert len(records) == 1
    assert records[0]["raw_rule_result"]["decision"] == "accept"
    assert records[0]["raw_rule_result"]["status"] == "PASS"


def test_verify_step_with_no_gated_rules_does_not_run_anything(tmp_path, monkeypatch):
    chat_id = _setup_project(tmp_path, monkeypatch, fake_status="PASS", rule_category="security", gated_category="unrelated")
    # The plan's only rule is category "security", but the verifier only gates "unrelated".
    with pytest.raises(SystemExit) as exc_info:
        verify_step.callback("step-1", "security-audit", chat_id, None)
    assert exc_info.value.code == 1

    evidence = load_evidence_document(chat_id)
    assert evidence["records"] == []


def test_verify_step_then_accept_risk_end_to_end(tmp_path, monkeypatch, capsys):
    chat_id = _setup_project(tmp_path, monkeypatch, fake_status="PASS_WITH_RISK")
    monkeypatch.setenv("USER", "test-approver")

    with pytest.raises(SystemExit) as exc_info:
        verify_step.callback("step-1", "security-audit", chat_id, None)
    assert exc_info.value.code == 1  # PASS_WITH_RISK blocks until accepted

    evidence = load_evidence_document(chat_id)
    verifier_record = next(r for r in evidence["records"] if r.get("source") == "external-verifier")
    invocation_id = verifier_record["raw_rule_result"]["invocation_id"]

    import click.testing

    runner = click.testing.CliRunner()
    result = runner.invoke(
        accept_risk,
        ["step-1", "--invocation-id", invocation_id, "--reason", "Acceptable for this release", "--chat-id", chat_id],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "Risk accepted" in result.output

    evidence_after = load_evidence_document(chat_id)
    acceptance = [r for r in evidence_after["records"] if r.get("source") == "human-risk-acceptance"]
    assert len(acceptance) == 1
    assert acceptance[0]["raw_rule_result"]["invocation_id"] == invocation_id
    assert acceptance[0]["raw_rule_result"]["approver"] == "test-approver"


def test_accept_risk_refuses_when_no_matching_verifier_evidence_exists(tmp_path, monkeypatch):
    chat_id = _setup_project(tmp_path, monkeypatch, fake_status="PASS")

    import click.testing

    runner = click.testing.CliRunner()
    result = runner.invoke(
        accept_risk,
        ["step-1", "--invocation-id", "nonexistent-invocation", "--reason", "x", "--chat-id", chat_id],
    )
    assert result.exit_code != 0
    assert "No external-verifier evidence found" in result.output


def test_accept_risk_declined_at_the_confirmation_prompt_does_not_write_a_record(tmp_path, monkeypatch):
    chat_id = _setup_project(tmp_path, monkeypatch, fake_status="PASS_WITH_RISK")

    with pytest.raises(SystemExit):
        verify_step.callback("step-1", "security-audit", chat_id, None)

    evidence = load_evidence_document(chat_id)
    invocation_id = next(r for r in evidence["records"] if r.get("source") == "external-verifier")["raw_rule_result"]["invocation_id"]

    import click.testing

    runner = click.testing.CliRunner()
    result = runner.invoke(
        accept_risk,
        ["step-1", "--invocation-id", invocation_id, "--reason", "x", "--chat-id", chat_id],
        input="n\n",
    )
    assert result.exit_code != 0

    evidence_after = load_evidence_document(chat_id)
    assert not [r for r in evidence_after["records"] if r.get("source") == "human-risk-acceptance"]
