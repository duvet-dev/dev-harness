"""Git repository protocol interface for domain operations.

Defines the contract for git repository operations that application
and infrastructure services depend on, allowing implementations to
vary independently of the domain layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from harness.scm.git_types import DiffResult, LogEntry, StatusResult
from harness.scm.git_types import (
    GitAddError,
    GitCheckoutError,
    GitCommitError,
    GitInitError,
    GitLsFilesError,
    GitRevParseError,
)


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

    # ── New methods for encapsulation ────────────────────────────────

    def init(self, path: Path) -> None:
        """Run ``git init <path>``.

        Raises:
            GitInitError: If the init command fails.
        """

    def add(self, paths: list[str] | None = None) -> None:
        """Stage files with ``git add``.

        Args:
            paths: Specific paths to stage, or None for all.

        Raises:
            GitAddError: If the add command fails.
        """

    def commit(self, message: str = "") -> str:
        """Create a commit and return the commit SHA.

        Args:
            message: Commit message. Uses git editor if empty.

        Raises:
            GitCommitError: If the commit fails.
        """

    def checkout(self, branch: str, create: bool = False) -> None:
        """Switch to a branch, optionally creating it.

        Args:
            branch: Branch name.
            create: If True, create the branch first.

        Raises:
            GitCheckoutError: If the checkout fails.
        """

    def rev_parse(self, ref: str) -> str:
        """Resolve a git ref to a SHA.

        Raises:
            GitRevParseError: If the ref cannot be resolved.
        """

    def head_sha(self) -> str:
        """Return the full SHA of HEAD.

        Raises:
            GitRevParseError: If HEAD cannot be resolved.
        """

    def ls_files(
        self,
        others: bool = False,
        exclude_standard: bool = True,
    ) -> list[str]:
        """List tracked (or untracked) files in the index.

        Raises:
            GitLsFilesError: If the ls-files command fails.
        """

    def is_git_repo(self) -> bool:
        """Check if the working directory is inside a git repo."""


__all__ = [
    "GitRepo",
]
