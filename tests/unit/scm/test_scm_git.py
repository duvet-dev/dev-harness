"""Tests for harness.scm.git — Git subprocess adapter."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from harness.scm.git import (
    GitRepo,
    GitOperationError,
    GitInitError,
    GitAddError,
    GitCommitError,
    GitCheckoutError,
    GitRevParseError,
    GitLsFilesError,
    NotAGitRepoError,
    DiffResult,
    StatusResult,
    LogEntry,
    _parse_numstat,
    _parse_status_porcelain,
    _parse_log_entries,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with an initial commit."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo_dir), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo_dir), capture_output=True,
    )
    # Initial commit so we have a HEAD
    (repo_dir / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(repo_dir), capture_output=True,
    )
    return repo_dir


# ── Parsing helpers ───────────────────────────────────────────────────────


class TestParseNumstat:
    def test_empty_string(self):
        files, ins, dels = _parse_numstat("")
        assert files == []
        assert ins == 0
        assert dels == 0

    def test_single_file(self):
        stdout = "5\t3\tsrc/main.py\n"
        files, ins, dels = _parse_numstat(stdout)
        assert files == ["src/main.py"]
        assert ins == 5
        assert dels == 3

    def test_multiple_files(self):
        stdout = "1\t0\tREADME.md\n10\t7\tsrc/lib.py\n"
        files, ins, dels = _parse_numstat(stdout)
        assert files == ["README.md", "src/lib.py"]
        assert ins == 11
        assert dels == 7

    def test_binary_file(self):
        stdout = "-\t-\timage.png\n"
        files, ins, dels = _parse_numstat(stdout)
        assert files == ["image.png"]
        assert ins == 0
        assert dels == 0

    def test_whitespace_only_lines_skipped(self):
        stdout = "\n\n5\t3\tsrc/main.py\n\n"
        files, ins, dels = _parse_numstat(stdout)
        assert files == ["src/main.py"]
        assert ins == 5
        assert dels == 3

    def test_malformed_line_skipped(self):
        stdout = "incomplete\n5\t3\tsrc/main.py\n"
        files, ins, dels = _parse_numstat(stdout)
        assert files == ["src/main.py"]
        assert ins == 5
        assert dels == 3


class TestParseStatusPorcelain:
    def test_empty(self):
        staged, unstaged, untracked = _parse_status_porcelain("")
        assert staged == []
        assert unstaged == []
        assert untracked == []

    def test_untracked_file(self):
        stdout = "?? new_file.py\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert untracked == ["new_file.py"]

    def test_staged_file(self):
        stdout = "M  modified.py\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert "modified.py" in staged
        assert "modified.py" not in unstaged

    def test_unstaged_modification(self):
        stdout = " M modified.py\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert "modified.py" not in staged
        assert "modified.py" in unstaged

    def test_staged_and_unstaged(self):
        stdout = "MM modified.py\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert "modified.py" in staged
        assert "modified.py" in unstaged

    def test_whitespace_only_lines_skipped(self):
        stdout = "\n\n?? new_file.py\n\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert untracked == ["new_file.py"]

    def test_short_line_skipped(self):
        stdout = "X\n?? new_file.py\n"
        staged, unstaged, untracked = _parse_status_porcelain(stdout)
        assert untracked == ["new_file.py"]


class TestParseLogEntries:
    def test_empty(self):
        entries = _parse_log_entries("")
        assert entries == []

    def test_single_entry(self):
        stdout = "abc123|Test|2024-01-15|Initial commit\n"
        entries = _parse_log_entries(stdout)
        assert len(entries) == 1
        assert entries[0].commit_hash == "abc123"
        assert entries[0].author == "Test"
        assert entries[0].date == "2024-01-15"
        assert entries[0].message == "Initial commit"

    def test_multiple_entries(self):
        stdout = (
            "aaa|Alice|2024-01-15|First\n"
            "bbb|Bob|2024-01-16|Second\n"
        )
        entries = _parse_log_entries(stdout)
        assert len(entries) == 2

    def test_whitespace_only_lines_skipped(self):
        stdout = "\n\nabc123|Test|2024-01-15|Message\n\n"
        entries = _parse_log_entries(stdout)
        assert len(entries) == 1
        assert entries[0].commit_hash == "abc123"

    def test_malformed_line_skipped(self):
        stdout = "too|few\nabc123|Test|2024-01-15|Message\n"
        entries = _parse_log_entries(stdout)
        assert len(entries) == 1
        assert entries[0].commit_hash == "abc123"


# ── GitRepo ────────────────────────────────────────────────────────────────


class TestGitRepoInit:
    def test_creates_from_valid_repo(self, git_repo: Path):
        repo = GitRepo(git_repo)
        assert repo.root == git_repo.resolve()

    def test_raises_on_non_repo(self, tmp_path: Path):
        with pytest.raises(NotAGitRepoError):
            GitRepo(tmp_path)

    def test_raises_on_nonexistent_dir(self, tmp_path: Path):
        with pytest.raises(NotAGitRepoError):
            GitRepo(tmp_path / "nonexistent")


class TestGitRepoBranch:
    def test_main_or_master(self, git_repo: Path):
        repo = GitRepo(git_repo)
        branch = repo.branch()
        assert branch in ("main", "master")

    def test_after_branch_creation(self, git_repo: Path):
        repo = GitRepo(git_repo)
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=str(git_repo), capture_output=True,
        )
        assert repo.branch() == "feature/test"


class TestGitRepoStatus:
    def test_clean_repo(self, git_repo: Path):
        repo = GitRepo(git_repo)
        status = repo.status()
        assert status.staged == []
        assert status.unstaged == []
        assert status.untracked == []

    def test_detects_untracked(self, git_repo: Path):
        (git_repo / "new.txt").write_text("hello")
        repo = GitRepo(git_repo)
        status = repo.status()
        assert "new.txt" in status.untracked

    def test_detects_staged(self, git_repo: Path):
        (git_repo / "new.txt").write_text("hello")
        subprocess.run(
            ["git", "add", "new.txt"], cwd=str(git_repo), capture_output=True,
        )
        repo = GitRepo(git_repo)
        status = repo.status()
        assert "new.txt" in status.staged

    def test_detects_unstaged_modification(self, git_repo: Path):
        (git_repo / "README.md").write_text("# Modified")
        repo = GitRepo(git_repo)
        status = repo.status()
        assert "README.md" in status.unstaged

    def test_returns_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        status = repo.status()
        assert status.branch in ("main", "master")

    def test_returns_bool_fields(self, git_repo: Path):
        repo = GitRepo(git_repo)
        status = repo.status()
        assert isinstance(status.ahead, int)
        assert isinstance(status.behind, int)


class TestGitRepoDiff:
    def test_initial_diff_returns_empty(self, git_repo: Path):
        repo = GitRepo(git_repo)
        diff = repo.diff("HEAD")
        assert diff.files_changed == []
        assert diff.insertions == 0
        assert diff.deletions == 0

    def test_diff_after_modification(self, git_repo: Path):
        (git_repo / "README.md").write_text("# Modified content")
        repo = GitRepo(git_repo)
        diff = repo.diff("HEAD")
        assert "README.md" in diff.files_changed

    def test_diff_between_refs(self, git_repo: Path):
        # Add a commit
        (git_repo / "file2.txt").write_text("content")
        subprocess.run(
            ["git", "add", "-A"], cwd=str(git_repo), capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "second"],
            cwd=str(git_repo), capture_output=True,
        )
        repo = GitRepo(git_repo)
        diff = repo.diff("HEAD~1", "HEAD")
        assert "file2.txt" in diff.files_changed


class TestGitRepoLog:
    def test_returns_entries(self, git_repo: Path):
        repo = GitRepo(git_repo)
        entries = repo.log(max_count=10)
        assert len(entries) >= 1
        assert isinstance(entries[0], LogEntry)
        assert len(entries[0].commit_hash) == 40

    def test_since_ref_filter(self, git_repo: Path):
        repo = GitRepo(git_repo)
        # Make another commit
        (git_repo / "second.txt").write_text("second")
        subprocess.run(
            ["git", "add", "-A"], cwd=str(git_repo), capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "second"],
            cwd=str(git_repo), capture_output=True,
        )
        # Log since the first commit (use SHA)
        first_sha = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=str(git_repo), capture_output=True, text=True,
        ).stdout.strip()
        entries = repo.log(since=first_sha, max_count=10)
        assert len(entries) >= 1

    def test_max_count(self, git_repo: Path):
        repo = GitRepo(git_repo)
        entries = repo.log(max_count=1)
        assert len(entries) <= 1

    def test_log_with_date_since(self, git_repo: Path):
        repo = GitRepo(git_repo)
        entries = repo.log(since="2020-01-01", max_count=10)
        assert len(entries) >= 1


class TestGitRepoMergeDetection:
    def test_no_new_commits(self, git_repo: Path):
        repo = GitRepo(git_repo)
        branch = repo.branch()
        assert not repo.merge_detected(branch)

    def test_new_commits_on_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        original_branch = repo.branch()
        # Create a feature branch with a new commit
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=str(git_repo), capture_output=True,
        )
        (git_repo / "feature.txt").write_text("feature")
        subprocess.run(
            ["git", "add", "-A"], cwd=str(git_repo), capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feature"],
            cwd=str(git_repo), capture_output=True,
        )
        # Switch back to main/master
        subprocess.run(
            ["git", "checkout", original_branch],
            cwd=str(git_repo), capture_output=True,
        )
        # Now merge_detected("feature") should return True
        # because feature has commits not in original_branch
        assert repo.merge_detected("feature") is True
        assert repo.merge_detected(original_branch) is False


class TestGitRepoInterfaceChanges:
    def test_returns_entries_for_touched_file(self, git_repo: Path):
        repo = GitRepo(git_repo)
        entries = repo.find_interface_changes("README.md", "2020-01-01")
        assert len(entries) >= 1


class TestGitRepoRenameBranch:
    def test_renames_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        repo.rename_branch(repo.branch(), "renamed-branch")
        assert repo.branch() == "renamed-branch"

    def test_raises_on_nonexistent_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        with pytest.raises(GitOperationError):
            repo.rename_branch("nonexistent", "new-name")

    def test_rename_branch_returns_none(self, git_repo: Path):
        repo = GitRepo(git_repo)
        result = repo.rename_branch(repo.branch(), "temp-branch")
        assert result is None
        # Clean up
        repo.rename_branch("temp-branch", repo.branch())


# ── GitRepo with mock runner ────────────────────────────────────────────────


class TestGitRepoMockRunner:
    """Tests for GitRepo with a mocked GitCommandRunner."""

    def test_status_with_ahead_behind(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        # Sequence of calls: rev-parse --git-dir, status --porcelain, branch --show-current,
        # rev-list --count upstream..HEAD, rev-list --count HEAD..upstream
        runner.run.side_effect = [
            ".git\n",  # rev-parse --git-dir
            "\n",       # status --porcelain (clean)
            "main\n",   # branch --show-current
            "3\n",      # rev-list --count upstream..HEAD (ahead=3)
            "2\n",      # rev-list --count HEAD..upstream (behind=2)
        ]

        # Create a mock temp dir that looks like a directory
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        repo = GitRepo(repo_dir, runner=runner)
        status = repo.status()
        assert status.ahead == 3
        assert status.behind == 2

    def test_status_with_ahead_success_behind_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",    # rev-parse --git-dir
            "\n",         # status --porcelain
            "main\n",     # branch --show-current
            "5\n",        # ahead succeeds
            GitOperationError(cmd="rev-list", exit_code=128, stderr="no upstream"),  # behind fails
        ]

        repo_dir = tmp_path / "repo2"
        repo_dir.mkdir()

        repo = GitRepo(repo_dir, runner=runner)
        status = repo.status()
        assert status.ahead == 5
        assert status.behind == 0

    def test_diff_with_ref_b(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            "5\t3\tsrc/main.py\n2\t0\tREADME.md\n",
        ]

        repo_dir = tmp_path / "repo3"
        repo_dir.mkdir()

        repo = GitRepo(repo_dir, runner=runner)
        diff = repo.diff("abc123", "def456")
        assert "src/main.py" in diff.files_changed
        assert diff.insertions == 7
        assert diff.deletions == 3

    def test_merge_detected_raises_git_operation_error(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            "main\n",  # branch()
            GitOperationError(cmd="merge-base", exit_code=1, stderr="not ancestor"),
        ]

        repo_dir = tmp_path / "repo4"
        repo_dir.mkdir()

        repo = GitRepo(repo_dir, runner=runner)
        assert repo.merge_detected("feature") is True


# ── Domain protocol test ────────────────────────────────────────────────────


class TestGitRepoProtocol:
    """Verify the GitRepo protocol can be satisfied by the real GitRepo."""

    def test_root_property(self):
        """The GitRepo protocol's root property should be satisfiable."""
        from harness.domain.interfaces.git import GitRepo as GitRepoProtocol
        from pathlib import Path

        class FakeRepo:
            @property
            def root(self) -> Path:
                return Path("/fake")

            def branch(self) -> str:
                return "main"

            def status(self) -> StatusResult:
                return StatusResult()

            def diff(self, ref_a="HEAD", ref_b=None) -> DiffResult:
                return DiffResult()

            def log(self, since=None, max_count=50) -> list[LogEntry]:
                return []

            def merge_detected(self, watched_branch: str) -> bool:
                return False

            def find_interface_changes(self, interface_path: str, since: str) -> list[LogEntry]:
                return []

            def rename_branch(self, old_name: str, new_name: str) -> None:
                return None

        fake = FakeRepo()
        # Verify structural compatibility with the protocol
        repo: GitRepoProtocol = fake
        assert repo.root == Path("/fake")
        assert repo.branch() == "main"
        assert repo.merge_detected("x") is False


# ── Typed Error Class Tests ─────────────────────────────────────────────────


class TestGitTypedErrors:
    """Verify typed error hierarchy."""

    @pytest.mark.parametrize(
        "error_cls",
        [GitInitError, GitAddError, GitCommitError, GitCheckoutError, GitRevParseError, GitLsFilesError],
    )
    def test_is_subclass_of_git_operation_error(self, error_cls):
        assert issubclass(error_cls, GitOperationError)

    def test_git_init_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitInitError(cmd="init /tmp/fake", exit_code=128, stderr="permission denied")
            except GitInitError:
                raise

    def test_git_add_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitAddError(cmd="add -A", exit_code=128, stderr="error")
            except GitAddError:
                raise

    def test_git_commit_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitCommitError(cmd="commit -m x", exit_code=1, stderr="nothing to commit")
            except GitCommitError:
                raise

    def test_git_checkout_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitCheckoutError(cmd="checkout missing", exit_code=1, stderr="not a valid ref")
            except GitCheckoutError:
                raise

    def test_git_rev_parse_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitRevParseError(cmd="rev-parse INVALID", exit_code=128, stderr="unknown revision")
            except GitRevParseError:
                raise

    def test_git_ls_files_error_raises_from_operation(self):
        with pytest.raises(GitOperationError):
            try:
                raise GitLsFilesError(cmd="ls-files --bad", exit_code=128, stderr="unknown option")
            except GitLsFilesError:
                raise


# ── GitRepo.init ────────────────────────────────────────────────────────────


class TestGitRepoInitMethod:
    """Tests for GitRepo.init()."""

    def test_init_creates_git_repo(self, tmp_path: Path):
        target = tmp_path / "new_project"
        repo = GitRepo.__new__(GitRepo)
        repo._runner = None  # Need fresh runner for real init
        from harness.infrastructure.git.git_command import GitCommandRunner
        repo._runner = GitCommandRunner()
        repo._root = target.resolve()  # Set after init

        # init creates the repo, then we construct a real GitRepo to validate
        GitRepo.init(repo, target)
        assert (target / ".git").is_dir()

    def test_init_twice_is_idempotent(self, tmp_path: Path):
        target = tmp_path / "idempotent"
        from harness.infrastructure.git.git_command import GitCommandRunner
        runner = GitCommandRunner()
        # First init
        runner.run(["init", str(target)], cwd=target.parent, ensure_cwd=True)
        # Second init - should not raise
        runner.run(["init", str(target)], cwd=target.parent)
        assert (target / ".git").is_dir()

    def test_init_raises_git_init_error_on_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = GitOperationError(
            cmd="init /invalid/x", exit_code=128, stderr="permission denied"
        )
        repo = GitRepo.__new__(GitRepo)
        repo._runner = runner
        repo._root = tmp_path

        with pytest.raises(GitInitError):
            repo.init(tmp_path / "x")


# ── GitRepo.add ─────────────────────────────────────────────────────────────


class TestGitRepoAdd:
    """Tests for GitRepo.add()."""

    def test_add_all_stages_untracked(self, git_repo: Path):
        (git_repo / "new_file.txt").write_text("new")
        repo = GitRepo(git_repo)
        repo.add()
        status = repo.status()
        assert "new_file.txt" in status.staged

    def test_add_specific_path(self, git_repo: Path):
        (git_repo / "specific.txt").write_text("specific")
        (git_repo / "other.txt").write_text("other")
        repo = GitRepo(git_repo)
        repo.add(["specific.txt"])
        status = repo.status()
        assert "specific.txt" in status.staged
        assert "other.txt" not in status.staged

    def test_add_raises_git_add_error_on_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",  # GitRepo.__init__ succeeds
            GitOperationError(cmd="add", exit_code=128, stderr="error"),
        ]
        repo_dir = tmp_path / "repoadd"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitAddError):
            repo.add()


# ── GitRepo.commit ──────────────────────────────────────────────────────────


class TestGitRepoCommit:
    """Tests for GitRepo.commit()."""

    def test_commit_with_message_returns_sha(self, git_repo: Path):
        (git_repo / "to_commit.txt").write_text("content")
        repo = GitRepo(git_repo)
        repo.add()
        sha = repo.commit("test commit")
        assert len(sha) == 40
        assert sha.isalnum()

    def test_commit_message_appears_in_log(self, git_repo: Path):
        (git_repo / "msg_test.txt").write_text("content")
        repo = GitRepo(git_repo)
        repo.add()
        repo.commit("custom message here")
        entries = repo.log(max_count=10)
        # The latest log entry should have our message
        # (first entry is most recent with oneline format)
        # Actually log returns multiple fields via _parse_log_entries
        messages = [e.message for e in entries]
        assert any("custom message here" in m for m in messages)

    def test_commit_raises_git_commit_error_on_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",  # init
            GitOperationError(cmd="commit", exit_code=1, stderr="nothing to commit"),
        ]
        repo_dir = tmp_path / "repocommit"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitCommitError):
            repo.commit("message")


# ── GitRepo.checkout ────────────────────────────────────────────────────────


class TestGitRepoCheckout:
    """Tests for GitRepo.checkout()."""

    def test_checkout_existing_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        original = repo.branch()
        # Create another branch to switch to
        subprocess.run(
            ["git", "branch", "other"],
            cwd=str(git_repo), capture_output=True,
        )
        repo.checkout("other")
        assert repo.branch() == "other"
        # Restore
        repo.checkout(original)

    def test_checkout_create_new_branch(self, git_repo: Path):
        repo = GitRepo(git_repo)
        repo.checkout("new-feature", create=True)
        assert repo.branch() == "new-feature"

    def test_checkout_with_empty_string_create(self, git_repo: Path):
        repo = GitRepo(git_repo)
        # Creating a branch with an empty name should fail
        with pytest.raises(GitCheckoutError):
            repo.checkout("", create=True)

    def test_checkout_raises_git_checkout_error_on_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            GitOperationError(cmd="checkout missing", exit_code=1, stderr="pathspec did not match"),
        ]
        repo_dir = tmp_path / "repocheckout"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitCheckoutError):
            repo.checkout("nonexistent")


# ── GitRepo.rev_parse ───────────────────────────────────────────────────────


class TestGitRepoRevParse:
    """Tests for GitRepo.rev_parse() and head_sha()."""

    def test_rev_parse_head(self, git_repo: Path):
        repo = GitRepo(git_repo)
        sha = repo.rev_parse("HEAD")
        assert len(sha) == 40
        assert sha.isalnum()

    def test_rev_parse_master(self, git_repo: Path):
        repo = GitRepo(git_repo)
        branch = repo.branch()
        sha = repo.rev_parse(branch)
        assert len(sha) == 40

    def test_rev_parse_raises_on_invalid_ref(self, tmp_path):
        from unittest.mock import MagicMock, Mock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            GitOperationError(cmd="rev-parse INVALID", exit_code=128, stderr="unknown revision"),
        ]
        repo_dir = tmp_path / "reforevparse"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitRevParseError):
            repo.rev_parse("INVALID")

    def test_head_sha_returns_40_char(self, git_repo: Path):
        repo = GitRepo(git_repo)
        sha = repo.head_sha()
        assert len(sha) == 40
        assert sha.isalnum()

    def test_head_sha_raises_on_non_repo(self, tmp_path: Path):
        with pytest.raises(NotAGitRepoError):
            GitRepo(tmp_path / "nonexistent")


# ── GitRepo.ls_files ────────────────────────────────────────────────────────


class TestGitRepoLsFiles:
    """Tests for GitRepo.ls_files()."""

    def test_ls_files_returns_tracked(self, git_repo: Path):
        repo = GitRepo(git_repo)
        files = repo.ls_files()
        assert "README.md" in files

    def test_ls_files_others(self, git_repo: Path):
        (git_repo / "untracked.txt").write_text("untracked")
        repo = GitRepo(git_repo)
        files = repo.ls_files(others=True, exclude_standard=True)
        assert "untracked.txt" in files
        assert "README.md" not in files

    def test_ls_files_others_without_exclude(self, git_repo: Path):
        (git_repo / "untracked2.txt").write_text("untracked")
        repo = GitRepo(git_repo)
        files = repo.ls_files(others=True, exclude_standard=False)
        assert "untracked2.txt" in files

    def test_ls_files_raises_on_failure(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            GitOperationError(cmd="ls-files", exit_code=128, stderr="error"),
        ]
        repo_dir = tmp_path / "repolsfiles"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitLsFilesError):
            repo.ls_files()


# ── GitRepo.is_git_repo ─────────────────────────────────────────────────────


class TestGitRepoIsGitRepo:
    """Tests for GitRepo.is_git_repo()."""

    def test_is_git_repo_true(self, git_repo: Path):
        repo = GitRepo(git_repo)
        assert repo.is_git_repo() is True

    def test_is_git_repo_false_on_non_repo(self, tmp_path: Path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        # We can't construct GitRepo with a non-repo path (it raises),
        # so we test via mock
        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            GitOperationError(cmd="rev-parse --git-dir", exit_code=128, stderr="not a git repo"),
        ]
        repo = GitRepo.__new__(GitRepo)
        repo._runner = runner
        repo._root = tmp_path

        assert repo.is_git_repo() is False

    def test_is_git_repo_true_with_mock(self, tmp_path):
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.return_value = ".git\n"
        repo = GitRepo.__new__(GitRepo)
        repo._runner = runner
        repo._root = tmp_path

        assert repo.is_git_repo() is True


# ── GitRepo new methods with mock runner (failure paths) ────────────────────


class TestGitRepoNewMethodsMockRunner:
    """Additional failure-path tests for new GitRepo methods."""

    def test_add_with_empty_paths_list(self, tmp_path):
        """Adding with an empty list should stage nothing (graceful)."""
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [".git\n", ""]
        repo_dir = tmp_path / "repoemptyadd"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        # Should not raise
        repo.add(paths=[])

    def test_init_with_ensure_cwd(self, tmp_path):
        """init should create parent directories."""
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.return_value = "Initialized empty Git repository\n"
        repo = GitRepo.__new__(GitRepo)
        repo._runner = runner
        repo._root = tmp_path

        target = tmp_path / "sub" / "deep" / "repo"
        repo.init(target)
        runner.run.assert_called_once()

    def test_commit_empty_message_no_m_flag(self, tmp_path):
        """Commit with empty message should run without -m flag."""
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",  # init
            "",          # commit (no -m flag)
            "abc123def456abc123def456abc123def456abc123\n",  # head_sha
        ]
        repo_dir = tmp_path / "repoemptycommit"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        sha = repo.commit("")
        assert sha == "abc123def456abc123def456abc123def456abc123"
        # Verify commit was called without -m flag
        # The commit call is the 2nd call (index 1)
        commit_call = runner.run.call_args_list[1]
        assert "-m" not in commit_call.args[0]

    def test_checkout_special_chars_branch(self, tmp_path):
        """Branch name with special characters."""
        from unittest.mock import MagicMock
        from harness.infrastructure.git.git_command import GitCommandRunner

        runner = MagicMock(spec=GitCommandRunner)
        runner.run.side_effect = [
            ".git\n",
            GitOperationError(cmd="checkout branch/with/slashes", exit_code=128, stderr="invalid"),
        ]
        repo_dir = tmp_path / "repospecial"
        repo_dir.mkdir()
        repo = GitRepo(repo_dir, runner=runner)

        with pytest.raises(GitCheckoutError):
            repo.checkout("branch/with/slashes", create=True)
