"""Shared types for git operations — errors and result dataclasses.

This module is intentionally free of subprocess and runner imports
to avoid circular dependencies. Both ``scm/git.py`` and
``infrastructure/git/git_command.py`` import from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class GitOperationError(Exception):
    """Raised when a git subprocess call fails."""

    def __init__(self, cmd: str, exit_code: int, stderr: str):
        self.cmd = cmd
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"git {cmd} failed (exit={exit_code}): {stderr.strip()}")


class NotAGitRepoError(GitOperationError):
    """Raised when the target path is not inside a git repository."""

    def __init__(self, path: Path, stderr: str = ""):
        self.repo_path = path
        super().__init__(
            cmd=f"rev-parse --git-dir in {path}",
            exit_code=128,
            stderr=stderr or f"Not a git repository: {path}",
        )


class GitInitError(GitOperationError):
    """git init failed"""


class GitAddError(GitOperationError):
    """git add failed"""


class GitCommitError(GitOperationError):
    """git commit failed"""


class GitCheckoutError(GitOperationError):
    """git checkout failed"""


class GitRevParseError(GitOperationError):
    """git rev-parse failed"""


class GitLsFilesError(GitOperationError):
    """git ls-files failed"""


# ---------------------------------------------------------------------------
# Typed result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DiffResult:
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class StatusResult:
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    branch: str = ""
    ahead: int = 0
    behind: int = 0


@dataclass
class LogEntry:
    commit_hash: str = ""
    author: str = ""
    date: str = ""
    message: str = ""


__all__ = [
    "DiffResult",
    "GitAddError",
    "GitCheckoutError",
    "GitCommitError",
    "GitInitError",
    "GitLsFilesError",
    "GitOperationError",
    "GitRevParseError",
    "LogEntry",
    "NotAGitRepoError",
    "StatusResult",
]
