import sys
import importlib

from backend.cli import cli as cli_module

viz_update_module = importlib.import_module("backend.cli.commands.visualization.viz_update")
viz_verify_rule_module = importlib.import_module("backend.cli.commands.visualization.viz_verify_rule")


def test_prove_rule_dispatches_to_rule_callback(monkeypatch):
    captured = {}

    def fake_callback(
        item_id,
        rule,
        explanation,
        files,
        snippets,
        line_ranges,
        verdict,
        test_name,
        test_command,
        test_result,
        test_output,
        test_file,
        chat_id,
    ):
        captured["item_id"] = item_id
        captured["rule"] = rule
        captured["explanation"] = explanation
        captured["files"] = files
        captured["snippets"] = snippets
        captured["line_ranges"] = line_ranges
        captured["verdict"] = verdict
        captured["chat_id"] = chat_id

    monkeypatch.setattr(cli_module.viz_verify_rule, "callback", fake_callback)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "prove-rule",
            "step-1-1",
            "--rule",
            "[architecture] Use repo pattern",
            "--explanation",
            "Detailed proof",
            "--file",
            "backend/service.py",
            "--snippet",
            "class Service:\\n    pass",
            "--line-range",
            "10-11",
            "--verdict",
            "pass",
            "--chat-id",
            "chat-123",
        ],
    )

    cli_module.main()

    assert captured == {
        "item_id": "step-1-1",
        "rule": "[architecture] Use repo pattern",
        "explanation": "Detailed proof",
        "files": ("backend/service.py",),
        "snippets": ("class Service:\\n    pass",),
        "line_ranges": ("10-11",),
        "verdict": "pass",
        "chat_id": "chat-123",
    }


def test_viz_verify_rule_decodes_escaped_newlines_and_saves_verification(monkeypatch):
    saved = {}
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
                "verifications": [],
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(viz_verify_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(viz_verify_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(viz_verify_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        viz_verify_rule_module,
        "collect_rules_for_item",
        lambda plan_data, item_id: [
            {
                "rule": item["rules"][0],
                "source": "self",
                "source_title": item["title"],
                "is_inherited": False,
                "rule_index": 0,
            }
        ],
    )
    monkeypatch.setattr(viz_verify_rule_module, "_recalculate_inherited_rules", lambda items: None)
    monkeypatch.setattr(viz_verify_rule_module, "save_plan_data", lambda chat_id, data: saved.update({"chat_id": chat_id, "data": data}))
    monkeypatch.setattr(viz_verify_rule_module, "get_rule_test_evidence_enabled", lambda: False)

    viz_verify_rule_module.viz_verify_rule.callback(
        "step-1-1",
        "[architecture] Use repository pattern",
        "Detailed proof",
        ("backend/service.py",),
        ("class Service:\\n    pass",),
        ("10-11",),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
    )

    verification = item["rules"][0]["verifications"][0]
    assert saved["chat_id"] == "chat-123"
    assert verification["item_id"] == "step-1-1"
    assert verification["code_blocks"][0]["file_path"] == "backend/service.py"
    assert verification["code_blocks"][0]["code_snippet"] == "class Service:\n    pass"
    assert verification["code_blocks"][0]["line_range"] == "10-11"


def test_check_verification_requirements_no_longer_requires_step_verification():
    item = {
        "id": "step-1-1",
        "children": [],
        "step_verifications": [],
        "item_verifications": [],
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
                "verifications": [],
            }
        ],
    }
    plan_data = {"plan": {"items": [item]}}

    issues = viz_update_module.check_verification_requirements(item, plan_data, "step-1-1", "verification")

    assert issues == [
        {
            "type": "not_verified",
            "rule": item["rules"][0],
            "source": None,
            "strict": False,
        }
    ]


def test_viz_verify_rule_rejects_literal_newlines(monkeypatch, capsys):
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
                "verifications": [],
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}
    save_called = {"value": False}

    monkeypatch.setattr(viz_verify_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(viz_verify_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(viz_verify_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        viz_verify_rule_module,
        "collect_rules_for_item",
        lambda plan_data, item_id: [
            {
                "rule": item["rules"][0],
                "source": "self",
                "source_title": item["title"],
                "is_inherited": False,
                "rule_index": 0,
            }
        ],
    )
    monkeypatch.setattr(viz_verify_rule_module, "save_plan_data", lambda chat_id, data: save_called.update({"value": True}))
    monkeypatch.setattr(viz_verify_rule_module, "get_rule_test_evidence_enabled", lambda: False)

    viz_verify_rule_module.viz_verify_rule.callback(
        "step-1-1",
        "[architecture] Use repository pattern",
        "Detailed proof",
        ("backend/service.py",),
        ("class Service:\n    pass",),
        ("10-11",),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
    )

    out = capsys.readouterr().out
    assert "cannot contain literal newline characters" in out
    assert "escaped \\n inside --snippet" in out
    assert save_called["value"] is False
