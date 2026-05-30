"""Tests for harness.scm.git — Git subprocess adapter."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from harness.scm.git import (
    GitRepo,
    GitOperationError,
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
        # Switch back to main and check
        subprocess.run(
            ["git", "checkout", "main" if repo.branch() == "feature" else "master"],
            cwd=str(git_repo), capture_output=True,
        )


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
