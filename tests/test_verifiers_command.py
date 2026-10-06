import sys

import pytest

from backend.verifiers.command import MAX_CAPTURED_BYTES, run_command_verifier


def test_runs_a_trivial_command_and_captures_output(tmp_path):
    execution = run_command_verifier(
        [sys.executable, "-c", "print('hello')"],
        cwd=str(tmp_path),
        timeout_seconds=10,
    )

    assert execution.process_exit_code == 0
    assert execution.bounded_stdout.strip() == "hello"
    assert execution.timed_out is False
    assert execution.launch_error is None


def test_a_nonzero_exit_is_a_normal_outcome_not_a_launch_error(tmp_path):
    execution = run_command_verifier(
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        cwd=str(tmp_path),
        timeout_seconds=10,
    )

    assert execution.process_exit_code == 3
    assert execution.launch_error is None
    assert execution.timed_out is False


def test_timeout_is_distinct_from_a_normal_exit(tmp_path):
    execution = run_command_verifier(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=str(tmp_path),
        timeout_seconds=1,
    )

    assert execution.timed_out is True
    assert execution.process_exit_code is None


def test_a_missing_binary_is_a_launch_error_not_a_timeout_or_normal_exit(tmp_path):
    execution = run_command_verifier(
        ["this-binary-does-not-exist-xyz-12345"],
        cwd=str(tmp_path),
        timeout_seconds=10,
    )

    assert execution.launch_error is not None
    assert execution.process_exit_code is None
    assert execution.timed_out is False


def test_the_sanitized_environment_never_includes_an_unallowlisted_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("TOTALLY_FAKE_SECRET_FOR_THIS_TEST", "sk-should-never-appear")

    execution = run_command_verifier(
        [sys.executable, "-c", "print('ok')"],
        cwd=str(tmp_path),
        timeout_seconds=10,
    )

    assert "TOTALLY_FAKE_SECRET_FOR_THIS_TEST" not in execution.sanitized_environment
    assert set(execution.sanitized_environment).issubset({"PATH", "HOME"})


def test_custom_env_allowlist_is_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("SOME_ALLOWED_VAR", "value")
    monkeypatch.setenv("SOME_DISALLOWED_VAR", "other")

    execution = run_command_verifier(
        [sys.executable, "-c", "print('ok')"],
        cwd=str(tmp_path),
        timeout_seconds=10,
        env_allowlist=["SOME_ALLOWED_VAR"],
    )

    assert execution.sanitized_environment == {"SOME_ALLOWED_VAR": "value"}


def test_stdout_is_truncated_rather_than_unbounded(tmp_path):
    execution = run_command_verifier(
        [sys.executable, "-c", "print('x' * 200000)"],
        cwd=str(tmp_path),
        timeout_seconds=10,
    )

    assert len(execution.bounded_stdout.encode("utf-8")) <= MAX_CAPTURED_BYTES + len("\n...[truncated]")
    assert execution.bounded_stdout.endswith("...[truncated]")


def test_rejects_a_non_list_or_empty_argv(tmp_path):
    with pytest.raises(ValueError):
        run_command_verifier([], cwd=str(tmp_path), timeout_seconds=10)
