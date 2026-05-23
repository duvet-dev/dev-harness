"""Git operations adapter with typed results.

Pure subprocess-based implementation — no GitPython dependency.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GIT_TIMEOUT: int = 30  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str],
    cwd: Path,
    timeout: int = _GIT_TIMEOUT,
) -> str:
    """Run a git subprocess and return stdout (stripped).

    Raises ``GitOperationError`` on failure.
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


def _parse_numstat(stdout: str) -> tuple[list[str], int, int]:
    """Parse ``git diff --numstat`` output.

    Returns (files_changed, insertions, deletions).
    """
    files: list[str] = []
    insertions = 0
    deletions = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins_str, del_str, filepath = parts[0], parts[1], parts[2]
        if ins_str != "-":
            insertions += int(ins_str) if ins_str.isdigit() else 0
        if del_str != "-":
            deletions += int(del_str) if del_str.isdigit() else 0
        files.append(filepath)
    return files, insertions, deletions


def _parse_status_porcelain(stdout: str) -> tuple[list[str], list[str], list[str]]:
    """Parse ``git status --porcelain`` output.

    Returns (staged, unstaged, untracked).
    CAUTION: Do NOT strip() the whole stdout — leading spaces on
    each line are significant (they encode staged vs unstaged status).
    """
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        if len(line) < 3:
            continue
        xy = line[:2]
        path = line[3:]
        if xy == "??":
            untracked.append(path)
        else:
            index_status = xy[0]
            worktree_status = xy[1]
            if index_status != " " and index_status != "?":
                staged.append(path)
            if worktree_status != " ":
                unstaged.append(path)
    return staged, unstaged, untracked


def _parse_log_entries(stdout: str) -> list[LogEntry]:
    """Parse ``git log --format="%H|%an|%ad|%s"`` output."""
    entries: list[LogEntry] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        entries.append(
            LogEntry(
                commit_hash=parts[0],
                author=parts[1],
                date=parts[2],
                message=parts[3],
            )
        )
    return entries


# ---------------------------------------------------------------------------
# GitRepo
# ---------------------------------------------------------------------------


class GitRepo:
    """Interface to a local git repository.

    All subprocess calls use a 30-second timeout.
    """

    def __init__(self, root: Path):
        self._root = root.resolve()
        # Validate that root exists and is inside a git repo.
        if not self._root.is_dir():
            raise NotAGitRepoError(
                path=self._root,
                stderr=f"Directory does not exist: {self._root}",
            )
        try:
            _run_git(["rev-parse", "--git-dir"], cwd=self._root)
        except GitOperationError as exc:
            raise NotAGitRepoError(path=self._root, stderr=exc.stderr) from exc

    # -- public properties ---------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    # -- diff ----------------------------------------------------------------

    def diff(
        self,
        ref_a: str = "HEAD",
        ref_b: Optional[str] = None,
    ) -> DiffResult:
        """Return a ``DiffResult`` for *ref_a..ref_b* (or working tree).

        When *ref_b* is ``None`` the diff is against the working tree.
        """
        if ref_b is None:
            spec = ref_a
        else:
            spec = f"{ref_a}..{ref_b}"

        stdout = _run_git(["diff", "--numstat", spec], cwd=self._root)
        files, insertions, deletions = _parse_numstat(stdout)
        return DiffResult(
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
        )

    # -- status --------------------------------------------------------------

    def status(self) -> StatusResult:
        """Return a ``StatusResult`` for the repository."""
        stdout_porcelain = _run_git(
            ["status", "--porcelain"], cwd=self._root
        )
        staged, unstaged, untracked = _parse_status_porcelain(stdout_porcelain)

        branch = self.branch()

        ahead, behind = 0, 0
        try:
            ahead_stdout = _run_git(
                ["rev-list", "--count", f"@{'{upstream}'}", "..HEAD"],
                cwd=self._root,
                timeout=_GIT_TIMEOUT,
            )
            ahead = int(ahead_stdout.strip())
        except GitOperationError:
            ahead = 0
        try:
            behind_stdout = _run_git(
                ["rev-list", "--count", "HEAD.." f"@{'{upstream}'}"],
                cwd=self._root,
                timeout=_GIT_TIMEOUT,
            )
            behind = int(behind_stdout.strip())
        except GitOperationError:
            behind = 0

        return StatusResult(
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            branch=branch,
            ahead=ahead,
            behind=behind,
        )

    # -- log -----------------------------------------------------------------

    def log(
        self,
        since: Optional[str] = None,
        max_count: int = 50,
    ) -> list[LogEntry]:
        """Return commit log entries.

        Args:
            since: Optional ref (SHA, branch, or tag) to start from.
                   If a 40-char hex string, uses ``{since}..HEAD`` range.
                   Otherwise treated as git ref (branch, tag, or ISO date
                   for backward compatibility).
            max_count: Maximum number of entries to return.
        """
        args = [
            "log",
            "--oneline",
            f'--format={"%H|%an|%ad|%s"}',
            "--date=short",
            f"--max-count={max_count}",
        ]
        if since is not None:
            # Detect if 'since' is a full SHA: use ref-range notation
            if re.match(r'^[0-9a-f]{40}$', since):
                args.append(f"{since}..HEAD")
            else:
                # git's --since=<date> treats date-only (YYYY-MM-DD) as
                # exclusive of that day (commits from the next day onward).
                # Appending T00:00:00 makes it inclusive of the whole day.
                _since = since
                if re.match(r'^\d{4}-\d{2}-\d{2}$', _since):
                    _since = f"{_since}T00:00:00"
                args.append(f"--since={_since}")

        stdout = _run_git(args, cwd=self._root)
        return _parse_log_entries(stdout)

    # -- branch --------------------------------------------------------------

    def branch(self) -> str:
        """Return the current branch name."""
        stdout = _run_git(
            ["branch", "--show-current"], cwd=self._root
        )
        return stdout.strip()

    # -- merge detection -----------------------------------------------------

    def merge_detected(self, watched_branch: str) -> bool:
        """Check if *watched_branch* has commits not in the current branch."""
        try:
            _run_git(
                ["merge-base", "--is-ancestor", watched_branch, self.branch()],
                cwd=self._root,
            )
            # watched_branch is an ancestor of current → watched has no new commits
            return False
        except GitOperationError:
            # merge-base returns 1 if not ancestor → watched has new commits
            return True

    # -- interface changes ---------------------------------------------------

    def find_interface_changes(
        self,
        interface_path: str,
        since: str,
    ) -> list[LogEntry]:
        """Return log entries that touched a specific file path.

        Args:
            interface_path: Relative path within the repo.
            since: ISO date or ref to limit from.
        """
        args = [
            "log",
            "--oneline",
            f'--format={"%H|%an|%ad|%s"}',
            "--date=short",
            f"--since={since}",
            "--",
            interface_path,
        ]
        stdout = _run_git(args, cwd=self._root)
        return _parse_log_entries(stdout)

    def rename_branch(self, old_name: str, new_name: str) -> None:
        """Rename a local git branch.

        Args:
            old_name: Current branch name.
            new_name: Desired new branch name.

        Raises:
            RuntimeError: If the git command fails (e.g. old_name doesn't
                exist, new_name already exists, or repo is dirty).
        """
        args = ["branch", "-m", old_name, new_name]
        _run_git(args, cwd=self._root)
