"""Git repository protocol interface for domain operations.

Defines the contract for git repository operations that application
and infrastructure services depend on, allowing implementations to
vary independently of the domain layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from harness.scm.git_types import DiffResult, LogEntry, StatusResult


class GitRepo(Protocol):
    """Protocol for git repository operations used by the domain layer.

    All methods operate on a repository whose root is established
    during construction (not passed per-method).
    """

    @property
    def root(self) -> Path:
        """The absolute path to the repository root."""
        ...  # pragma: no cover

    def branch(self) -> str:
        """Return the current branch name."""

    def status(self) -> StatusResult:
        """Return the current repository status."""

    def diff(
        self,
        ref_a: str = "HEAD",
        ref_b: Optional[str] = None,
    ) -> DiffResult:
        """Return a DiffResult for *ref_a..ref_b* (or working tree)."""

    def log(
        self,
        since: Optional[str] = None,
        max_count: int = 50,
    ) -> list[LogEntry]:
        """Return commit log entries."""

    def merge_detected(self, watched_branch: str) -> bool:
        """Check if *watched_branch* has commits not in the current branch."""

    def find_interface_changes(
        self,
        interface_path: str,
        since: str,
    ) -> list[LogEntry]:
        """Return log entries that touched a specific file path."""

    def rename_branch(self, old_name: str, new_name: str) -> None:
        """Rename a local git branch."""


__all__ = [
    "GitRepo",
]
