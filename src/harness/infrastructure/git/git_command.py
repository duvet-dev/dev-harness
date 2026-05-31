"""Git command runner — pure subprocess execution, no business logic.

Separates the concern of running ``git`` subprocess commands from the
business logic in ``GitRepo``, making the latter fully testable by
mocking the runner.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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
    ) -> str:
        """Run ``git <args>`` in *cwd* and return stripped stdout.

        Raises:
            GitOperationError: If the git command exits non-zero or times out.
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                timeout=timeout,
            )
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
