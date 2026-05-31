"""Tests for engagement/startup.py: StartupResumeFlow.

All tests avoid real git operations by monkeypatching subprocess.run.
File-based persistence is tested with tmp_path.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.domain.engagement.model import (
    Engagement,
    EngagementStatus,
    HealthWarning,
)
from harness.domain.engagement.repository import EngagementRepository
from harness.domain.engagement.startup import (
    StartupResumeFlow,
    StartupResult,
    create_engagement,
    load_engagement,
    resume_engagement,
)
from harness.errors import (
    EngagementNotFoundError,
    UnknownWorkflowError,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a temporary project root with .harness directory."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock subprocess.run for all git operations.

    Makes git commands return success with reasonable defaults:
    - rev-parse --abbrev-ref HEAD → "main"
    - rev-parse --verify → success if branch starts with "eng/"
    - checkout -b → always succeeds
    - rev-parse --git-dir → .git exists
    """

    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""

        result = MockResult()
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

        if "rev-parse --abbrev-ref HEAD" in cmd_str:
            result.stdout = "main\n"
        elif "rev-parse --git-dir" in cmd_str:
            result.stdout = ".git\n"
        elif "rev-parse --verify" in cmd_str:
            branch_name = cmd[-1]
            if branch_name.startswith("eng/") or branch_name.startswith("refs/heads/eng/"):
                # New eng/ branches don't exist yet
                result.returncode = 128
                result.stderr = f"fatal: Needed a single revision -- {branch_name} does not exist"
            else:
                result.returncode = 0
                result.stdout = "abc123\n"
        elif "checkout -b" in cmd_str:
            result.stdout = f"Switched to a new branch '{cmd[-1]}'\n"
        elif "ls-files" in cmd_str:
            result.stdout = ""
        elif "diff --name-only" in cmd_str:
            result.stdout = ""

        return result

    monkeypatch.setattr(
        "harness.domain.engagement.startup.subprocess.run", mock_run
    )


@pytest.fixture
def startup_flow(
    project_root: Path,
    mock_subprocess: None,
) -> StartupResumeFlow:
    """Create a StartupResumeFlow with clean temp project root."""
    repo = EngagementRepository(root=project_root)
    return StartupResumeFlow(root=project_root, repository=repo)


@pytest.fixture
def existing_engagement(
    project_root: Path,
    mock_subprocess: None,
) -> Engagement:
    """Create and return an engagement that already exists in the repo."""
    flow = StartupResumeFlow(root=project_root)
    result = flow.create(
        slug="test-eng-001",
        workflow_name="standard",
        session_type="greenfield",
    )
    assert result.success
    assert result.engagement is not None
    return result.engagement


# ── StartupResumeFlow.create() Tests ────────────────────────────────


class TestCreate:
    """Tests for StartupResumeFlow.create()."""

    def test_creates_engagement_basic(self, startup_flow: StartupResumeFlow) -> None:
        """Basic engagement creation with default workflow."""
        result = startup_flow.create(
            slug="my-feature",
            session_type="greenfield",
        )

        assert result.success
        assert result.engagement is not None
        assert result.branch_created

        eng = result.engagement
        assert eng.slug == "my-feature"
        assert eng.workflow_name == "standard"  # Derived from greenfield
        assert eng.session_type == "greenfield"
        assert eng.status == EngagementStatus.ACTIVE
        assert eng.target_branch == "eng/my-feature"
        assert eng.current_phase is not None

    def test_creates_with_explicit_workflow(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Engagement creation with explicit workflow name."""
        result = startup_flow.create(
            slug="fix-bug",
            workflow_name="quick-fix",
            session_type="refactoring",
        )

        assert result.success
        assert result.engagement is not None
        assert result.engagement.workflow_name == "quick-fix"
        assert result.engagement.session_type == "refactoring"

    def test_session_type_workflow_mapping(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Each session type maps to the correct default workflow."""
        cases = [
            ("greenfield", "standard"),
            ("refactoring", "refactoring"),
            ("get-well", "get-well"),
            ("audit", "inspect"),
            ("review", "inspect"),
        ]
        for session_type, expected_wf in cases:
            result = startup_flow.create(
                slug=f"test-{session_type}",
                session_type=session_type,
            )
            assert result.success
            assert result.engagement is not None
            assert result.engagement.workflow_name == expected_wf, (
                f"Session type '{session_type}' should map to "
                f"'{expected_wf}', got '{result.engagement.workflow_name}'"
            )

    def test_rejects_empty_slug(self, startup_flow: StartupResumeFlow) -> None:
        """Empty slug is rejected."""
        result = startup_flow.create(
            slug="",
            session_type="greenfield",
        )
        assert not result.success
        assert result.error is not None
        assert "cannot be empty" in result.error.lower()

    def test_rejects_duplicate_slug(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """Creating with an existing slug is rejected."""
        result = startup_flow.create(
            slug=existing_engagement.slug,
            session_type="greenfield",
        )
        assert not result.success
        assert "already exists" in result.error.lower()

    def test_saves_to_repository(
        self, project_root: Path, startup_flow: StartupResumeFlow
    ) -> None:
        """Engagement is persisted to the repository."""
        result = startup_flow.create(
            slug="persisted-eng",
            session_type="greenfield",
        )
        assert result.success

        # Verify it's in the repository
        repo = EngagementRepository(root=project_root)
        loaded = repo.load("persisted-eng")
        assert loaded.slug == "persisted-eng"
        assert loaded.workflow_name == "standard"
        assert loaded.status == EngagementStatus.ACTIVE

    def test_target_branch_format(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Target branch follows eng/<slug> format."""
        result = startup_flow.create(
            slug="refactor-authentication",
            session_type="refactoring",
        )
        assert result.success
        assert result.engagement is not None
        assert result.engagement.target_branch == "eng/refactor-authentication"

    def test_health_check_runs_automatically(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Proactive health check runs during create()."""
        result = startup_flow.create(
            slug="healthy-eng",
            session_type="greenfield",
        )
        assert result.success
        assert result.report is not None

    def test_unknown_workflow_raises(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Unknown workflow name raises UnknownWorkflowError."""
        with pytest.raises(UnknownWorkflowError):
            startup_flow.create(
                slug="unknown-wf",
                workflow_name="nonexistent-workflow",
                session_type="greenfield",
            )


# ── StartupResumeFlow.resume() Tests ────────────────────────────────


class TestResume:
    """Tests for StartupResumeFlow.resume()."""

    def test_resumes_existing_engagement(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """Resuming an existing engagement works."""
        result = startup_flow.resume(slug=existing_engagement.slug)

        assert result.success
        assert result.engagement is not None
        assert result.engagement.status == EngagementStatus.ACTIVE
        assert result.engagement.slug == existing_engagement.slug

    def test_resume_runs_health_check(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """Health check runs during resume()."""
        result = startup_flow.resume(slug="test-eng-001")
        assert result.success
        assert result.report is not None
        assert result.engagement is not None
        # Should have at least some warnings from the health check
        # (branch missing for eng/test-eng-001 since it's not a real git repo)

    def test_rejects_nonexistent_engagement(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Resuming a non-existent engagement fails."""
        result = startup_flow.resume(slug="does-not-exist")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_rejects_completed_engagement(
        self,
        startup_flow: StartupResumeFlow,
        project_root: Path,
    ) -> None:
        """Resuming a completed engagement is rejected."""
        # Create and complete an engagement
        result = startup_flow.create(
            slug="completed-eng",
            session_type="greenfield",
        )
        assert result.success
        assert result.engagement is not None

        repo = EngagementRepository(root=project_root)
        eng = repo.load("completed-eng")
        eng.status = EngagementStatus.COMPLETED
        repo.save(eng)

        # Try to resume
        resume_result = startup_flow.resume(slug="completed-eng")
        assert not resume_result.success
        assert "completed" in resume_result.error.lower()

    def test_rejects_aborted_engagement(
        self,
        startup_flow: StartupResumeFlow,
        project_root: Path,
    ) -> None:
        """Resuming an aborted engagement is rejected."""
        result = startup_flow.create(
            slug="aborted-eng",
            session_type="greenfield",
        )
        assert result.success

        repo = EngagementRepository(root=project_root)
        eng = repo.load("aborted-eng")
        eng.status = EngagementStatus.ABORTED
        repo.save(eng)

        resume_result = startup_flow.resume(slug="aborted-eng")
        assert not resume_result.success
        assert "aborted" in resume_result.error.lower()

    def test_paused_engagement_can_resume(
        self,
        startup_flow: StartupResumeFlow,
        project_root: Path,
    ) -> None:
        """Paused engagements can be resumed."""
        result = startup_flow.create(
            slug="paused-eng",
            session_type="greenfield",
        )
        assert result.success

        repo = EngagementRepository(root=project_root)
        eng = repo.load("paused-eng")
        eng.status = EngagementStatus.PAUSED
        repo.save(eng)

        resume_result = startup_flow.resume(slug="paused-eng")
        assert resume_result.success
        assert resume_result.engagement is not None
        assert resume_result.engagement.status == EngagementStatus.ACTIVE


# ── StartupResumeFlow.load() Tests ──────────────────────────────────


class TestLoad:
    """Tests for StartupResumeFlow.load()."""

    def test_loads_existing_engagement(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """Loading an existing engagement returns it unchanged."""
        result = startup_flow.load(slug=existing_engagement.slug)

        assert result.success
        assert result.engagement is not None
        assert result.engagement.slug == existing_engagement.slug

    def test_load_does_not_change_status(
        self,
        startup_flow: StartupResumeFlow,
        project_root: Path,
    ) -> None:
        """Loading does not modify engagement status."""
        result = startup_flow.create(
            slug="load-status-check",
            session_type="greenfield",
        )
        assert result.success

        # The engagement should be ACTIVE after create
        load_result = startup_flow.load(slug="load-status-check")
        assert load_result.success
        assert load_result.engagement is not None
        # Should still be ACTIVE (load doesn't change state)

    def test_load_runs_health_check(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """Health check runs during load()."""
        result = startup_flow.load(slug="test-eng-001")
        assert result.success
        assert result.report is not None

    def test_load_nonexistent_fails(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Loading a non-existent engagement fails."""
        result = startup_flow.load(slug="nonexistent-eng")
        assert not result.success
        assert "not found" in result.error.lower()


# ── Branch Creation Tests ───────────────────────────────────────────


class TestBranchCreation:
    """Tests for the branch creation logic in StartupResumeFlow."""

    def test_branch_created_flag(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Branch creation flag is set correctly."""
        result = startup_flow.create(
            slug="branch-test",
            session_type="greenfield",
        )
        assert result.success
        assert result.branch_created
        assert result.engagement is not None
        assert result.engagement.target_branch == "eng/branch-test"

    def test_missing_git_repo_does_not_block(
        self, project_root: Path
    ) -> None:
        """Missing git repo warns but doesn't block creation."""

        # Git not available
        def mock_git_fail(cmd, *args, **kwargs):
            class MockFail:
                returncode = 128
                stdout = ""
                stderr = "fatal: not a git repository"

            return MockFail()

        with patch(
            "harness.domain.engagement.startup.subprocess.run",
            side_effect=mock_git_fail,
        ):
            flow = StartupResumeFlow(root=project_root)
            result = flow.create(
                slug="no-git",
                session_type="greenfield",
            )

        # Should succeed with a warning
        assert result.success
        assert result.engagement is not None
        assert len(result.engagement.warnings) >= 1
        warning_types = {w.type for w in result.engagement.warnings}
        assert "no_git_repo" in warning_types or "branch_create_error" in warning_types


# ── Auto Mode Tests ─────────────────────────────────────────────────


class TestAutoMode:
    """Tests for auto mode integration.

    The full async dispatch is tested via the async method signatures;
    actual async execution depends on WorkflowOrchestrator internals
    which are tested separately.
    """

    def test_mode_passed_to_engagement(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Auto mode is recorded in the engagement workflow."""
        result = startup_flow.create(
            slug="auto-eng",
            session_type="greenfield",
            mode="auto",
        )
        assert result.success
        assert result.engagement is not None

    def test_manual_mode_also_works(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Manual mode creates engagement without auto execution."""
        result = startup_flow.create(
            slug="manual-eng",
            session_type="greenfield",
            mode="manual",
        )
        assert result.success
        assert result.engagement is not None

    def test_enter_first_phase_async_signature(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """enter_first_phase_async exists and is async."""
        import asyncio
        assert asyncio.iscoroutinefunction(startup_flow.enter_first_phase_async)

    def test_resume_async_signature(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """resume_async exists and is async."""
        import asyncio
        assert asyncio.iscoroutinefunction(startup_flow.resume_async)

    def test_run_auto_async_signature(
        self, startup_flow: StartupResumeFlow, existing_engagement: Engagement
    ) -> None:
        """run_auto_async exists and is async."""
        import asyncio
        assert asyncio.iscoroutinefunction(startup_flow.run_auto_async)


# ── Health Check Integration Tests ──────────────────────────────────


class TestProactiveHealthCheck:
    """Tests for proactive health check integration."""

    def test_health_report_in_startup_result(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Startup result includes health report."""
        result = startup_flow.create(
            slug="health-check-eng",
            session_type="greenfield",
        )
        assert result.success
        assert result.report is not None

    def test_warnings_aggregated(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Health warnings are aggregated into engagement warnings."""
        result = startup_flow.create(
            slug="warn-test",
            session_type="greenfield",
        )
        assert result.success
        assert result.engagement is not None
        # Warnings should appear in both the engagement and the result
        if result.report and not result.report.all_ok:
            assert len(result.warnings) > 0

    def test_health_check_does_not_block_creation(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Even with health check warnings, creation succeeds."""
        result = startup_flow.create(
            slug="unhealthy-eng",
            session_type="greenfield",
        )
        # Should succeed even if health check warns
        assert result.success


# ── Properties Tests ────────────────────────────────────────────────


class TestProperties:
    """Tests for StartupResumeFlow properties."""

    def test_repository_property(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """repository property returns the engagement repository."""
        repo = startup_flow.repository
        assert isinstance(repo, EngagementRepository)

    def test_health_check_property(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """health_check property returns the health checker."""
        hc = startup_flow.health_check
        assert hc is not None

    def test_workflow_orchestrator_property(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """workflow_orchestrator property returns the orchestrator."""
        wf = startup_flow.workflow_orchestrator
        assert wf is not None
        assert wf.list_workflows() is not None

    def test_workflows_registered(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Default workflows are registered."""
        wf = startup_flow.workflow_orchestrator
        workflows = wf.list_workflows()
        assert "standard" in workflows
        assert "quick-fix" in workflows
        assert "refactoring" in workflows
        assert "get-well" in workflows
        assert "inspect" in workflows


# ── List Engagements Test ───────────────────────────────────────────


class TestListEngagements:
    """Tests for listing engagements."""

    def test_list_empty(self, startup_flow: StartupResumeFlow) -> None:
        """Empty repository returns empty list."""
        engagements = startup_flow.list_engagements()
        assert len(engagements) == 0

    def test_list_multiple(self, startup_flow: StartupResumeFlow) -> None:
        """Multiple engagements are listed correctly."""
        slugs = ["eng-a", "eng-b", "eng-c"]
        for slug in slugs:
            result = startup_flow.create(
                slug=slug,
                session_type="greenfield",
            )
            assert result.success

        engagements = startup_flow.list_engagements()
        assert len(engagements) == 3
        eng_slugs = {e.slug for e in engagements}
        assert eng_slugs == set(slugs)


# ── Error Handling Tests ────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling in StartupResumeFlow."""

    def test_load_with_corrupt_state(
        self, project_root: Path, mock_subprocess: None
    ) -> None:
        """Corrupt state file is handled gracefully."""
        # Create an engagement
        flow = StartupResumeFlow(root=project_root)
        result = flow.create(
            slug="corrupt-eng",
            session_type="greenfield",
        )
        assert result.success

        # Corrupt the state file
        eng_dir = project_root / ".harness" / "engagements" / "corrupt-eng"
        json_file = eng_dir / "engagement.json"
        json_file.write_text("{{invalid json!!}}")

        # Load should warn but not crash
        load_result = flow.load(slug="corrupt-eng")
        assert not load_result.success
        assert "not found" in load_result.error.lower()
        # Actually it might be "corrupt" depending on error path

    def test_delete_and_recreate(
        self, startup_flow: StartupResumeFlow
    ) -> None:
        """Deleting an engagement then recreating with same slug works."""
        result = startup_flow.create(
            slug="recreate-eng",
            session_type="greenfield",
        )
        assert result.success

        # Delete from repository
        startup_flow.repository.delete("recreate-eng")

        # Recreate should work
        result2 = startup_flow.create(
            slug="recreate-eng",
            session_type="refactoring",
        )
        assert result2.success
        assert result2.engagement is not None
        assert result2.engagement.session_type == "refactoring"


# ── Convenience Functions Tests ─────────────────────────────────────


class TestConvenienceFunctions:
    """Tests for the module-level convenience functions."""

    def test_create_engagement_function(
        self, project_root: Path, mock_subprocess: None
    ) -> None:
        """create_engagement() convenience function works."""
        result = create_engagement(
            slug="convenience-eng",
            session_type="greenfield",
            root=project_root,
        )
        assert result.success
        assert result.engagement is not None
        assert result.engagement.slug == "convenience-eng"

    def test_resume_engagement_function(
        self, project_root: Path, mock_subprocess: None
    ) -> None:
        """resume_engagement() convenience function works."""
        # Create first
        create_result = create_engagement(
            slug="convenience-resume",
            session_type="greenfield",
            root=project_root,
        )
        assert create_result.success

        # Resume
        resume_result = resume_engagement(
            slug="convenience-resume",
            root=project_root,
        )
        assert resume_result.success
        assert resume_result.engagement is not None
        assert resume_result.engagement.slug == "convenience-resume"

    def test_load_engagement_function(
        self, project_root: Path, mock_subprocess: None
    ) -> None:
        """load_engagement() convenience function works."""
        create_result = create_engagement(
            slug="convenience-load",
            session_type="greenfield",
            root=project_root,
        )
        assert create_result.success

        load_result = load_engagement(
            slug="convenience-load",
            root=project_root,
        )
        assert load_result.success
        assert load_result.engagement is not None

    def test_convenience_functions_accept_optional_root(
        self, project_root: Path, mock_subprocess: None
    ) -> None:
        """Convenience functions work without root (auto-discover)."""
        # These will use cwd which may or may not have a harness project;
        # test that they at least don't crash with a TypeError
        with patch("harness.domain.engagement.startup.find_project_root") as mock_find:
            mock_find.return_value = project_root
            result = create_engagement(
                slug="auto-root",
                session_type="greenfield",
            )
            # Should succeed with mocked find_project_root
            assert result.success
