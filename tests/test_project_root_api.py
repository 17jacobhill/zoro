from backend.api import create_app


def test_get_project_root_returns_the_current_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = create_app().test_client()

    response = client.get("/api/project-root")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "path": str(tmp_path)}


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
