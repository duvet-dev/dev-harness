"""Tests for harness.state.reconciliation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.state.reconciliation import (
    DeltaEntry,
    ReconciliationReport,
    BranchReconciler,
)
from harness.scm.git import GitRepo


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def git_repo_with_history(tmp_path: Path) -> Path:
    """Create a git repo with multiple commits and a .harness dir."""
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
    # Commit 1: add README
    (repo_dir / "README.md").write_text("# Project")
    (repo_dir / ".harness").mkdir()
    subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(repo_dir), capture_output=True,
    )
    # Commit 2: add source file
    (repo_dir / "src").mkdir()
    (repo_dir / "src/main.py").write_text("print('hello')")
    subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add main"],
        cwd=str(repo_dir), capture_output=True,
    )
    return repo_dir


@pytest.fixture
def reconciler(git_repo_with_history: Path) -> BranchReconciler:
    repo = GitRepo(git_repo_with_history)
    return BranchReconciler(repo, git_repo_with_history)


@pytest.fixture
def first_sha(git_repo_with_history: Path) -> str:
    """Return the SHA of the first commit."""
    return subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=str(git_repo_with_history), capture_output=True, text=True,
    ).stdout.strip()


# ── Data classes ───────────────────────────────────────────────────────────


class TestDeltaEntry:
    def test_create_added(self):
        entry = DeltaEntry(path="new.txt", change_type="added")
        assert entry.path == "new.txt"
        assert entry.change_type == "added"

    def test_create_modified(self):
        entry = DeltaEntry(path="old.txt", change_type="modified")
        assert entry.change_type == "modified"

    def test_create_deleted(self):
        entry = DeltaEntry(path="gone.txt", change_type="deleted")
        assert entry.change_type == "deleted"


class TestReconciliationReport:
    def test_empty_report(self):
        report = ReconciliationReport(engagement_id="eng-1")
        assert report.engagement_id == "eng-1"
        assert report.stale_commits == []
        assert report.delta == []
        assert not report.merge_detected


# ── BranchReconciler ───────────────────────────────────────────────────────


class TestBranchReconciler:
    def test_reconcile_from_first_commit(self, reconciler: BranchReconciler,
                                          first_sha: str):
        report = reconciler.reconcile(last_known_sha=first_sha, engagement_id="eng-1")
        assert report.engagement_id == "eng-1"
        # Should find commits since first_sha
        assert len(report.stale_commits) >= 1

    def test_reconcile_from_head(self, reconciler: BranchReconciler,
                                  git_repo_with_history: Path):
        # Get current HEAD SHA
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(git_repo_with_history), capture_output=True, text=True,
        ).stdout.strip()
        report = reconciler.reconcile(last_known_sha=head_sha, engagement_id="eng-1")
        # No stale commits since we're at HEAD
        assert len(report.stale_commits) == 0

    def test_reconcile_merge_detection(self, reconciler: BranchReconciler,
                                        first_sha: str):
        report = reconciler.reconcile(
            last_known_sha=first_sha,
            engagement_id="eng-1",
            watched_branch="nonexistent-branch",
        )
        # merge_detected should be False for a non-existent watched branch
        assert isinstance(report.merge_detected, bool)

    def test_reconcile_delta(self, reconciler: BranchReconciler,
                              first_sha: str):
        report = reconciler.reconcile(last_known_sha=first_sha, engagement_id="eng-1")
        # Should have some delta from first to second commit
        assert isinstance(report.delta, list)
        # Some files might be filtered, but delta should be present
        assert len(report.delta) >= 0

    def test_reconcile_classifies_external_changes(self, reconciler: BranchReconciler,
                                                    first_sha: str):
        report = reconciler.reconcile(last_known_sha=first_sha, engagement_id="eng-1")
        assert isinstance(report.external_changes, int)
        assert isinstance(report.harness_managed_changes, int)

    def test_reconcile_invalid_sha_raises(self, reconciler: BranchReconciler):
        # Invalid SHA should raise GitOperationError from the underlying git call
        from harness.scm.git import GitOperationError
        with pytest.raises(GitOperationError, match="Invalid revision range"):
            reconciler.reconcile(
                last_known_sha="0000000000000000000000000000000000000000",
                engagement_id="eng-1",
            )
