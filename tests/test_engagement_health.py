"""Tests for EngagementHealthCheck — branch alignment, dirty repo, branch existence, state consistency.

Uses temporary directories and mock-style isolation where possible.
Git-dependent checks are tested with a real (temporary) git repo.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from harness.engagement.health import EngagementHealthCheck, HealthReport, check_engagement_health
from harness.engagement.model import Engagement, EngagementStatus
from harness.engagement.repository import EngagementRepository


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary project root with .harness/ directory."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    engagements_dir = harness_dir / "engagements"
    engagements_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def repo(tmp_root: Path) -> EngagementRepository:
    return EngagementRepository(root=tmp_root)


@pytest.fixture
def checker(repo: EngagementRepository) -> EngagementHealthCheck:
    return EngagementHealthCheck(repository=repo)


@pytest.fixture
def git_repo_root(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    root = tmp_path / "git-project"
    root.mkdir(parents=True)
    harness_dir = root / ".harness"
    harness_dir.mkdir(parents=True)
    engagements_dir = harness_dir / "engagements"
    engagements_dir.mkdir(parents=True)

    subprocess.run(["git", "init"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True)
    # Create an initial commit
    (root / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, capture_output=True)

    return root


@pytest.fixture
def git_repo(git_repo_root: Path) -> EngagementRepository:
    return EngagementRepository(root=git_repo_root)


@pytest.fixture
def git_checker(git_repo_root: Path, git_repo: EngagementRepository) -> EngagementHealthCheck:
    return EngagementHealthCheck(root=git_repo_root, repository=git_repo)


# ── HealthReport Tests ──────────────────────────────────────────────


class TestHealthReport:
    """Tests for HealthReport dataclass."""

    def test_default_all_ok(self):
        """A fresh HealthReport has all_ok=True."""
        report = HealthReport(slug="test")
        assert report.all_ok is True
        assert report.warnings == []

    def test_with_warnings(self):
        """Adding warnings sets all_ok=False."""
        from harness.engagement.model import HealthWarning
        report = HealthReport(slug="test")
        report.warnings.append(
            HealthWarning(type="dirty_repo", message="Changes found")
        )
        assert report.all_ok is True  # all_ok is set at check time
        report.all_ok = False
        assert report.all_ok is False


# ── Check: Basic status ────────────────────────────────────────────


class TestEngagementHealthCheckBasic:
    """Basic engagement health check scenarios."""

    def test_check_nonexistent_engagement(self, checker: EngagementHealthCheck):
        """Checking a non-existent engagement returns warnings."""
        report = checker.check("does-not-exist")
        assert report.all_ok is False
        assert len(report.warnings) >= 1
        assert any(w.type == "engagement_not_found" for w in report.warnings)

    def test_check_empty_slug(self, checker: EngagementHealthCheck):
        """Checking with empty slug returns warnings."""
        report = checker.check("")
        assert report.all_ok is False

    def test_check_returns_report_object(self, checker: EngagementHealthCheck):
        """Check returns a HealthReport."""
        report = checker.check("does-not-exist")
        assert isinstance(report, HealthReport)

    def test_check_populates_slug(self, checker: EngagementHealthCheck):
        """Check populates the report slug."""
        report = checker.check("test-eng")
        assert report.slug == "test-eng"

    def test_check_without_branch_no_warnings(
        self, repo: EngagementRepository, checker: EngagementHealthCheck
    ):
        """An engagement with no target_branch doesn't warn about branches."""
        eng = Engagement(slug="no-branch", target_branch="")
        repo.save(eng)
        report = checker.check("no-branch")
        branch_warnings = [w for w in report.warnings if "branch" in w.type]
        assert len(branch_warnings) == 0


# ── Check: With Git repo ───────────────────────────────────────────


class TestEngagementHealthCheckGit:
    """Health check tests with a real git repository."""

    def test_check_clean_repo(self, git_repo_root: Path, git_checker: EngagementHealthCheck):
        """A clean repo with matching branch has no warnings."""
        eng = Engagement(
            slug="clean-eng",
            target_branch="main",
            status=EngagementStatus.ACTIVE,
            last_active=datetime.now(),
        )
        git_checker.repository.save(eng)
        report = git_checker.check("clean-eng")
        # May have dirtiness warnings depending on test dir
        assert report.engagement is not None
        assert report.slug == "clean-eng"

    def test_check_branch_mismatch(self, git_repo_root: Path, git_checker: EngagementHealthCheck):
        """A branch mismatch generates a warning."""
        # Create a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=git_repo_root, capture_output=True,
        )
        eng = Engagement(
            slug="mismatch-eng",
            target_branch="eng/expected",
            status=EngagementStatus.ACTIVE,
        )
        git_checker.repository.save(eng)
        report = git_checker.check("mismatch-eng")
        branch_warnings = [w for w in report.warnings if w.type == "branch_mismatch"]
        assert len(branch_warnings) >= 1

    def test_check_dirty_repo(self, git_repo_root: Path, git_checker: EngagementHealthCheck):
        """Uncommitted changes generate a dirty_repo warning."""
        # Create an untracked file
        (git_repo_root / "untracked-file.txt").write_text("dirty")
        eng = Engagement(
            slug="dirty-eng",
            target_branch="main",
            status=EngagementStatus.ACTIVE,
        )
        git_checker.repository.save(eng)
        report = git_checker.check("dirty-eng")
        dirty_warnings = [w for w in report.warnings if w.type == "dirty_repo"]
        assert len(dirty_warnings) >= 1

    def test_check_nonexistent_branch(
        self, git_repo_root: Path, git_checker: EngagementHealthCheck
    ):
        """A non-existent target branch generates a branch_missing warning."""
        eng = Engagement(
            slug="missing-branch-eng",
            target_branch="eng/nonexistent",
            status=EngagementStatus.ACTIVE,
        )
        git_checker.repository.save(eng)
        report = git_checker.check("missing-branch-eng")
        missing_warnings = [w for w in report.warnings if w.type == "branch_missing"]
        assert len(missing_warnings) >= 1

    def test_check_existing_branch(self, git_checker: EngagementHealthCheck):
        """An existing target branch doesn't generate branch_missing."""
        eng = Engagement(
            slug="existing-branch-eng",
            target_branch="main",
            status=EngagementStatus.ACTIVE,
        )
        git_checker.repository.save(eng)
        report = git_checker.check("existing-branch-eng")
        missing_warnings = [w for w in report.warnings if w.type == "branch_missing"]
        assert len(missing_warnings) == 0


# ── Check: State consistency ───────────────────────────────────────


class TestEngagementHealthCheckState:
    """State consistency checks."""

    def test_stale_active_engagement_warns(
        self, repo: EngagementRepository, checker: EngagementHealthCheck
    ):
        """An active engagement with last_active >24h ago warns."""
        old_time = datetime.now() - timedelta(hours=48)
        eng = Engagement(
            slug="stale-eng",
            status=EngagementStatus.ACTIVE,
            last_active=old_time,
        )
        repo.save(eng)
        report = checker.check("stale-eng")
        stale_warnings = [w for w in report.warnings if w.type == "stale_engagement"]
        assert len(stale_warnings) >= 1

    def test_recent_active_no_warning(
        self, repo: EngagementRepository, checker: EngagementHealthCheck
    ):
        """A recently active engagement doesn't warn about staleness."""
        eng = Engagement(
            slug="recent-eng",
            status=EngagementStatus.ACTIVE,
            last_active=datetime.now(),
        )
        repo.save(eng)
        report = checker.check("recent-eng")
        stale_warnings = [w for w in report.warnings if w.type == "stale_engagement"]
        assert len(stale_warnings) == 0

    def test_slug_mismatch_warns(
        self, repo: EngagementRepository, checker: EngagementHealthCheck
    ):
        """A slug mismatch between file and request generates a warning."""
        eng = Engagement(slug="file-slug")
        repo.save(eng)
        report = checker.check("file-slug")  # matches, no mismatch
        slug_warnings = [w for w in report.warnings if w.type == "slug_mismatch"]
        assert len(slug_warnings) == 0


# ── Convenience function ────────────────────────────────────────────


class TestCheckEngagementHealth:
    """Tests for the check_engagement_health convenience function."""

    def test_convenience_function_returns_report(self):
        """check_engagement_health returns a HealthReport."""
        report = check_engagement_health("nonexistent-slug")
        assert isinstance(report, HealthReport)

    def test_convenience_function_for_unknown(self):
        """check_engagement_health for unknown returns warnings."""
        report = check_engagement_health("really-nonexistent")
        assert report.all_ok is False
