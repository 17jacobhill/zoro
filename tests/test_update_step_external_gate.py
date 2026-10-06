import json

import importlib

update_step_module = importlib.import_module("backend.cli.commands.update_step")

from backend.verifiers.schemas import VerifierCommandConfig, VerifiersConfig

HEAD = "a" * 40


def _item(rule_overrides=None):
    rule = {"category": "security", "text": "No hardcoded secrets"}
    if rule_overrides:
        rule.update(rule_overrides)
    return {"id": "step-1", "children": [], "rules": [rule]}


def _plan(item):
    return {"plan": {"items": [item]}}


def _verifiers_config(gated_rule_categories=("security",), require_complete_coverage=True):
    return VerifiersConfig(
        verifiers={
            "security-audit": VerifierCommandConfig(
                kind="command",
                argv=["node", "verify"],
                schema="zoro.security-audit.verifier-result/v1",
                require_complete_coverage=require_complete_coverage,
                gated_rule_categories=list(gated_rule_categories),
            )
        }
    )


def _external_record(*, decision, invocation_id="inv-1", manifest_path=None, head=HEAD, tmp_path=None):
    if manifest_path is None and tmp_path is not None:
        manifest_path = str(tmp_path / "manifest.json")
        (tmp_path / "manifest.json").write_text(json.dumps({"source": {"head": head}}), encoding="utf-8")
    return {
        "source": "external-verifier",
        "item_id": "step-1",
        "raw_rule_result": {
            "verifier_id": "security-audit",
            "invocation_id": invocation_id,
            "manifest_path": manifest_path,
            "decision": decision,
        },
    }


def _patch(monkeypatch, verifiers_config, current_head=HEAD):
    monkeypatch.setattr(update_step_module, "get_verifiers_config", lambda: verifiers_config)
    monkeypatch.setattr(update_step_module, "_current_head_or_none", lambda: current_head)


def test_no_verifiers_configured_means_no_gating(monkeypatch):
    _patch(monkeypatch, VerifiersConfig())
    issues = update_step_module.check_external_verifier_requirements("chat-1", _plan(_item()), "step-1", {"records": []})
    assert issues == []


def test_rule_not_gated_by_any_verifier_is_unaffected(monkeypatch):
    _patch(monkeypatch, _verifiers_config(gated_rule_categories=["other-category"]))
    issues = update_step_module.check_external_verifier_requirements("chat-1", _plan(_item()), "step-1", {"records": []})
    assert issues == []


def test_gated_rule_with_no_evidence_at_all_is_blocked(monkeypatch):
    _patch(monkeypatch, _verifiers_config())
    issues = update_step_module.check_external_verifier_requirements("chat-1", _plan(_item()), "step-1", {"records": []})
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_missing"


def test_accept_decision_with_current_head_passes(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config())
    record = _external_record(decision="accept", tmp_path=tmp_path)
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [record]}
    )
    assert issues == []


def test_do_not_ship_decision_blocks_as_a_distinct_issue_type(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config())
    record = _external_record(decision="reject", tmp_path=tmp_path)
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [record]}
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_blocked"
    assert issues[0]["decision"] == "reject"


def test_incomplete_coverage_blocks_as_a_distinct_issue_type(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config())
    record = _external_record(decision="incomplete", tmp_path=tmp_path)
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [record]}
    )
    assert issues[0]["type"] == "external_verifier_blocked"
    assert issues[0]["decision"] == "incomplete"


def test_review_required_without_acceptance_is_blocked(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config())
    record = _external_record(decision="review_required", invocation_id="inv-risk", tmp_path=tmp_path)
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [record]}
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_risk_not_accepted"
    assert issues[0]["invocation_id"] == "inv-risk"


def test_review_required_with_a_matching_acceptance_record_passes(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config())
    verifier_record = _external_record(decision="review_required", invocation_id="inv-risk", tmp_path=tmp_path)
    acceptance_record = {
        "source": "human-risk-acceptance",
        "item_id": "step-1",
        "raw_rule_result": {"invocation_id": "inv-risk"},
    }
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [verifier_record, acceptance_record]}
    )
    assert issues == []


def test_a_prove_rule_record_alone_never_satisfies_the_external_gate(monkeypatch):
    _patch(monkeypatch, _verifiers_config())
    prove_rule_record = {
        "source": "rule-verification",
        "item_id": "step-1",
        "rule_category": "security",
        "rule_text": "No hardcoded secrets",
        "verdict": "pass",
    }
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [prove_rule_record]}
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_missing"


def test_evidence_is_stale_when_the_source_head_has_moved(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config(), current_head="b" * 40)  # HEAD moved since verify-step ran
    record = _external_record(decision="accept", head=HEAD, tmp_path=tmp_path)
    issues = update_step_module.check_external_verifier_requirements(
        "chat-1", _plan(_item()), "step-1", {"records": [record]}
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_stale"


def test_requires_verifier_field_also_gates_a_rule_regardless_of_category(monkeypatch, tmp_path):
    _patch(monkeypatch, _verifiers_config(gated_rule_categories=["unrelated-category"]))
    item = _item({"category": "unrelated-category", "requires_verifier": "security-audit"})
    issues = update_step_module.check_external_verifier_requirements("chat-1", _plan(item), "step-1", {"records": []})
    assert len(issues) == 1
    assert issues[0]["type"] == "external_verifier_missing"


def test_malformed_verifier_config_fails_closed(monkeypatch):
    from backend.verifiers.schemas import VerifierConfigError

    def _raise():
        raise VerifierConfigError("bad config")

    monkeypatch.setattr(update_step_module, "get_verifiers_config", _raise)
    issues = update_step_module.check_external_verifier_requirements("chat-1", _plan(_item()), "step-1", {"records": []})
    assert len(issues) == 1
    assert issues[0]["type"] == "verifier_config_error"
