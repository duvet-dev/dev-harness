"""Tests for ``harness.infrastructure.engagement.engagement_health_service``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.infrastructure.engagement.engagement_health_service import (
    EngagementHealthChecker,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_yaml_reader():
    reader = MagicMock()
    return reader


@pytest.fixture
def mock_engagement_reader():
    """Returns a callable that returns a default engagement dict."""
    return MagicMock(return_value={"slug": "test-eng"})


@pytest.fixture
def mock_plan_factory():
    """Returns a callable that creates a mock PlanManager."""
    factory = MagicMock()
    pm = MagicMock()
    pm.load.return_value = MagicMock()
    pm.load.return_value.waves = [MagicMock()]
    factory.return_value = pm
    return factory


@pytest.fixture
def mock_git_factory():
    factory = MagicMock()
    repo = MagicMock()
    repo.branch.return_value = "eng/test-eng"
    factory.return_value = repo
    return factory


@pytest.fixture
def mock_freshness_loader():
    fresh = MagicMock()
    fresh.stale = False
    return MagicMock(return_value=fresh)


@pytest.fixture
def checker(mock_engagement_reader, mock_yaml_reader, mock_plan_factory, mock_git_factory, mock_freshness_loader):
    return EngagementHealthChecker(
        mock_engagement_reader,
        mock_yaml_reader,
        mock_plan_factory,
        mock_git_factory,
        mock_freshness_loader,
    )


# ── check_engagement_fresh ─────────────────────────────────────────────────


class TestCheckEngagementFresh:
    """Verify engagement freshness check."""

    def test_no_freshness_record(self, checker, mock_freshness_loader):
        mock_freshness_loader.return_value = None
        result = checker.check_engagement_fresh(Path("/tmp"))
        assert result.name == "engagement-fresh"
        assert result.status == "pass"

    def test_stale(self, checker, mock_freshness_loader):
        fresh = MagicMock()
        fresh.stale = True
        mock_freshness_loader.return_value = fresh
        result = checker.check_engagement_fresh(Path("/tmp"))
        assert result.status == "fail"
        assert result.severity == "CRITICAL"

    def test_fresh(self, checker, mock_freshness_loader):
        fresh = MagicMock()
        fresh.stale = False
        mock_freshness_loader.return_value = fresh
        result = checker.check_engagement_fresh(Path("/tmp"))
        assert result.status == "pass"

    def test_exception_handling(self, checker, mock_freshness_loader):
        mock_freshness_loader.side_effect = RuntimeError("load error")
        result = checker.check_engagement_fresh(Path("/tmp"))
        assert result.status == "warn"


# ── check_plan_consistency ─────────────────────────────────────────────────


class TestCheckPlanConsistency:
    """Verify plan consistency check."""

    def test_no_active_engagement(self, checker, mock_engagement_reader):
        mock_engagement_reader.return_value = None
        result = checker.check_plan_consistency(Path("/tmp"))
        assert result.name == "plan-consistency"
        assert result.status == "pass"

    def test_no_plan_yaml(self, checker, tmp_path):
        result = checker.check_plan_consistency(tmp_path)
        assert result.status == "pass"

    def test_plan_md_missing(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "plan.yaml").write_text("waves:\n  - name: wave1\n")
        mock_yaml_reader.read.return_value = {"waves": [{"name": "wave1"}]}
        result = checker.check_plan_consistency(tmp_path)
        assert result.status == "warn"

    def test_plan_md_empty(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "plan.yaml").write_text("waves:\n  - name: wave1\n")
        (eng_dir / "plan.md").write_text("")
        mock_yaml_reader.read.return_value = {"waves": [{"name": "wave1"}]}
        result = checker.check_plan_consistency(tmp_path)
        assert result.status == "warn"

    def test_both_exist(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "plan.yaml").write_text("waves:\n  - name: wave1\n")
        (eng_dir / "plan.md").write_text("# Plan\n")
        mock_yaml_reader.read.return_value = {"waves": [{"name": "wave1"}]}
        result = checker.check_plan_consistency(tmp_path)
        assert result.status == "pass"

    def test_exception_handling(self, checker, mock_engagement_reader):
        mock_engagement_reader.side_effect = RuntimeError("reader error")
        result = checker.check_plan_consistency(Path("/tmp"))
        assert result.status == "warn"


# ── check_manifest_link ────────────────────────────────────────────────────


class TestCheckManifestLink:
    """Verify manifest link check."""

    def test_no_active_engagement(self, checker, mock_engagement_reader):
        mock_engagement_reader.return_value = None
        result = checker.check_manifest_link(Path("/tmp"))
        assert result.name == "manifest-link"
        assert result.status == "pass"

    def test_no_engagement_yaml(self, checker, tmp_path):
        result = checker.check_manifest_link(tmp_path)
        assert result.status == "pass"

    def test_no_baseline_manifest(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        mock_yaml_reader.read.return_value = {"slug": "test-eng"}
        result = checker.check_manifest_link(tmp_path)
        assert result.status == "pass"
        assert "baseline manifest" in result.message

    def test_manifest_exists(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\nbaseline_manifest: manifest.json\n")
        (eng_dir / "manifest.json").write_text("{}")
        mock_yaml_reader.read.return_value = {"slug": "test-eng", "baseline_manifest": "manifest.json"}
        result = checker.check_manifest_link(tmp_path)
        assert result.status == "pass"

    def test_manifest_missing(self, checker, mock_yaml_reader, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\nbaseline_manifest: manifest.json\n")
        mock_yaml_reader.read.return_value = {"slug": "test-eng", "baseline_manifest": "manifest.json"}
        result = checker.check_manifest_link(tmp_path)
        assert result.status == "warn"

    def test_exception_handling(self, checker, mock_engagement_reader):
        mock_engagement_reader.side_effect = RuntimeError("reader error")
        result = checker.check_manifest_link(Path("/tmp"))
        assert result.status == "warn"


# ── fix_plan_consistency ───────────────────────────────────────────────────


class TestFixPlanConsistency:
    """Verify plan consistency fix."""

    def test_no_active_engagement(self, checker, mock_engagement_reader):
        mock_engagement_reader.return_value = None
        messages = checker.fix_plan_consistency(Path("/tmp"))
        assert any("no active engagement" in m.lower() for m in messages)

    def test_successful_sync(self, checker, mock_engagement_reader, mock_plan_factory):
        mock_engagement_reader.return_value = {"slug": "test-eng"}
        pm = mock_plan_factory.return_value
        pm.load.return_value = MagicMock()
        pm.load.return_value.waves = [MagicMock()]
        messages = checker.fix_plan_consistency(Path("/tmp"))
        assert any("synced" in m.lower() for m in messages)
        pm.sync_to_md.assert_called_once()

    def test_creates_empty_plan_yaml(self, checker, mock_engagement_reader, mock_plan_factory, tmp_path):
        mock_engagement_reader.return_value = {"slug": "test-eng"}
        pm = mock_plan_factory.return_value
        pm.load.return_value = None
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        # The plan_yaml won't exist, so the code should create it
        messages = checker.fix_plan_consistency(tmp_path)
        plan_yaml = eng_dir / "plan.yaml"
        assert plan_yaml.is_file()
        assert plan_yaml.read_text() == "waves: []\n"

    def test_exception_handling(self, checker, mock_engagement_reader):
        mock_engagement_reader.side_effect = RuntimeError("reader error")
        messages = checker.fix_plan_consistency(Path("/tmp"))
        assert any("failed" in m.lower() for m in messages)


# ── fix_missing_dir ────────────────────────────────────────────────────────


class TestFixMissingDir:
    """Verify missing directory fix."""

    def test_no_active_engagement(self, checker, mock_engagement_reader):
        mock_engagement_reader.return_value = None
        messages = checker.fix_missing_dir(Path("/tmp"))
        assert any("no active engagement" in m.lower() for m in messages)

    def test_creates_missing_engagement_dir(self, checker, tmp_path):
        messages = checker.fix_missing_dir(tmp_path)
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        assert eng_dir.is_dir()
        assert any("created engagement directory" in m.lower() for m in messages)

    def test_creates_missing_engagement_yaml(self, checker, tmp_path):
        messages = checker.fix_missing_dir(tmp_path)
        eng_yaml = tmp_path / ".harness" / "engagements" / "test-eng" / "engagement.yaml"
        assert eng_yaml.is_file()
        assert any("created engagement.yaml" in m.lower() for m in messages)

    def test_creates_missing_engagement_md(self, checker, mock_git_factory, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\nbranch: eng/test-eng\n")
        messages = checker.fix_missing_dir(tmp_path)
        eng_md = eng_dir / "engagement.md"
        assert eng_md.is_file()
        assert any("created engagement.md" in m.lower() for m in messages)

    def test_creates_missing_plan_yaml(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        messages = checker.fix_missing_dir(tmp_path)
        plan_yaml = eng_dir / "plan.yaml"
        assert plan_yaml.is_file()
        assert any("empty plan" in m.lower() for m in messages)

    def test_creates_assessments_dir(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        messages = checker.fix_missing_dir(tmp_path)
        assess_dir = eng_dir / "assessments"
        assert assess_dir.is_dir()
        assert any("assessments" in m.lower() for m in messages)

    def test_already_complete(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        assess_dir = eng_dir / "assessments"
        assess_dir.mkdir(parents=True)
        messages = checker.fix_missing_dir(tmp_path)
        assert any("already complete" in m.lower() for m in messages)

    def test_exception_handling(self, checker, mock_engagement_reader):
        mock_engagement_reader.side_effect = RuntimeError("reader error")
        messages = checker.fix_missing_dir(Path("/tmp"))
        assert any("failed" in m.lower() for m in messages)


# ── fix_engagement ─────────────────────────────────────────────────────────


class TestFixEngagement:
    """Verify engagement fix."""

    def test_creates_missing_dir(self, checker, tmp_path):
        messages = checker.fix_engagement(tmp_path, "test-eng")
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        assert eng_dir.is_dir()
        assert any("created engagement directory" in m.lower() for m in messages)

    def test_creates_engagement_yaml(self, checker, tmp_path):
        messages = checker.fix_engagement(tmp_path, "test-eng")
        eng_yaml = tmp_path / ".harness" / "engagements" / "test-eng" / "engagement.yaml"
        assert eng_yaml.is_file()
        assert any("created engagement.yaml" in m.lower() for m in messages)

    def test_engagement_yaml_already_exists(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\nbranch: eng/test-eng\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert any("engagement.yaml exists" in m.lower() for m in messages)

    def test_creates_engagement_md(self, checker, mock_git_factory, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\nbranch: eng/test-branch\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert (eng_dir / "engagement.md").is_file()
        assert any("created engagement.md" in m.lower() for m in messages)

    def test_engagement_md_already_exists(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert any("engagement.md exists" in m.lower() for m in messages)

    def test_creates_plan_yaml(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert (eng_dir / "plan.yaml").is_file()
        assert any("empty plan.yaml" in m.lower() or "plan.yaml exists" in m.lower() for m in messages)

    def test_creates_plan_md_from_yaml(self, checker, mock_plan_factory, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        pm = mock_plan_factory.return_value
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert any("created plan.md" in m.lower() for m in messages)
        pm.sync_to_md.assert_called_once()

    def test_plan_md_already_exists(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        (eng_dir / "plan.md").write_text("# Plan\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert any("plan.md exists" in m.lower() for m in messages)

    def test_creates_assessments_dir(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        (eng_dir / "plan.md").write_text("# Plan\n")
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert (eng_dir / "assessments").is_dir()
        assert any("assessments" in m.lower() for m in messages)

    def test_complete(self, checker, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("slug: test-eng\n")
        (eng_dir / "engagement.md").write_text("# Test\n")
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        (eng_dir / "plan.md").write_text("# Plan\n")
        (eng_dir / "assessments").mkdir(parents=True)
        messages = checker.fix_engagement(tmp_path, "test-eng")
        assert any("fix complete" in m.lower() for m in messages)
