"""Direct subprocess execution for external verifiers.

The ONE place in ZORO that ever launches an external verifier process.
Always argv-array + shell=False (never a shell string — PRD security
requirement #1), a sanitized/allowlisted environment (never the caller's
full os.environ), a configurable timeout, and bounded/truncated
stdout+stderr capture so a misbehaving tool can't exhaust memory or leak
unrelated environment secrets into persisted evidence.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime

from backend.verifiers.schemas import VerifierExecution

DEFAULT_ENV_ALLOWLIST = ["PATH", "HOME"]
MAX_CAPTURED_BYTES = 64 * 1024


def _truncate(text: str, max_bytes: int = MAX_CAPTURED_BYTES) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore") + "\n...[truncated]"


def run_command_verifier(
    argv: list[str],
    *,
    cwd: str,
    timeout_seconds: int,
    env_allowlist: list[str] | None = None,
) -> VerifierExecution:
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise ValueError("argv must be a non-empty list of strings")

    allowlist = DEFAULT_ENV_ALLOWLIST if env_allowlist is None else env_allowlist
    sanitized_env = {key: os.environ[key] for key in allowlist if key in os.environ}

    started_at = datetime.now(UTC).isoformat()

    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=sanitized_env,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            shell=False,
        )
        return VerifierExecution(
            argv=argv,
            sanitized_environment=sanitized_env,
            working_directory=cwd,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            process_exit_code=completed.returncode,
            bounded_stdout=_truncate(completed.stdout or ""),
            bounded_stderr=_truncate(completed.stderr or ""),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        # subprocess.run already killed the process (and, on timeout, any
        # output captured so far is returned as str since text=True).
        return VerifierExecution(
            argv=argv,
            sanitized_environment=sanitized_env,
            working_directory=cwd,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            process_exit_code=None,
            bounded_stdout=_truncate(exc.stdout or "" if isinstance(exc.stdout, str) else ""),
            bounded_stderr=_truncate(exc.stderr or "" if isinstance(exc.stderr, str) else ""),
            timed_out=True,
        )
    except OSError as exc:
        # The binary/interpreter named in argv[0] doesn't exist, isn't
        # executable, etc. — the process never ran at all, which is a
        # distinct failure mode from a normal nonzero exit.
        return VerifierExecution(
            argv=argv,
            sanitized_environment=sanitized_env,
            working_directory=cwd,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            process_exit_code=None,
            timed_out=False,
            launch_error=str(exc),
        )
