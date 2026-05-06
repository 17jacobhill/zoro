import sys
import importlib

from backend.cli import cli as cli_module

update_step_module = importlib.import_module("backend.cli.commands.update_step")
prove_rule_module = importlib.import_module("backend.cli.commands.prove_rule")


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
        snippet_max_lines,
    ):
        captured["item_id"] = item_id
        captured["rule"] = rule
        captured["explanation"] = explanation
        captured["files"] = files
        captured["snippets"] = snippets
        captured["line_ranges"] = line_ranges
        captured["verdict"] = verdict
        captured["chat_id"] = chat_id
        captured["snippet_max_lines"] = snippet_max_lines

    monkeypatch.setattr(cli_module.prove_rule, "callback", fake_callback)
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
        "snippet_max_lines": 12,
    }

def test_prove_rule_decodes_escaped_newlines_and_persists_evidence(monkeypatch):
    captured = {}
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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
    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-1"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    prove_rule_module.prove_rule.callback(
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

    assert captured["chat_id"] == "chat-123"
    assert captured["item_id"] == "step-1-1"
    assert captured["rule"]["text"] == "Use repository pattern"
    assert captured["verification"]["code_blocks"][0]["file_path"] == "backend/service.py"
    assert captured["verification"]["code_blocks"][0]["code_snippet"] == "class Service:\n    pass"
    assert captured["verification"]["code_blocks"][0]["line_range"] == "10-11"
    assert captured["is_inherited"] is False
    assert "verifications" not in item["rules"][0]


def test_prove_rule_allows_prose_only_evidence(monkeypatch):
    captured = {}
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "workflow",
                "text": "Explain the change clearly",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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
    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-plain"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[workflow] Explain the change clearly",
        "This step only needs prose evidence for the appendix flow.",
        (),
        (),
        (),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
    )

    assert captured["chat_id"] == "chat-123"
    assert captured["verification"]["code_blocks"] == []
    assert captured["verification"]["explanation"] == "This step only needs prose evidence for the appendix flow."


def test_prove_rule_clamps_code_snippet_lines_by_default(monkeypatch):
    captured = {}
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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

    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-clamp-default"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    escaped_snippet = "\\n".join([f"line {i}" for i in range(1, 15)])
    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[architecture] Use repository pattern",
        "Proof with concise snippet",
        ("backend/service.py",),
        (escaped_snippet,),
        (),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
    )

    expected = "\n".join([f"line {i}" for i in range(1, 13)]) + "\n... (2 more lines omitted)"
    assert captured["verification"]["code_blocks"][0]["code_snippet"] == expected


def test_prove_rule_respects_snippet_max_lines_override(monkeypatch):
    captured = {}
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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

    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-clamp-override"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    escaped_snippet = "\\n".join([f"line {i}" for i in range(1, 15)])
    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[architecture] Use repository pattern",
        "Proof with override snippet limit",
        ("backend/service.py",),
        (escaped_snippet,),
        (),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
        20,
    )

    expected = "\n".join([f"line {i}" for i in range(1, 15)])
    assert captured["verification"]["code_blocks"][0]["code_snippet"] == expected


def test_prove_rule_requires_test_evidence_for_strict_testable_rule(monkeypatch, capsys):
    item = {
        "id": "step-1-1",
        "title": "Strict testable item",
        "rules": [
            {
                "category": "workflow",
                "text": "Verify with a test",
                "needs_strict_enforcement": True,
                "is_testable": True,
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}
    append_called = {"value": False}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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
    monkeypatch.setattr(
        prove_rule_module,
        "append_rule_verification_evidence",
        lambda chat_id, **kwargs: append_called.update({"value": True}) or {"record_id": "ev-missing-test"},
    )

    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[workflow] Verify with a test",
        "I complied but forgot to include tests.",
        (),
        (),
        (),
        "pass",
        None,
        None,
        None,
        None,
        None,
        None,
    )

    out = capsys.readouterr().out
    assert "requires test evidence" in out
    assert append_called["value"] is False


def test_prove_rule_requires_test_output_for_strict_testable_rule(monkeypatch, capsys):
    item = {
        "id": "step-1-1",
        "title": "Strict testable item",
        "rules": [
            {
                "category": "workflow",
                "text": "Verify with a test",
                "needs_strict_enforcement": True,
                "is_testable": True,
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}
    append_called = {"value": False}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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
    monkeypatch.setattr(
        prove_rule_module,
        "append_rule_verification_evidence",
        lambda chat_id, **kwargs: append_called.update({"value": True}) or {"record_id": "ev-missing-output"},
    )

    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[workflow] Verify with a test",
        "I provided most test metadata but not output.",
        (),
        (),
        (),
        "pass",
        "test_rule_compliance",
        "pytest tests/test_rule.py -k test_rule_compliance",
        "pass",
        None,
        "tests/test_rule.py",
        None,
    )

    out = capsys.readouterr().out
    assert "requires test evidence" in out
    assert append_called["value"] is False


def test_prove_rule_persists_test_evidence_for_strict_testable_rule(monkeypatch, tmp_path):
    captured = {}
    test_file = tmp_path / "test_rule.py"
    test_file.write_text("def test_rule_compliance():\n    assert True\n", encoding="utf-8")

    item = {
        "id": "step-1-1",
        "title": "Strict testable item",
        "rules": [
            {
                "category": "workflow",
                "text": "Verify with a test",
                "needs_strict_enforcement": True,
                "is_testable": True,
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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

    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-testable"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[workflow] Verify with a test",
        "Added and ran a dedicated regression test.",
        (),
        (),
        (),
        "pass",
        "test_rule_compliance",
        "pytest tests/test_rule.py -k test_rule_compliance",
        "pass",
        "1 passed",
        str(test_file),
        None,
    )

    test_evidence = captured["verification"]["test_evidence"]
    assert captured["chat_id"] == "chat-123"
    assert test_evidence["name"] == "test_rule_compliance"
    assert test_evidence["command"] == "pytest tests/test_rule.py -k test_rule_compliance"
    assert test_evidence["result"] == "pass"
    assert test_evidence["output"] == "1 passed"
    assert test_evidence["test_file"] == str(test_file)
    assert "test_rule_compliance" in test_evidence["test_code"]
    assert "enabled" not in test_evidence


def test_check_verification_requirements_reads_rule_proof_records(monkeypatch):
    item = {
        "id": "step-1-1",
        "children": [],
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
    }
    plan_data = {"plan": {"items": [item]}}
    monkeypatch.setattr(
        update_step_module,
        "load_evidence_document",
        lambda chat_id: {
            "records": [
                {
                    "source": "rule-verification",
                    "item_id": "step-1-1",
                    "rule_category": "architecture",
                    "rule_text": "Use repository pattern",
                    "verdict": "pass",
                }
            ]
        },
    )

    issues = update_step_module.check_verification_requirements("chat-123", plan_data, "step-1-1", "verification")

    assert issues == []


def test_check_verification_requirements_reports_missing_proof(monkeypatch):
    item = {
        "id": "step-1-1",
        "children": [],
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
    }
    plan_data = {"plan": {"items": [item]}}
    monkeypatch.setattr(update_step_module, "load_evidence_document", lambda chat_id: {"records": []})

    issues = update_step_module.check_verification_requirements("chat-123", plan_data, "step-1-1", "verification")

    assert issues == [
        {
            "type": "not_verified",
            "rule": item["rules"][0],
            "source": None,
            "strict": False,
        }
    ]


def test_prove_rule_rejects_literal_newlines(monkeypatch, capsys):
    item = {
        "id": "step-1-1",
        "title": "Test item",
        "rules": [
            {
                "category": "architecture",
                "text": "Use repository pattern",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [item]}}
    evidence_called = {"value": False}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(prove_rule_module, "find_item_by_id", lambda items, item_id: item)
    monkeypatch.setattr(
        prove_rule_module,
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
    monkeypatch.setattr(
        prove_rule_module,
        "append_rule_verification_evidence",
        lambda chat_id, **kwargs: evidence_called.update({"value": True}) or {"record_id": "ev-1"},
    )
    prove_rule_module.prove_rule.callback(
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
    assert evidence_called["value"] is False


def test_prove_rule_persists_inherited_rule_evidence(monkeypatch):
    captured = {}
    child_item = {
        "id": "step-1-1",
        "title": "Child step",
        "rules": [],
        "inherited_rules": [
            {
                "rule": {
                    "category": "architecture",
                    "text": "Use repository pattern",
                    "needs_strict_enforcement": True,
                },
                "source": "Parent step",
            }
        ],
        "children": [],
    }
    plan_data = {"plan": {"items": [child_item]}}

    monkeypatch.setattr(prove_rule_module, "get_chat_id_from_plan_md", lambda: "chat-123")
    monkeypatch.setattr(prove_rule_module, "load_plan_data", lambda chat_id: plan_data)
    monkeypatch.setattr(
        prove_rule_module,
        "collect_rules_for_item",
        lambda plan_data, item_id: [
            {
                "rule": child_item["inherited_rules"][0]["rule"],
                "source": "parent",
                "source_title": "Parent step",
                "is_inherited": True,
                "inherited_index": 0,
            }
        ],
    )
    def fake_append(chat_id, **kwargs):
        captured["chat_id"] = chat_id
        captured.update(kwargs)
        return {"record_id": "ev-2"}

    monkeypatch.setattr(prove_rule_module, "append_rule_verification_evidence", fake_append)

    prove_rule_module.prove_rule.callback(
        "step-1-1",
        "[architecture] Use repository pattern",
        "Detailed proof for inherited rule",
        ("backend/service.py",),
        ("class Service:\\n    pass",),
        ("10-11",),
        "pass",
        None,
        None,
        None,
        None,
        None,
        "chat-123",
    )

    assert captured["chat_id"] == "chat-123"
    assert captured["is_inherited"] is True
    assert captured["source_title"] == "Parent step"


def test_check_verification_requirements_accepts_inherited_rule_proof(monkeypatch):
    item = {
        "id": "step-1-1",
        "children": [],
        "rules": [],
        "inherited_rules": [
            {
                "rule": {
                    "category": "architecture",
                    "text": "Use repository pattern",
                    "needs_strict_enforcement": True,
                },
                "source": "Parent step",
            }
        ],
    }
    plan_data = {"plan": {"items": [item]}}
    monkeypatch.setattr(
        update_step_module,
        "load_evidence_document",
        lambda chat_id: {
            "records": [
                {
                    "source": "rule-verification",
                    "item_id": "step-1-1",
                    "rule_category": "architecture",
                    "rule_text": "Use repository pattern",
                    "verdict": "pass",
                    "is_inherited": True,
                }
            ]
        },
    )

    issues = update_step_module.check_verification_requirements("chat-123", plan_data, "step-1-1", "verification")

    assert issues == []
