"""Git operations adapter with typed results.

Pure subprocess-based implementation — no GitPython dependency.

Architecture
------------
* ``_parse_*`` module-level helpers — pure functions for parsing git output.
* ``GitCommandRunner`` (from ``infrastructure/git/git_command.py``) — executes
  subprocess commands; injected into ``GitRepo`` for testability.
* ``GitRepo`` — business logic for git operations, delegates to the runner.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from harness.infrastructure.git.git_command import GitCommandRunner
from harness.scm.git_types import (
    DiffResult,
    GitAddError,
    GitCheckoutError,
    GitCommitError,
    GitInitError,
    GitLsFilesError,
    GitOperationError,
    GitRevParseError,
    LogEntry,
    NotAGitRepoError,
    StatusResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GIT_TIMEOUT: int = 30  # seconds


# ---------------------------------------------------------------------------
# Parsing helpers (pure functions, no subprocess calls)
# ---------------------------------------------------------------------------


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
    """Parse ``git log --format=\"%H|%an|%ad|%s\"`` output."""
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

    All subprocess calls use a 30-second timeout and are delegated to
    a ``GitCommandRunner`` (injectable for testing).

    Args:
        root: Absolute path to the git repository root.
        runner: Optional ``GitCommandRunner``. Defaults to a new instance.
    """

    def __init__(self, root: Path, runner: Optional[GitCommandRunner] = None):
        self._root = root.resolve()
        self._runner = runner or GitCommandRunner()

        # Validate that root exists and is inside a git repo.
        if not self._root.is_dir():
            raise NotAGitRepoError(
                path=self._root,
                stderr=f"Directory does not exist: {self._root}",
            )
        try:
            self._runner.run(["rev-parse", "--git-dir"], cwd=self._root)
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

        stdout = self._runner.run(["diff", "--numstat", spec], cwd=self._root)
        files, insertions, deletions = _parse_numstat(stdout)
        return DiffResult(
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
        )

    # -- status --------------------------------------------------------------

    def status(self) -> StatusResult:
        """Return a ``StatusResult`` for the repository."""
        stdout_porcelain = self._runner.run(
            ["status", "--porcelain"], cwd=self._root
        )
        staged, unstaged, untracked = _parse_status_porcelain(stdout_porcelain)

        branch = self.branch()

        ahead, behind = 0, 0
        try:
            ahead_stdout = self._runner.run(
                ["rev-list", "--count", "@{upstream}", "..HEAD"],
                cwd=self._root,
                timeout=_GIT_TIMEOUT,
            )
            ahead = int(ahead_stdout.strip())
        except GitOperationError:
            ahead = 0
        try:
            behind_stdout = self._runner.run(
                ["rev-list", "--count", "HEAD..@{upstream}"],
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
            if re.match(r"^[0-9a-f]{40}$", since):
                args.append(f"{since}..HEAD")
            else:
                # git's --since=<date> treats date-only (YYYY-MM-DD) as
                # exclusive of that day (commits from the next day onward).
                # Appending T00:00:00 makes it inclusive of the whole day.
                _since = since
                if re.match(r"^\d{4}-\d{2}-\d{2}$", _since):
                    _since = f"{_since}T00:00:00"
                args.append(f"--since={_since}")

        stdout = self._runner.run(args, cwd=self._root)
        return _parse_log_entries(stdout)

    # -- branch --------------------------------------------------------------

    def branch(self) -> str:
        """Return the current branch name."""
        stdout = self._runner.run(
            ["branch", "--show-current"], cwd=self._root
        )
        return stdout.strip()

    # -- merge detection -----------------------------------------------------

    def merge_detected(self, watched_branch: str) -> bool:
        """Check if *watched_branch* has commits not in the current branch."""
        try:
            self._runner.run(
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
        stdout = self._runner.run(args, cwd=self._root)
        return _parse_log_entries(stdout)

    def rename_branch(self, old_name: str, new_name: str) -> None:
        """Rename a local git branch.

        Args:
            old_name: Current branch name.
            new_name: Desired new branch name.

        Raises:
            GitOperationError: If the git command fails.
        """
        args = ["branch", "-m", old_name, new_name]
        self._runner.run(args, cwd=self._root)
        return None

    # ── init ----------------------------------------------------------------

    def init(self, path: Path) -> None:
        """Run ``git init <path>``.

        Args:
            path: Directory to initialise.

        Raises:
            GitInitError: If the init command fails.
        """
        try:
            self._runner.run(
                ["init", str(path)],
                cwd=path.parent,
                ensure_cwd=True,
            )
        except GitOperationError as exc:
            raise GitInitError(
                cmd=f"init {path}",
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc

    # ── add / stage ---------------------------------------------------------

    def add(self, paths: Optional[list[str]] = None) -> None:
        """Stage files with ``git add``.

        Args:
            paths: Specific paths to stage, or None for all (``-A``).

        Raises:
            GitAddError: If the add command fails.
        """
        try:
            args = ["add"]
            if paths is not None:
                args.extend(paths)
            else:
                args.append("-A")
            self._runner.run(args, cwd=self._root)
        except GitOperationError as exc:
            raise GitAddError(
                cmd=exc.cmd,
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc

    # ── commit --------------------------------------------------------------

    def commit(self, message: str = "") -> str:
        """Create a commit and return the commit SHA.

        Args:
            message: Commit message. When empty, the commit opens the
                configured git editor (no ``-m`` flag).

        Returns:
            The SHA of the new commit.

        Raises:
            GitCommitError: If the commit fails.
        """
        try:
            args = ["commit"]
            if message:
                args.extend(["-m", message])
            self._runner.run(args, cwd=self._root)
        except GitOperationError as exc:
            raise GitCommitError(
                cmd=exc.cmd,
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc
        return self.head_sha()

    # ── checkout ------------------------------------------------------------

    def checkout(self, branch: str, create: bool = False) -> None:
        """Switch to a branch, optionally creating it.

        Args:
            branch: Branch name.
            create: If True, create the branch first (``git checkout -b``).

        Raises:
            GitCheckoutError: If the checkout fails.
        """
        try:
            args = ["checkout"]
            if create:
                args.extend(["-b", branch])
            else:
                args.append(branch)
            self._runner.run(args, cwd=self._root)
        except GitOperationError as exc:
            raise GitCheckoutError(
                cmd=exc.cmd,
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc

    # ── rev-parse -----------------------------------------------------------

    def rev_parse(self, ref: str) -> str:
        """Resolve a git ref to a full SHA.

        Args:
            ref: Git reference (branch, tag, HEAD, etc.).

        Returns:
            The full SHA of the resolved ref.

        Raises:
            GitRevParseError: If the ref cannot be resolved.
        """
        try:
            stdout = self._runner.run(
                ["rev-parse", ref], cwd=self._root
            )
            return stdout.strip()
        except GitOperationError as exc:
            raise GitRevParseError(
                cmd=exc.cmd,
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc

    def head_sha(self) -> str:
        """Return the full SHA of HEAD.

        Raises:
            GitRevParseError: If HEAD cannot be resolved.
        """
        return self.rev_parse("HEAD")

    # ── ls-files ------------------------------------------------------------

    def ls_files(
        self,
        others: bool = False,
        exclude_standard: bool = True,
    ) -> list[str]:
        """List files tracked by the index (or untracked with ``--others``).

        Args:
            others: If True, list untracked files instead of tracked.
            exclude_standard: If True with ``--others``, apply standard
                exclusions (``.gitignore``, etc.).

        Returns:
            List of file paths relative to repo root.

        Raises:
            GitLsFilesError: If the ls-files command fails.
        """
        try:
            args = ["ls-files"]
            if others:
                args.append("--others")
            if exclude_standard:
                args.append("--exclude-standard")
            stdout = self._runner.run(args, cwd=self._root)
            return [f for f in stdout.splitlines() if f.strip()]
        except GitOperationError as exc:
            raise GitLsFilesError(
                cmd=exc.cmd,
                exit_code=exc.exit_code,
                stderr=exc.stderr,
            ) from exc

    # ── is_git_repo ---------------------------------------------------------

    def is_git_repo(self) -> bool:
        """Check if the working directory is inside a git repository.

        Returns:
            True if ``git rev-parse --git-dir`` succeeds.
        """
        try:
            self._runner.run(["rev-parse", "--git-dir"], cwd=self._root)
            return True
        except GitOperationError:
            return False
