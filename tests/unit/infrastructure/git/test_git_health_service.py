"""Tests for ``harness.infrastructure.git.git_health_service``."""

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from harness.domain.health import HealthCheck, HealthReport
from harness.infrastructure.git.git_health_service import GitHealthChecker


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_git_repo():
    repo = MagicMock()
    repo.branch.return_value = "eng/test-engagement"
    return repo


@pytest.fixture
def mock_engagement_store():
    store = MagicMock()
    return store


@pytest.fixture
def mock_freshness_store():
    store = MagicMock()
    fresh = MagicMock()
    fresh.stale = False
    store.load.return_value = fresh
    return store


@pytest.fixture
def checker(mock_git_repo, mock_engagement_store, mock_freshness_store):
    return GitHealthChecker(mock_git_repo, mock_engagement_store, mock_freshness_store)


# ── check_branch_match ──────────────────────────────────────────────────────


class TestCheckBranchMatch:
    """Verify branch match check behavior."""

    def test_no_active_engagement(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = None
        result = checker.check_branch_match(tmp_path)
        assert result.name == "branch-match"
        assert result.status == "pass"

    def test_missing_engagement_yaml(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = {"slug": "test-eng"}
        result = checker.check_branch_match(tmp_path)
        assert result.status == "warn"
        assert "no engagement.yaml" in result.message.lower()

    def test_branch_mismatch(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = {"slug": "test-eng"}
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text("slug: test-eng\nbranch: eng/expected-branch\n")
        result = checker.check_branch_match(tmp_path)
        assert result.status == "warn"
        assert result.severity == "BRANCH"
        assert "eng/expected-branch" in result.message
        assert "eng/test-engagement" in result.message

    def test_branch_match(self, checker, mock_git_repo, mock_engagement_store, tmp_path):
        mock_git_repo.branch.return_value = "eng/test-eng"
        mock_engagement_store.read_active_engagement.return_value = {"slug": "test-eng"}
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text("slug: test-eng\nbranch: eng/test-eng\n")
        result = checker.check_branch_match(tmp_path)
        assert result.status == "pass"

    def test_exception_handling(self, checker, mock_git_repo, tmp_path):
        mock_git_repo.branch.side_effect = RuntimeError("git error")
        result = checker.check_branch_match(tmp_path)
        assert result.status == "warn"
        assert "git error" in result.message


# ── check_git_clean ─────────────────────────────────────────────────────────


class TestCheckGitClean:
    """Verify git clean check behavior."""

    def test_clean_tree(self, checker, mock_git_repo, tmp_path):
        status = MagicMock()
        status.untracked = []
        status.unstaged = []
        mock_git_repo.status.return_value = status
        result = checker.check_git_clean(tmp_path)
        assert result.name == "git-clean"
        assert result.status == "pass"

    def test_dirty_tree(self, checker, mock_git_repo, tmp_path):
        status = MagicMock()
        status.untracked = ["file1.txt"]
        status.unstaged = ["file2.txt"]
        mock_git_repo.status.return_value = status
        result = checker.check_git_clean(tmp_path)
        assert result.status == "warn"
        assert "2" in result.message
        assert "file1.txt" not in result.message  # don't leak filenames

    def test_only_untracked(self, checker, mock_git_repo, tmp_path):
        status = MagicMock()
        status.untracked = ["new.txt"]
        status.unstaged = []
        mock_git_repo.status.return_value = status
        result = checker.check_git_clean(tmp_path)
        assert result.status == "warn"
        assert "1" in result.message

    def test_only_unstaged(self, checker, mock_git_repo, tmp_path):
        status = MagicMock()
        status.untracked = []
        status.unstaged = ["modified.txt"]
        mock_git_repo.status.return_value = status
        result = checker.check_git_clean(tmp_path)
        assert result.status == "warn"
        assert "1" in result.message

    def test_exception_handling(self, checker, mock_git_repo, tmp_path):
        mock_git_repo.status.side_effect = RuntimeError("permission denied")
        result = checker.check_git_clean(tmp_path)
        assert result.status == "warn"
        assert "permission denied" in result.message


# ── fix_branch_match ────────────────────────────────────────────────────────


class TestFixBranchMatch:
    """Verify branch match fix behavior."""

    def test_no_active_engagement(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = None
        messages = checker.fix_branch_match(tmp_path)
        assert any("no active engagement" in m.lower() for m in messages)

    def test_missing_engagement_yaml(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = {"slug": "test-eng"}
        messages = checker.fix_branch_match(tmp_path)
        assert any("no engagement.yaml" in m.lower() for m in messages)

    def test_successful_fix(self, checker, mock_engagement_store, tmp_path):
        mock_engagement_store.read_active_engagement.return_value = {"slug": "test-eng"}
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text("slug: test-eng\nbranch: old-branch\n")
        messages = checker.fix_branch_match(tmp_path)
        assert any("branch updated" in m.lower() for m in messages)
        assert any("old-branch" in m for m in messages)
        assert any("eng/test-engagement" in m for m in messages)

    def test_exception_handling(self, checker, mock_git_repo, tmp_path):
        mock_git_repo.branch.side_effect = RuntimeError("git error")
        messages = checker.fix_branch_match(tmp_path)
        assert any("failed" in m.lower() for m in messages)


# ── fix_git_state ───────────────────────────────────────────────────────────


class TestFixGitState:
    """Verify git state fix behavior."""

    def test_already_fresh(self, checker, mock_freshness_store, tmp_path):
        fresh = MagicMock()
        fresh.stale = False
        mock_freshness_store.load.return_value = fresh
        messages = checker.fix_git_state(tmp_path)
        assert any("already fresh" in m.lower() for m in messages)

    def test_stale_state_refreshed(self, checker, mock_git_repo, mock_freshness_store, tmp_path):
        stale = MagicMock()
        stale.stale = True
        stale.mark_fresh.return_value = stale
        mock_freshness_store.load.return_value = stale
        mock_git_repo.branch.return_value = "eng/test-branch"
        messages = checker.fix_git_state(tmp_path)
        mock_freshness_store.save.assert_called_once()
        assert any("refreshed" in m.lower() for m in messages)

    def test_no_freshness_store(self, tmp_path):
        checker = GitHealthChecker(MagicMock(), MagicMock(), freshness_store=None)
        messages = checker.fix_git_state(tmp_path)
        assert any("no freshness store" in m.lower() for m in messages)

    def test_exception_handling(self, checker, mock_freshness_store, tmp_path):
        mock_freshness_store.load.side_effect = RuntimeError("load error")
        messages = checker.fix_git_state(tmp_path)
        assert any("failed" in m.lower() for m in messages)


# ── _get_head_sha ───────────────────────────────────────────────────────────


class TestGetHeadSha:
    """Verify HEAD SHA retrieval."""

    def test_returns_unknown_on_failure(self, tmp_path):
        # tmp_path is not a git repo, so rev-parse will fail
        sha = GitHealthChecker._get_head_sha(tmp_path)
        assert sha == "unknown"

    def test_returns_unknown_on_exception(self, monkeypatch):
        import subprocess
        original_run = subprocess.run
        def failing_run(*args, **kwargs):
            raise RuntimeError("subprocess error")
        monkeypatch.setattr(subprocess, "run", failing_run)
        sha = GitHealthChecker._get_head_sha(Path("/tmp"))
        assert sha == "unknown"
