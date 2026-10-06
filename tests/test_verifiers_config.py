import json

import pytest

from backend.utils import get_chat_history_source_from_config, get_verifiers_config
from backend.verifiers.schemas import VerifierConfigError


def _write_config(tmp_path, data: dict):
    config_dir = tmp_path / ".zoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps(data), encoding="utf-8")


def test_returns_an_empty_config_when_zoro_config_json_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = get_verifiers_config()
    assert config.verifiers == {}


def test_parses_a_valid_verifiers_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "verifiers": {
                "security-audit": {
                    "kind": "command",
                    "argv": ["node", "verify"],
                    "schema": "zoro.security-audit.verifier-result/v1",
                }
            }
        },
    )

    config = get_verifiers_config()
    assert "security-audit" in config.verifiers
    assert config.verifiers["security-audit"].timeout_seconds == 1800  # default
    assert config.verifiers["security-audit"].require_complete_coverage is True  # default


def test_raises_on_malformed_json_rather_than_returning_an_empty_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".zoro"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(VerifierConfigError):
        get_verifiers_config()


def test_raises_when_verifiers_key_is_not_an_object(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"verifiers": ["not", "an", "object"]})

    with pytest.raises(VerifierConfigError):
        get_verifiers_config()


def test_raises_when_a_verifier_entry_is_missing_a_required_field(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"verifiers": {"security-audit": {"kind": "command"}}})  # missing argv, schema

    with pytest.raises(VerifierConfigError):
        get_verifiers_config()


def test_raises_on_an_invalid_pass_with_risk_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "verifiers": {
                "security-audit": {
                    "kind": "command",
                    "argv": ["node", "verify"],
                    "schema": "zoro.security-audit.verifier-result/v1",
                    "pass_with_risk": "auto_accept",
                }
            }
        },
    )

    with pytest.raises(VerifierConfigError):
        get_verifiers_config()


def test_chat_history_source_now_accepts_claude(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"chat_history_source": "claude"})
    assert get_chat_history_source_from_config() == "claude"


def test_chat_history_source_still_accepts_codex_and_cline_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"chat_history_source": "codex"})
    assert get_chat_history_source_from_config() == "codex"

    _write_config(tmp_path, {"chat_history_source": "cline"})
    assert get_chat_history_source_from_config() == "cline"
