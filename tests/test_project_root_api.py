import json

from backend.api import create_app


def test_get_project_root_returns_the_current_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.get("/api/project-root")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "path": str(tmp_path), "initialized": False}


def test_set_project_root_switches_cwd_for_subsequent_calls(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    other_dir = tmp_path / "other-project"
    other_dir.mkdir()
    client = create_app().test_client()

    response = client.post("/api/project-root", json={"path": str(other_dir)})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "path": str(other_dir)}

    follow_up = client.get("/api/project-root")
    assert follow_up.get_json()["path"] == str(other_dir)


def test_set_project_root_rejects_a_nonexistent_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.post("/api/project-root", json={"path": str(tmp_path / "does-not-exist")})

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_set_project_root_rejects_a_file_not_a_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    a_file = tmp_path / "not-a-dir.txt"
    a_file.write_text("x")
    client = create_app().test_client()

    response = client.post("/api/project-root", json={"path": str(a_file)})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_set_project_root_rejects_a_relative_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.post("/api/project-root", json={"path": "some/relative/path"})

    assert response.status_code == 400
    assert "absolute" in response.get_json()["error"]


def test_set_project_root_requires_a_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.post("/api/project-root", json={})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_set_project_root_expands_a_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    nested = tmp_path / "nested-project"
    nested.mkdir()
    client = create_app().test_client()

    response = client.post("/api/project-root", json={"path": "~/nested-project"})

    assert response.status_code == 200
    assert response.get_json()["path"] == str(nested)


def test_browse_directory_defaults_to_home_when_no_path_given(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Documents").mkdir()
    (tmp_path / "a-file.txt").write_text("x")
    client = create_app().test_client()  # create_app() itself creates .zoro/ (logging setup) under cwd

    response = client.get("/api/browse-directory")

    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["path"] == str(tmp_path)
    assert "Documents" in body["directories"]
    assert "a-file.txt" not in body["directories"]  # files are excluded


def test_browse_directory_lists_only_subdirectories_sorted_case_insensitively(tmp_path):
    for name in ["zebra", "Apple", "banana"]:
        (tmp_path / name).mkdir()
    (tmp_path / "readme.md").write_text("x")
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": str(tmp_path)})

    body = response.get_json()
    assert body["directories"] == ["Apple", "banana", "zebra"]


def test_browse_directory_reports_the_parent_for_navigating_up(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": str(nested)})

    body = response.get_json()
    assert body["parent"] == str(tmp_path)


def test_browse_directory_root_has_no_parent():
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": "/"})

    body = response.get_json()
    assert body["success"] is True
    assert body["parent"] is None


def test_browse_directory_rejects_a_nonexistent_path(tmp_path):
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": str(tmp_path / "nope")})

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_browse_directory_rejects_a_file(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": str(a_file)})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_browse_directory_expands_a_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "sub").mkdir()
    client = create_app().test_client()

    response = client.get("/api/browse-directory", query_string={"path": "~/sub"})

    body = response.get_json()
    assert body["success"] is True
    assert body["path"] == str(tmp_path / "sub")


def test_get_project_root_reports_initialized_false_when_no_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.get("/api/project-root")

    assert response.get_json()["initialized"] is False


def test_get_project_root_reports_initialized_true_when_config_exists(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".zoro").mkdir()
    (tmp_path / ".zoro" / "config.json").write_text("{}")
    client = create_app().test_client()

    response = client.get("/api/project-root")

    assert response.get_json()["initialized"] is True


def test_init_project_creates_config_and_protocol_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.post("/api/init-project", json={"user_name": "Test User"})

    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["path"] == str(tmp_path)

    config_path = tmp_path / ".zoro" / "config.json"
    assert config_path.exists()
    config = json.loads(config_path.read_text())
    assert config["user_name"] == "Test User"
    # Deliberately "claude", not cmd_init's own "codex" default — see
    # init_project()'s docstring in sessions.py for why.
    assert config["chat_history_source"] == "claude"

    assert (tmp_path / "ZORO.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()


def test_init_project_defaults_user_name_when_not_given(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USER", "env-user")
    client = create_app().test_client()

    response = client.post("/api/init-project", json={})

    config = json.loads((tmp_path / ".zoro" / "config.json").read_text())
    assert config["user_name"] == "env-user"


def test_init_project_refuses_to_clobber_an_already_initialized_project(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".zoro").mkdir()
    existing_config = tmp_path / ".zoro" / "config.json"
    existing_config.write_text(json.dumps({"user_name": "Original", "chat_history_source": "codex"}))
    client = create_app().test_client()

    response = client.post("/api/init-project", json={"user_name": "Someone Else"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    # The existing config must be completely untouched.
    assert json.loads(existing_config.read_text())["user_name"] == "Original"
