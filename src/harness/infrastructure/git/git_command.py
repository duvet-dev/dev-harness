"""Git command runner — pure subprocess execution, no business logic.

Separates the concern of running ``git`` subprocess commands from the
business logic in ``GitRepo``, making the latter fully testable by
mocking the runner.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from harness.scm.git_types import GitOperationError

_GIT_TIMEOUT: int = 30  # seconds


class GitCommandRunner:
    """Executes git subprocess commands against a working directory.

    This class has zero business logic — it only builds and runs
    subprocess commands, raising ``GitOperationError`` on failure.
    """

    def run(
        self,
        args: list[str],
        cwd: Path,
        timeout: int = _GIT_TIMEOUT,
        env: dict[str, str] | None = None,
        ensure_cwd: bool = False,
    ) -> str:
        """Run ``git <args>`` in *cwd* and return stripped stdout.

        Args:
            args: Git subcommand arguments (without leading "git").
            cwd: Working directory for the command.
            timeout: Maximum time in seconds.
            env: Optional environment variables to pass to the subprocess.
            ensure_cwd: If True, create *cwd* (and parents) before running.

        Raises:
            GitOperationError: If the git command exits non-zero or times out.
        """
        cmd = ["git"] + args
        run_kwargs: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "cwd": str(cwd),
            "timeout": timeout,
        }
        if env is not None:
            run_kwargs["env"] = env

        if ensure_cwd:
            cwd.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(cmd, **run_kwargs)
        except subprocess.TimeoutExpired:
            raise GitOperationError(
                cmd=" ".join(cmd),
                exit_code=-1,
                stderr=f"Command timed out after {timeout}s",
            )
        if result.returncode != 0:
            raise GitOperationError(
                cmd=" ".join(cmd),
                exit_code=result.returncode,
                stderr=result.stderr,
            )
        return result.stdout


__all__ = [
    "GitCommandRunner",
]
