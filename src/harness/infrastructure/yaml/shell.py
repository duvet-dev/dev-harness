"""Shell execution protocol.

Defines a Shell protocol that abstracts subprocess.run calls
for testability. Production uses subprocess directly; test
implementations can record or mock calls.
"""

from __future__ import annotations

import subprocess
from typing import Optional, Protocol


class ShellResult:
    """Result of a shell command execution."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def success(self) -> bool:
        return self.returncode == 0


class Shell(Protocol):
    """Abstract shell command execution.

    Follows the I/O abstraction pattern, allowing shell calls
    to be mocked or recorded in tests.
    """

    def run(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> ShellResult: ...


class RealShell:
    """Production shell that delegates to subprocess.run."""

    def run(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> ShellResult:
        """Execute a shell command via subprocess.

        Args:
            command: Command and arguments as a list.
            cwd: Working directory.
            timeout: Timeout in seconds.
            env: Environment variables override.

        Returns:
            ShellResult with returncode, stdout, stderr.
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
                env={**subprocess.os.environ, **(env or {})},
            )
            return ShellResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ShellResult(returncode=-1, stderr="Timeout expired")
        except FileNotFoundError:
            return ShellResult(returncode=-1, stderr=f"Command not found: {command[0]}")
