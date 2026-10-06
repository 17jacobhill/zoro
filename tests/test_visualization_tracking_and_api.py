import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from backend.api import create_app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_visualization_workspace(root: Path, chat_id: str = "chat-123") -> None:
    vis_dir = root / ".zoro" / "visualization" / chat_id
    _write_json(
        vis_dir / "session.json",
        {
            "chat_id": chat_id,
            "name": "Demo Chat",
            "chat_file_path": str(root / "demo.jsonl"),
            "status": "paused",
            "plan_tracking": {},
            "created_at": "2026-04-20T00:00:00",
            "updated_at": "2026-04-20T00:00:00",
        },
    )
    _write_json(
        vis_dir / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "First step",
                        "description": "Ship the retained visualization flow.",
                        "rules": [],
                        "children": [],
                    }
                ]
            }
        },
    )


def _seed_knowledge_base(root: Path) -> None:
    _write_json(
        root / ".zoro" / "rules" / "structured" / "knowledge_base.json",
        {
            "items": [
                {
                    "item_id": "rule-1",
                    "type": "rule",
                    "category": "workflow",
                    "title": "Keep plans small",
                    "content": "Keep plans tight and visualization-centered.",
                    "context": None,
                    "evidence": None,
                    "confidence": 0.8,
                    "decay": 0.2,
                    "usage_count": 0,
                    "is_favorite": False,
                    "is_strict": False,
                    "is_testable": False,
                    "created_at": "2026-04-20T00:00:00",
                }
            ],
            "categories": ["workflow"],
        },
    )


def test_update_step_updates_visualization_tracking_and_markdown(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)

    visualization_manager = importlib.import_module("backend.visualization.services.visualization_manager")
    monkeypatch.setattr(visualization_manager, "VIS_DIR", tmp_path / ".zoro" / "visualization")
    monkeypatch.setattr(visualization_manager, "INDEX_FILE", visualization_manager.VIS_DIR / "index.json")

    update_step_module = importlib.import_module("backend.cli.commands.update_step")
    update_step_module.update_step.callback("step-1", "in_progress", "chat-123")

    metadata = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "session.json").read_text(encoding="utf-8")
    )
    assert metadata["plan_tracking"]["step-1"] == "in_progress"

    plan_markdown = (tmp_path / ".zoro" / "CURRENT_PLAN.md").read_text(encoding="utf-8")
    assert "# Visualization Plan: Demo Chat (chat-123)" in plan_markdown
    assert "**Status:** in_progress" in plan_markdown
    assert "zoro update-step step-1 completed" in plan_markdown


def test_get_plan_endpoint_normalizes_extraction_only_metadata(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "has_plan": True,
            "structure_type": "flat_steps",
            "plan": {
                "title": "Normalized plan",
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "First step",
                        "description": "Ship the retained visualization flow.",
                        "rules": [],
                        "children": [],
                    }
                ],
            },
        },
    )

    app = create_app()
    client = app.test_client()

    response = client.get("/api/chat-visualizations/chat-123/plan")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["plan"]["plan"]["title"] == "Normalized plan"
    assert payload["plan"]["plan"]["items"][0]["id"] == "step-1"
    assert "has_plan" not in payload["plan"]
    assert "structure_type" not in payload["plan"]


def test_add_note_writes_to_visualization_notes_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)

    add_note_module = importlib.import_module("backend.cli.commands.add_note")
    add_note_module.add_note.callback("step-1", "- preserved the visualization-only flow", "chat-123")

    notes_doc = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "notes.json").read_text(encoding="utf-8")
    )
    saved_note = next(iter(notes_doc["notes"].values()))

    assert saved_note["plan_item_id"] == "step-1"
    assert saved_note["source"] == "plan-item-note"
    assert saved_note["note_text"] == "- preserved the visualization-only flow"

    plan_data = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json").read_text(encoding="utf-8")
    )
    assert "notes" not in plan_data["plan"]["items"][0]


def test_add_note_normalizes_free_text_without_prompt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)

    add_note_module = importlib.import_module("backend.cli.commands.add_note")
    add_note_module.add_note.callback(
        "step-1",
        "UI behavior decision: keep the sidebar compact. Also preserve green accents.",
        "chat-123",
    )

    notes_doc = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "notes.json").read_text(encoding="utf-8")
    )
    saved_note = next(iter(notes_doc["notes"].values()))

    assert saved_note["note_text"] == "- keep the sidebar compact\n- preserve green accents."


def test_visualization_manager_ignores_legacy_generated_workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    visualization_manager = importlib.import_module("backend.visualization.services.visualization_manager")
    monkeypatch.setattr(visualization_manager, "VIS_DIR", tmp_path / ".zoro" / "visualization")
    monkeypatch.setattr(visualization_manager, "INDEX_FILE", visualization_manager.VIS_DIR / "index.json")

    legacy_dir = tmp_path / ".zoro" / "generated" / "visualization" / "chat-legacy"
    _write_json(
        legacy_dir / "metadata.json",
        {
            "chat_id": "chat-legacy",
            "name": "Legacy Chat",
            "chat_file_path": str(tmp_path / "legacy.jsonl"),
            "status": "paused",
            "plan_tracking": {},
            "created_at": "2026-04-20T00:00:00",
            "updated_at": "2026-04-20T00:00:00",
        },
    )
    _write_json(
        legacy_dir / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "Legacy step",
                        "description": "Keep loading old workspaces cleanly.",
                        "rules": [],
                        "children": [],
                    }
                ]
            }
        },
    )

    assert visualization_manager.get_visualization("chat-legacy") is None
    assert visualization_manager.list_visualizations() == []


def test_create_visualization_splits_session_and_runtime_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    visualization_manager = importlib.import_module("backend.visualization.services.visualization_manager")
    monkeypatch.setattr(visualization_manager, "VIS_DIR", tmp_path / ".zoro" / "visualization")
    monkeypatch.setattr(visualization_manager, "INDEX_FILE", visualization_manager.VIS_DIR / "index.json")

    chat_file = tmp_path / "demo.jsonl"
    chat_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(visualization_manager, "find_latest_chat_history_path", lambda: chat_file)
    monkeypatch.setattr(visualization_manager, "get_chat_history_source_from_config", lambda: "codex")

    metadata, error = visualization_manager.create_visualization(rule_retrieval_source="structured")

    assert error is None
    assert metadata is not None

    session_path = tmp_path / ".zoro" / "visualization" / metadata["chat_id"] / "session.json"
    runtime_path = tmp_path / ".zoro" / "visualization" / metadata["chat_id"] / "runtime.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))

    assert "accumulated_content" not in session
    assert session["status"] == "idle"
    assert "llm_model_snapshot" in session
    assert session["llm_model_snapshot"]["default_model"] == "gpt-5"
    assert runtime["token_count"] == 0
    assert runtime["latest_rule_learning"]["rules"] == []


def test_plan_persistence_strips_transient_proof_fields(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    chat_id = "chat-123"
    vis_dir = tmp_path / ".zoro" / "visualization" / chat_id
    _write_json(
        vis_dir / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "First step",
                        "description": "Keep the plan clean.",
                        "step_verifications": [{"verdict": "pass"}],
                        "item_verifications": [{"verdict": "pass"}],
                        "rules": [
                            {
                                "category": "architecture",
                                "text": "Use repository pattern",
                                "verifications": [{"verdict": "pass"}],
                            }
                        ],
                        "inherited_rules": [
                            {
                                "source": "Parent",
                                "verifications": [{"verdict": "pass"}],
                                "rule": {
                                    "category": "architecture",
                                    "text": "Use repository pattern",
                                    "verifications": [{"verdict": "pass"}],
                                },
                            }
                        ],
                        "children": [],
                    }
                ]
            }
        },
    )
    plan_persistence = importlib.import_module("backend.visualization.services.plan_persistence")
    plan_data = plan_persistence.load_plan_document(chat_id)
    item = plan_data["plan"]["items"][0]

    assert "step_verifications" not in item
    assert "item_verifications" not in item
    assert "verifications" not in item["rules"][0]
    assert "verifications" not in item["inherited_rules"][0]
    assert "verifications" not in item["inherited_rules"][0]["rule"]


def test_init_creates_zoro_md_and_agents_shim_without_clinerules(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_module = importlib.import_module("backend.cli.commands.init")
    captured_config = {}

    def fake_save_config(config):
        captured_config.update(config)

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), fake_save_config)

    assert (tmp_path / "ZORO.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".clinerules" / "zoro_integration.md").exists()
    assert captured_config["rule_test_evidence_enabled"] is True


def test_init_injects_zoro_protocol_into_existing_agents_idempotently(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_module = importlib.import_module("backend.cli.commands.init")
    cli_module = importlib.import_module("backend.cli.cli")

    existing_agents = "# Repo Rules\n\nKeep existing instructions.\n"
    (tmp_path / "AGENTS.md").write_text(existing_agents, encoding="utf-8")

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), cli_module.save_config)
    first_pass = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    assert "<!-- ZORO-PROTOCOL:START -->" in first_pass
    assert "<!-- ZORO-PROTOCOL:END -->" in first_pass
    assert "Keep existing instructions." in first_pass
    assert first_pass.index("<!-- ZORO-PROTOCOL:START -->") < first_pass.index("# Repo Rules")

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), cli_module.save_config)
    second_pass = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    assert second_pass == first_pass


def test_init_creates_claude_md_with_a_zoro_pointer_when_none_existed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_module = importlib.import_module("backend.cli.commands.init")

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), lambda config: None)

    claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "<!-- ZORO-PROTOCOL:START -->" in claude_md
    assert "@ZORO.md" in claude_md


def test_init_preserves_existing_claude_md_content_and_injects_one_block_idempotently(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_module = importlib.import_module("backend.cli.commands.init")
    cli_module = importlib.import_module("backend.cli.cli")

    existing_claude = "# My project\n\nAlways run tests before committing.\n"
    (tmp_path / "CLAUDE.md").write_text(existing_claude, encoding="utf-8")

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), cli_module.save_config)
    first_pass = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

    assert "<!-- ZORO-PROTOCOL:START -->" in first_pass
    assert "<!-- ZORO-PROTOCOL:END -->" in first_pass
    assert "Always run tests before committing." in first_pass
    assert "@ZORO.md" in first_pass

    init_module.cmd_init(SimpleNamespace(user_name="Jenny"), cli_module.save_config)
    second_pass = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

    assert second_pass == first_pass
    # Exactly one block, not re-prepended on every run.
    assert second_pass.count("<!-- ZORO-PROTOCOL:START -->") == 1


def test_kb_favorites_endpoints_cover_kb_and_manual_entries(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_knowledge_base(tmp_path)

    app = create_app()
    client = app.test_client()

    add_kb = client.post("/api/kb/favorites", json={"item_id": "rule-1"})
    assert add_kb.status_code == 200
    assert add_kb.get_json()["item"]["is_favorite"] is True

    add_manual = client.post(
        "/api/kb/favorites/manual",
        json={
            "rule": "Keep manual favorites available after the cleanup.",
            "reasoning": "Visualization rule review still needs manually curated favorites.",
            "category": "workflow",
            "title": "Manual favorite",
            "context": "Accepted from the rule learning panel.",
            "evidence": "Learned from chat-123",
            "confidence_reasoning": "Observed multiple repetitions in the session.",
            "decay_reasoning": "May shift if the protocol evolves.",
        },
    )
    assert add_manual.status_code == 200
    manual_rule = add_manual.get_json()["rule"]
    assert manual_rule["context"] == "Accepted from the rule learning panel."
    assert manual_rule["evidence"] == "Learned from chat-123"
    assert manual_rule["confidence_reasoning"] == "Observed multiple repetitions in the session."
    assert manual_rule["decay_reasoning"] == "May shift if the protocol evolves."

    favorites = client.get("/api/kb/favorites")
    assert favorites.status_code == 200
    favorite_ids = {item["item_id"] for item in favorites.get_json()["favorites"]}
    assert {"rule-1", manual_rule["item_id"]}.issubset(favorite_ids)

    remove_kb = client.delete("/api/kb/favorites/rule-1")
    assert remove_kb.status_code == 200

    remove_manual = client.delete(f"/api/kb/favorites/{manual_rule['item_id']}")
    assert remove_manual.status_code == 200

    favorites_after_delete = client.get("/api/kb/favorites").get_json()["favorites"]
    favorite_ids_after_delete = {item["item_id"] for item in favorites_after_delete}
    assert "rule-1" not in favorite_ids_after_delete
    assert manual_rule["item_id"] not in favorite_ids_after_delete


def test_create_app_registers_only_visualization_and_knowledge_blueprints(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    app = create_app()

    assert set(app.blueprints.keys()) == {"visualization", "knowledge"}


def test_create_app_recovers_polling_status_to_paused(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)

    session_path = tmp_path / ".zoro" / "visualization" / "chat-123" / "session.json"
    session_data = json.loads(session_path.read_text(encoding="utf-8"))
    session_data["status"] = "polling"
    session_path.write_text(json.dumps(session_data, indent=2), encoding="utf-8")

    app = create_app()
    assert set(app.blueprints.keys()) == {"visualization", "knowledge"}

    recovered = json.loads(session_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "paused"


def test_import_repo_agents_structures_repo_root_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "# AGENTS.md\n\nFollow ZORO.md.\n\nRead `.zoro/CURRENT_PLAN.md` before acting.\n",
        encoding="utf-8",
    )

    processing_module = importlib.import_module("backend.routes.knowledge_api.processing")

    class FakeProvider:
        def chat_completion(self, messages, model, response_format=None, **kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "type": "rule",
                            "category": "workflow",
                            "title": "Follow ZORO",
                            "content": "Follow the Zoro workflow defined in `ZORO.md`.",
                            "context": None,
                            "evidence": "Follow ZORO.md",
                            "confidence": 0.9,
                            "decay": 0.2,
                            "confidence_reasoning": "Explicitly stated in the repo instructions.",
                            "decay_reasoning": "This protocol is expected to remain stable.",
                        },
                        {
                            "type": "rule",
                            "category": "setup",
                            "title": "Read current plan",
                            "content": "Read `.zoro/CURRENT_PLAN.md` before acting.",
                            "context": "Applies to agents working in this repository.",
                            "evidence": "Read `.zoro/CURRENT_PLAN.md` before acting.",
                            "confidence": 0.95,
                            "decay": 0.15,
                            "confidence_reasoning": "The instruction is direct and unambiguous.",
                            "decay_reasoning": "May change only if the plan filename changes.",
                        },
                    ]
                }
            )

    monkeypatch.setattr(processing_module, "get_default_provider", lambda: FakeProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/kb/files/import-agents", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["filename"] == "AGENTS.md"
    assert payload["items_added"] == 2
    assert payload["replaced_previous_count"] == 0
    assert payload["processed_path"].startswith(".zoro/rules/unstructured/processed/repo_AGENTS_")

    kb = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json").read_text(encoding="utf-8")
    )
    imported_items = [item for item in kb["items"] if item["source_file"] == "repo:AGENTS.md"]
    assert len(imported_items) == 2

    processing_log = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "processing_log.json").read_text(encoding="utf-8")
    )
    assert processing_log["files"]["repo:AGENTS.md"]["items_processed"] == 1
    assert processing_log["files"]["repo:AGENTS.md"]["processed_chunks"] == 1
    assert processing_log["files"]["repo:AGENTS.md"]["runs"][-1]["items_added"] == 2
    assert processing_log["files"]["repo:AGENTS.md"]["source_path"] == "AGENTS.md"

    second_response = client.post("/api/kb/files/import-agents", json={})
    second_payload = second_response.get_json()
    assert second_response.status_code == 200
    assert second_payload["items_added"] == 0
    assert "already up to date" in second_payload["message"]


def test_count_unstructured_files_includes_nested_markdown_and_skips_processed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    (unstructured_dir / "nested").mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "processed").mkdir(parents=True, exist_ok=True)

    (unstructured_dir / "root.md").write_text(
        "## Category: workflow\nKeep protocol checks.\n\n## Category: quality\nPrefer smaller modules.\n",
        encoding="utf-8",
    )
    (unstructured_dir / "nested" / "notes.md").write_text(
        "## Category: docs\nCapture implementation notes.\n",
        encoding="utf-8",
    )
    (unstructured_dir / "processed" / "old.md").write_text(
        "## Category: ignored\nProcessed snapshots should not reappear.\n",
        encoding="utf-8",
    )

    app = create_app()
    client = app.test_client()

    response = client.get("/api/kb/files/unstructured/count")
    assert response.status_code == 200

    payload = response.get_json()
    files = payload["files"]
    by_name = {entry["filename"]: entry for entry in files}

    assert set(by_name.keys()) == {"nested/notes.md", "root.md"}
    assert by_name["root.md"]["total_items"] >= 1
    assert by_name["nested/notes.md"]["total_items"] >= 1
    assert payload["total_pending"] == 2
    assert payload["total_pending_chunks"] == (
        by_name["root.md"]["pending_chunks"] + by_name["nested/notes.md"]["pending_chunks"]
    )
    assert payload["total_unprocessed_percent"] == 100.0


def test_count_unstructured_files_handles_heading_based_markdown(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    unstructured_dir.mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "playbook.md").write_text(
        "# Team Workflow\nKeep pull requests focused.\n\n## Testing Strategy\nAdd a regression test for bug fixes.\n",
        encoding="utf-8",
    )

    app = create_app()
    client = app.test_client()

    response = client.get("/api/kb/files/unstructured/count")
    assert response.status_code == 200

    payload = response.get_json()
    files = payload["files"]
    by_name = {entry["filename"]: entry for entry in files}
    assert "playbook.md" in by_name
    assert by_name["playbook.md"]["total_items"] >= 1
    assert payload["total_pending"] == 1
    assert payload["total_pending_chunks"] == by_name["playbook.md"]["pending_chunks"]


def test_process_unstructured_supports_nested_relative_filenames(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    (unstructured_dir / "nested").mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "nested" / "playbook.md").write_text(
        "## Category: workflow\nFollow the current plan order.\n",
        encoding="utf-8",
    )

    processing_module = importlib.import_module("backend.routes.knowledge_api.processing")

    class FakeProvider:
        def chat_completion(self, messages, model, response_format=None, **kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "type": "rule",
                            "category": "workflow",
                            "title": "Follow plan order",
                            "content": "Follow the current plan order.",
                            "context": None,
                            "evidence": None,
                            "confidence": 0.9,
                            "decay": 0.2,
                            "confidence_reasoning": None,
                            "decay_reasoning": None,
                        }
                    ]
                }
            )

    monkeypatch.setattr(processing_module, "get_default_provider", lambda: FakeProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/kb/process", json={"files": ["nested/playbook.md"]})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["total_added"] == 1
    result = payload["results"][0]
    assert result["success"] is True
    assert result["filename"] == "nested/playbook.md"
    assert result["processed_path"].startswith(".zoro/rules/unstructured/processed/nested__playbook_")

    kb = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json").read_text(encoding="utf-8")
    )
    imported_items = [item for item in kb["items"] if item.get("source_file") == "nested/playbook.md"]
    assert len(imported_items) == 1

    processing_log = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "processing_log.json").read_text(encoding="utf-8")
    )
    assert processing_log["files"]["nested/playbook.md"]["items_processed"] == 1


def test_process_unstructured_tolerates_section_item_count_mismatch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    unstructured_dir.mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "notes.md").write_text(
        "# Build Rules\nKeep API responses typed.\n\n## UI Rules\nShow explicit loading states.\n",
        encoding="utf-8",
    )

    processing_module = importlib.import_module("backend.routes.knowledge_api.processing")

    class FakeProvider:
        def chat_completion(self, messages, model, response_format=None, **kwargs):
            # Intentionally return fewer items than detected sections to verify we no longer hard-fail.
            return json.dumps(
                {
                    "items": [
                        {
                            "type": "rule",
                            "category": "api-contract",
                            "title": "Keep API responses typed",
                            "content": "Keep API responses typed.",
                            "context": None,
                            "evidence": None,
                            "confidence": 0.8,
                            "decay": 0.4,
                            "confidence_reasoning": None,
                            "decay_reasoning": None,
                        }
                    ]
                }
            )

    monkeypatch.setattr(processing_module, "get_default_provider", lambda: FakeProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/kb/process", json={"files": ["notes.md"]})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["total_added"] == 1
    result = payload["results"][0]
    assert result["success"] is True
    assert result["pre_count"] >= 1
    assert result["post_count"] == 1

    processing_log = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "processing_log.json").read_text(encoding="utf-8")
    )
    assert processing_log["files"]["notes.md"]["items_processed"] >= 1


def test_process_unstructured_replaces_existing_items_for_same_source(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    unstructured_dir.mkdir(parents=True, exist_ok=True)
    file_path = unstructured_dir / "rules.md"
    file_path.write_text("## Category: workflow\nRule A\n", encoding="utf-8")

    processing_module = importlib.import_module("backend.routes.knowledge_api.processing")
    responses = [
        {
            "items": [
                {
                    "type": "rule",
                    "category": "workflow",
                    "title": "Rule A",
                    "content": "Rule A",
                    "context": None,
                    "evidence": None,
                    "confidence": 0.9,
                    "decay": 0.2,
                    "confidence_reasoning": None,
                    "decay_reasoning": None,
                }
            ]
        },
        {
            "items": [
                {
                    "type": "rule",
                    "category": "workflow",
                    "title": "Rule B",
                    "content": "Rule B",
                    "context": None,
                    "evidence": None,
                    "confidence": 0.8,
                    "decay": 0.3,
                    "confidence_reasoning": None,
                    "decay_reasoning": None,
                }
            ]
        },
    ]

    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def chat_completion(self, messages, model, response_format=None, **kwargs):
            idx = min(self.calls, len(responses) - 1)
            self.calls += 1
            return json.dumps(responses[idx])

    provider = FakeProvider()
    monkeypatch.setattr(processing_module, "get_default_provider", lambda: provider)

    app = create_app()
    client = app.test_client()

    first = client.post("/api/kb/process", json={"files": ["rules.md"]})
    assert first.status_code == 200
    assert first.get_json()["total_added"] == 1

    file_path.write_text("## Category: workflow\nRule B\n", encoding="utf-8")
    second = client.post("/api/kb/process", json={"files": ["rules.md"]})
    assert second.status_code == 200
    assert second.get_json()["total_added"] == 1

    kb = json.loads(
        (tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json").read_text(encoding="utf-8")
    )
    source_items = [item for item in kb["items"] if item.get("source_file") == "rules.md"]
    assert len(source_items) == 1
    assert source_items[0]["title"] == "Rule B"
    assert source_items[0]["content"] == "Rule B"


def test_count_unstructured_files_reports_zero_unprocessed_after_processing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    unstructured_dir.mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "notes.md").write_text("## Category: docs\nCapture notes.\n", encoding="utf-8")

    processing_module = importlib.import_module("backend.routes.knowledge_api.processing")

    class FakeProvider:
        def chat_completion(self, messages, model, response_format=None, **kwargs):
            return json.dumps(
                {
                    "items": [
                        {
                            "type": "doc",
                            "category": "docs",
                            "title": "Capture notes",
                            "content": "Capture notes.",
                            "context": None,
                            "evidence": None,
                            "confidence": None,
                            "decay": None,
                            "confidence_reasoning": None,
                            "decay_reasoning": None,
                        }
                    ]
                }
            )

    monkeypatch.setattr(processing_module, "get_default_provider", lambda: FakeProvider())

    app = create_app()
    client = app.test_client()

    process_response = client.post("/api/kb/process", json={"files": ["notes.md"]})
    assert process_response.status_code == 200

    count_response = client.get("/api/kb/files/unstructured/count")
    assert count_response.status_code == 200
    payload = count_response.get_json()

    file_entry = payload["files"][0]
    assert file_entry["filename"] == "notes.md"
    assert file_entry["unprocessed_percent"] == 0.0
    assert payload["total_pending"] == 0
    assert payload["total_unprocessed_percent"] == 0.0


def test_process_unstructured_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = app.test_client()

    response = client.post("/api/kb/process", json={"files": ["../outside.md"]})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["total_added"] == 0
    assert payload["results"][0]["success"] is False
    assert payload["results"][0]["error"] == "Invalid file path"


def test_unstructured_rule_retrieval_includes_nested_markdown_and_skips_processed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    unstructured_dir = tmp_path / ".zoro" / "rules" / "unstructured"
    (unstructured_dir / "nested").mkdir(parents=True, exist_ok=True)
    (unstructured_dir / "processed").mkdir(parents=True, exist_ok=True)

    (unstructured_dir / "root.md").write_text("Root guidance", encoding="utf-8")
    (unstructured_dir / "nested" / "notes.md").write_text("Nested guidance", encoding="utf-8")
    (unstructured_dir / "processed" / "old.md").write_text("Old guidance", encoding="utf-8")

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")
    rules = plans_module._load_rule_retrieval_items("unstructured")

    sources = {rule["source_file"] for rule in rules}
    assert sources == {"nested/notes.md", "root.md"}


def test_detect_duplicates_endpoint_uses_prompt_items_list_placeholder(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json",
        {
            "items": [
                {
                    "item_id": "rule-1",
                    "type": "rule",
                    "category": "workflow",
                    "title": "Follow protocol",
                    "content": "Follow protocol checks.",
                    "confidence": 0.8,
                    "decay": 0.2,
                },
                {
                    "item_id": "rule-2",
                    "type": "rule",
                    "category": "workflow",
                    "title": "Use protocol checks",
                    "content": "Use protocol checks before merge.",
                    "confidence": 0.7,
                    "decay": 0.3,
                },
            ],
            "categories": ["workflow"],
        },
    )

    duplicates_module = importlib.import_module("backend.routes.knowledge_api.duplicates")

    class FakeProvider:
        def chat_completion(self, messages, model, response_format=None, **kwargs):
            payload = messages[0]["content"]
            assert "Items to analyze:" in payload
            assert '"item_id": "rule-1"' in payload
            return json.dumps(
                {
                    "groups": [
                        {
                            "item_ids": ["rule-1", "rule-2"],
                            "similarity_score": 0.92,
                            "is_conflict": False,
                            "reasoning": "Same protocol intent.",
                            "merged_title": "Protocol checks",
                            "merged_content": "Run protocol checks before merging.",
                            "merged_context": None,
                            "merged_evidence": None,
                            "merged_confidence": 0.86,
                            "merged_decay": 0.24,
                            "scoring_explanation": "Agreement boost and lower decay.",
                        }
                    ]
                }
            )

    monkeypatch.setattr(duplicates_module, "get_default_provider", lambda: FakeProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/kb/duplicates/detect", json={})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert len(payload["duplicates"]) == 1
    assert payload["duplicates"][0]["item_ids"] == ["rule-1", "rule-2"]
    assert payload["duplicates"][0]["merged_title"] == "Protocol checks"


def test_zoro_api_backend_only_skips_frontend_and_browser(monkeypatch):
    api_module = importlib.import_module("backend.api")
    captured = {}

    monkeypatch.setattr(
        api_module,
        "_start_frontend_dev_server",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("frontend launcher should not run in backend-only mode")
        ),
    )
    monkeypatch.setattr(
        api_module.webbrowser,
        "open",
        lambda *args, **kwargs: captured.setdefault("browser", True),
    )
    monkeypatch.setattr(
        api_module,
        "serve_api",
        lambda **kwargs: captured.setdefault("serve_api", kwargs),
    )

    api_module.main(["--backend-only", "--no-browser", "--no-debug"])

    assert "browser" not in captured
    assert captured["serve_api"]["debug"] is False
    assert captured["serve_api"]["host"] == api_module.DEFAULT_BACKEND_HOST
    assert captured["serve_api"]["port"] == api_module.DEFAULT_BACKEND_PORT


def test_zoro_api_launches_browser_when_frontend_is_reachable(monkeypatch):
    api_module = importlib.import_module("backend.api")
    captured = {}

    monkeypatch.setattr(
        api_module,
        "_start_frontend_dev_server",
        lambda *args, **kwargs: (None, "Launched frontend dev server"),
    )
    monkeypatch.setattr(api_module, "_port_is_open", lambda host, port: True)
    monkeypatch.setattr(
        api_module.webbrowser,
        "open",
        lambda url, new=1: captured.setdefault("browser_url", url),
    )
    monkeypatch.setattr(
        api_module,
        "serve_api",
        lambda **kwargs: captured.setdefault("serve_api", kwargs),
    )

    api_module.main(["--no-debug"])

    assert captured["browser_url"] == "http://127.0.0.1:5274"
    assert captured["serve_api"]["debug"] is False


def test_evidence_endpoint_reads_canonical_evidence_records(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "evidence.json",
        {
            "chat_id": "chat-123",
            "records": [
                {
                    "record_id": "ev-1",
                    "item_id": "step-1",
                    "rule_category": "architecture",
                    "rule_text": "Use repository pattern",
                    "source": "rule-verification",
                    "explanation": "Repository created in backend/service.py",
                    "artifacts": [{"file_path": "backend/service.py", "code_snippet": "class Service: pass"}],
                    "verdict": "pass",
                    "timestamp": "2026-04-20T00:00:00+00:00",
                }
            ],
        },
    )

    app = create_app()
    client = app.test_client()

    response = client.get("/api/chat-visualizations/chat-123/evidence")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["evidence"][0]["rule_text"] == "Use repository pattern"
    assert payload["evidence"][0]["source"] == "rule-verification"


def test_bootstrap_plan_endpoint_extracts_and_enriches_in_one_call(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _seed_knowledge_base(tmp_path)

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def chat_completion(self, messages, model):
            self.calls += 1
            if self.calls == 1:
                return json.dumps(
                    {
                        "plan": {
                            "title": "Extracted Plan",
                            "items": [
                                {
                                    "id": "step-1",
                                    "number": "1",
                                    "title": "First step",
                                    "description": "Extracted from chat.",
                                    "rules": [],
                                    "children": [],
                                }
                            ],
                        }
                    }
                )

            return json.dumps(
                {
                    "plan": {
                        "title": "Extracted Plan",
                        "items": [
                            {
                                "id": "step-1",
                                "number": "1",
                                "title": "First step",
                                "description": "Extracted from chat.",
                                "rules": [
                                    {
                                        "kb_item_id": "rule-1",
                                        "category": "workflow",
                                        "text": "Keep plans tight and visualization-centered.",
                                        "needs_strict_enforcement": False,
                                        "is_testable": False,
                                    }
                                ],
                                "children": [],
                            }
                        ],
                    }
                }
            )

    fake_provider = FakeProvider()
    monkeypatch.setattr(plans_module, "get_default_provider", lambda: fake_provider)

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat-visualizations/chat-123/bootstrap-plan",
        json={"content": "User asked to scaffold a simple one-step plan."},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["rules_applied"] is True
    assert payload["rules_attached_count"] == 1
    assert payload["rule_retrieval_source"] == "structured"
    assert payload["warnings"] == []
    assert fake_provider.calls == 2

    saved_plan = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json").read_text(encoding="utf-8")
    )
    saved_rules = saved_plan["plan"]["items"][0]["rules"]
    assert len(saved_rules) == 1
    assert saved_rules[0]["kb_item_id"] == "rule-1"
    assert saved_rules[0]["text"] == "Keep plans tight and visualization-centered."


def test_bootstrap_plan_uses_latest_assistant_plan_block(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _seed_knowledge_base(tmp_path)

    codex_lines = [
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "## Implementation Plan\n1. Stale Step\n2. Keep old structure.",
                    }
                ],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Can you update it with a better plan?"}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": (
                            "## Implementation Changes\n"
                            "1. Fresh Step\n"
                            "2. Add regression tests\n"
                            "### Test Plan\n"
                            "- [ ] Run pytest"
                        ),
                    }
                ],
            },
        },
    ]
    (tmp_path / "demo.jsonl").write_text(
        "\n".join(json.dumps(line) for line in codex_lines),
        encoding="utf-8",
    )

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FakeProvider:
        def __init__(self):
            self.calls = 0
            self.extraction_prompt = ""

        def chat_completion(self, messages, model):
            self.calls += 1
            if self.calls == 1:
                self.extraction_prompt = messages[0]["content"]
                return json.dumps(
                    {
                        "plan": {
                            "title": "Fresh Plan",
                            "items": [
                                {
                                    "id": "step-1",
                                    "number": "1",
                                    "title": "Fresh Step",
                                    "description": "Use the newest plan from chat history.",
                                    "rules": [],
                                    "children": [],
                                }
                            ],
                        }
                    }
                )

            return json.dumps(
                {
                    "plan": {
                        "title": "Fresh Plan",
                        "items": [
                            {
                                "id": "step-1",
                                "number": "1",
                                "title": "Fresh Step",
                                "description": "Use the newest plan from chat history.",
                                "rules": [
                                    {
                                        "kb_item_id": "rule-1",
                                        "category": "workflow",
                                        "text": "Keep plans tight and visualization-centered.",
                                        "needs_strict_enforcement": False,
                                        "is_testable": False,
                                    }
                                ],
                                "children": [],
                            }
                        ],
                    }
                }
            )

    fake_provider = FakeProvider()
    monkeypatch.setattr(plans_module, "get_default_provider", lambda: fake_provider)

    app = create_app()
    client = app.test_client()

    response = client.post("/api/chat-visualizations/chat-123/bootstrap-plan", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["plan_detected"] is True
    assert payload["rules_attached_count"] == 1
    assert payload["rule_retrieval_source"] == "structured"
    assert fake_provider.calls == 2
    assert "Fresh Step" in fake_provider.extraction_prompt
    assert "Stale Step" not in fake_provider.extraction_prompt


def test_prepare_play_extracts_plan_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _seed_knowledge_base(tmp_path)
    (tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json").unlink()

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def chat_completion(self, messages, model):
            self.calls += 1
            if self.calls == 1:
                return json.dumps(
                    {
                        "plan": {
                            "title": "Extracted Plan",
                            "items": [
                                {
                                    "id": "step-1",
                                    "number": "1",
                                    "title": "First step",
                                    "description": "Extracted from chat.",
                                    "rules": [],
                                    "children": [],
                                }
                            ],
                        }
                    }
                )

            return json.dumps(
                {
                    "plan": {
                        "title": "Extracted Plan",
                        "items": [
                            {
                                "id": "step-1",
                                "number": "1",
                                "title": "First step",
                                "description": "Extracted from chat.",
                                "rules": [
                                    {
                                        "kb_item_id": "rule-1",
                                        "category": "workflow",
                                        "text": "Keep plans tight and visualization-centered.",
                                        "needs_strict_enforcement": False,
                                        "is_testable": False,
                                    }
                                ],
                                "children": [],
                            }
                        ],
                    }
                }
            )

    fake_provider = FakeProvider()
    monkeypatch.setattr(plans_module, "get_default_provider", lambda: fake_provider)

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat-visualizations/chat-123/prepare-play",
        json={"content": "Please create a concise implementation plan."},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["play_action"] == "extract_plan"
    assert payload["plan_detected"] is True
    assert payload["rules_applied"] is True
    assert payload["rules_attached_count"] == 1
    assert fake_provider.calls == 2


def test_prepare_play_enriches_existing_plan_when_rules_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _seed_knowledge_base(tmp_path)

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def chat_completion(self, messages, model):
            self.calls += 1
            return json.dumps(
                {
                    "plan": {
                        "title": "Demo Plan",
                        "items": [
                            {
                                "id": "step-1",
                                "number": "1",
                                "title": "First step",
                                "description": "Ship the retained visualization flow.",
                                "rules": [
                                    {
                                        "kb_item_id": "rule-1",
                                        "category": "workflow",
                                        "text": "Keep plans tight and visualization-centered.",
                                        "needs_strict_enforcement": False,
                                        "is_testable": False,
                                    }
                                ],
                                "children": [],
                            }
                        ],
                    }
                }
            )

    fake_provider = FakeProvider()
    monkeypatch.setattr(plans_module, "get_default_provider", lambda: fake_provider)

    app = create_app()
    client = app.test_client()

    response = client.post("/api/chat-visualizations/chat-123/prepare-play", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["play_action"] == "enrich_plan"
    assert payload["rules_applied"] is True
    assert payload["rules_attached_count"] == 1
    assert fake_provider.calls == 1


def test_prepare_play_skips_llm_when_plan_already_enriched(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "First step",
                        "description": "Already enriched.",
                        "rules": [
                            {
                                "category": "workflow",
                                "text": "Keep plans tight and visualization-centered.",
                                "needs_strict_enforcement": False,
                                "is_testable": False,
                            }
                        ],
                        "children": [],
                    }
                ]
            }
        },
    )

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FailingProvider:
        def chat_completion(self, messages, model):
            raise AssertionError("LLM should not run for already-enriched plans")

    monkeypatch.setattr(plans_module, "get_default_provider", lambda: FailingProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/chat-visualizations/chat-123/prepare-play", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["play_action"] == "sync_chat_only"
    assert payload["rules_applied"] is True
    assert payload["rules_attached_count"] == 1


def test_prepare_play_treats_inherited_rules_as_enriched(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "First step",
                        "description": "Inherited rules already present.",
                        "rules": [],
                        "inherited_rules": [
                            {
                                "rule": {
                                    "category": "workflow",
                                    "text": "Keep plans tight and visualization-centered.",
                                },
                                "source": "Parent step",
                            }
                        ],
                        "children": [],
                    }
                ]
            }
        },
    )

    plans_module = importlib.import_module("backend.routes.visualization_api.plans")

    class FailingProvider:
        def chat_completion(self, messages, model):
            raise AssertionError("LLM should not run when inherited rules already exist")

    monkeypatch.setattr(plans_module, "get_default_provider", lambda: FailingProvider())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/chat-visualizations/chat-123/prepare-play", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["play_action"] == "sync_chat_only"
    assert payload["rules_applied"] is True
    assert payload["rules_attached_count"] == 1


def test_move_plan_item_endpoint_reorders_existing_siblings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "plan": {
                "items": [
                    {"id": "step-1", "number": "1", "title": "First", "description": "", "rules": [], "children": []},
                    {"id": "step-2", "number": "2", "title": "Second", "description": "", "rules": [], "children": []},
                    {"id": "step-3", "number": "3", "title": "Third", "description": "", "rules": [], "children": []},
                ]
            }
        },
    )

    app = create_app()
    client = app.test_client()

    move_up = client.post("/api/chat-visualizations/chat-123/plan/items/step-2/move", json={"direction": "up"})
    assert move_up.status_code == 200
    assert move_up.get_json()["success"] is True

    updated_plan = json.loads(
        (tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json").read_text(encoding="utf-8")
    )
    items = updated_plan["plan"]["items"]
    assert [item["id"] for item in items] == ["step-2", "step-1", "step-3"]
    assert [item["number"] for item in items] == ["1", "2", "3"]

    blocked_move = client.post("/api/chat-visualizations/chat-123/plan/items/step-2/move", json={"direction": "up"})
    assert blocked_move.status_code == 400
    assert "Cannot move item up" in blocked_move.get_json()["error"]


def test_get_supervision_includes_rules_in_focus_snapshot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "Parent step",
                        "description": "",
                        "rules": [
                            {
                                "category": "workflow",
                                "text": "Use protocol checks",
                                "needs_strict_enforcement": True,
                                "is_testable": True,
                            }
                        ],
                        "children": [
                            {
                                "id": "step-1-1",
                                "number": "1.1",
                                "title": "Child step",
                                "description": "",
                                "rules": [{"category": "quality", "text": "Keep logs clean"}],
                                "inherited_rules": [
                                    {
                                        "source": "Parent step",
                                        "rule": {
                                            "category": "workflow",
                                            "text": "Use protocol checks",
                                            "needs_strict_enforcement": True,
                                            "is_testable": True,
                                        },
                                    }
                                ],
                                "children": [],
                            }
                        ],
                    }
                ]
            }
        },
    )
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "monitoring.json",
        [
            {
                "status": "needs_attention",
                "summary": "Agent drifted from expected order.",
                "current_step": "step-1-1",
                "expected_step": "step-1",
                "action_required": ["Pause and re-align to plan order."],
                "timestamp": "2026-04-20T00:00:00",
            }
        ],
    )

    app = create_app()
    client = app.test_client()

    response = client.get("/api/visualization/supervision/chat-123")
    assert response.status_code == 200

    payload = response.get_json()
    history = payload["supervision_history"]
    assert len(history) == 1

    rules_in_focus = history[0]["rules_in_focus"]
    assert rules_in_focus["current_step"]["step_id"] == "step-1-1"
    assert rules_in_focus["expected_step"]["step_id"] == "step-1"

    current_rules = rules_in_focus["current_step"]["rules"]
    expected_rules = rules_in_focus["expected_step"]["rules"]

    assert any(rule["text"] == "Keep logs clean" and rule["source"] == "own" for rule in current_rules)
    assert any(rule["text"] == "Use protocol checks" and rule["source"] == "inherited" for rule in current_rules)
    assert any(rule["text"] == "Use protocol checks" and rule["source"] == "own" for rule in expected_rules)


def test_supervise_endpoint_returns_rules_in_focus_snapshot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_visualization_workspace(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "plan.json",
        {
            "plan": {
                "items": [
                    {
                        "id": "step-1",
                        "number": "1",
                        "title": "Main step",
                        "description": "",
                        "rules": [{"category": "workflow", "text": "Follow plan order"}],
                        "children": [],
                    }
                ]
            }
        },
    )
    _write_json(
        tmp_path / ".zoro" / "visualization" / "chat-123" / "runtime.json",
        {
            "supervision_cleaned_accumulated_content": "agent updated files and status",
            "last_supervised_token_index": 0,
        },
    )

    monitoring_module = importlib.import_module("backend.routes.visualization_api.monitoring")

    class FakeSupervisor:
        def supervise(self, chat_id, content_window):
            return {
                "status": "on_track",
                "summary": "Agent is aligned with plan.",
                "current_step": "step-1",
                "expected_step": None,
                "action_required": [],
                "timestamp": "2026-04-20T00:00:00",
            }

    monkeypatch.setattr(monitoring_module, "SupervisorAgent", FakeSupervisor)

    app = create_app()
    client = app.test_client()

    response = client.post("/api/chat-visualizations/chat-123/supervise")
    assert response.status_code == 200
    payload = response.get_json()

    supervision = payload["supervision"]
    assert supervision["current_step"] == "step-1"
    assert supervision["rules_in_focus"]["current_step"]["step_id"] == "step-1"
    assert supervision["rules_in_focus"]["current_step"]["rules"][0]["text"] == "Follow plan order"


def test_rule_verification_pass_increments_rule_usage_count(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json",
        {
            "items": [
                {
                    "item_id": "rule-1",
                    "type": "rule",
                    "category": "workflow",
                    "title": "Follow protocol",
                    "content": "Use protocol checks",
                    "usage_count": 0,
                }
            ],
            "categories": ["workflow"],
        },
    )

    evidence_store = importlib.import_module("backend.visualization.services.evidence_store")
    storage = importlib.import_module("backend.routes.knowledge_api.storage")

    evidence_store.append_rule_verification_evidence(
        "chat-123",
        item_id="step-1",
        rule={
            "kb_item_id": "rule-1",
            "category": "workflow",
            "text": "Use protocol checks",
        },
        verification={
            "explanation": "Verified protocol checks were followed.",
            "code_blocks": [],
            "verdict": "pass",
            "timestamp": "2026-04-20T00:00:00",
        },
        source_title="Step 1",
        is_inherited=False,
    )

    kb = storage.load_knowledge_base()
    assert kb["items"][0]["usage_count"] == 1


def test_rule_verification_non_pass_does_not_increment_rule_usage_count(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / ".zoro" / "rules" / "structured" / "knowledge_base.json",
        {
            "items": [
                {
                    "item_id": "rule-1",
                    "type": "rule",
                    "category": "workflow",
                    "title": "Follow protocol",
                    "content": "Use protocol checks",
                    "usage_count": 0,
                }
            ],
            "categories": ["workflow"],
        },
    )

    evidence_store = importlib.import_module("backend.visualization.services.evidence_store")
    storage = importlib.import_module("backend.routes.knowledge_api.storage")

    evidence_store.append_rule_verification_evidence(
        "chat-123",
        item_id="step-1",
        rule={
            "kb_item_id": "rule-1",
            "category": "workflow",
            "text": "Use protocol checks",
        },
        verification={
            "explanation": "Rule was not met.",
            "code_blocks": [],
            "verdict": "fail",
            "timestamp": "2026-04-20T00:00:00",
        },
        source_title="Step 1",
        is_inherited=False,
    )

    kb = storage.load_knowledge_base()
    assert kb["items"][0]["usage_count"] == 0
