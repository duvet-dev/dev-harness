"""Tests for InitProjectTypedHandler and PhaseManagementTypedHandler.

Wave 2: Typed handler implementations.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.command.handlers.project_handlers import InitProjectTypedHandler
from harness.command.handlers.phase_handlers import PhaseManagementTypedHandler
from harness.command.commands.project import InitProjectCommand
from harness.command.commands.phase import ManagePhaseCommand
from harness.command.results.project import InitProjectResult
from harness.command.results.phase import ManagePhaseResult
from harness.command.types import TypedResult


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def init_handler() -> InitProjectTypedHandler:
    return InitProjectTypedHandler()


@pytest.fixture
def phase_handler() -> PhaseManagementTypedHandler:
    return PhaseManagementTypedHandler()


# ═══════════════════════════════════════════════════════════════════════
# InitProjectTypedHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestInitProjectTypedHandler:
    """Tests for InitProjectTypedHandler — project scaffolding."""

    def test_init_project_creates_files(self, init_handler, tmp_project):
        """Happy path: project files created."""
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = InitProjectCommand(
                    root=tmp_project,
                    no_git=False,
                    force=False,
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.project == tmp_project.name
        assert result.git_initted is True

        # Verify files were created
        assert (tmp_project / "constitution.yaml").is_file()
        assert (tmp_project / ".gitignore").is_file()
        assert (tmp_project / ".harness").is_dir()
        assert (tmp_project / "harness-state.yaml").is_file()

    def test_init_with_subdirectory(self, init_handler, tmp_project):
        """Initialises a subdirectory inside the root."""
        subdir = "my-project"
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = InitProjectCommand(
                    root=tmp_project,
                    project_dir=subdir,
                    no_git=False,
                    force=False,
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        sub_path = tmp_project / subdir
        assert sub_path.is_dir()
        assert (sub_path / "constitution.yaml").is_file()

    def test_init_already_initted_fails(self, init_handler, tmp_project):
        """Already initialised without force returns error."""
        (tmp_project / ".harness").mkdir()
        cmd = InitProjectCommand(
            root=tmp_project,
            force=False,
        )
        result = init_handler.handle(cmd)

        assert result.success is False
        assert "already a harness project" in result.error

    def test_init_force_reinits(self, init_handler, tmp_project):
        """Already initted with --force succeeds."""
        (tmp_project / ".harness").mkdir()
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = InitProjectCommand(
                    root=tmp_project,
                    force=True,
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_init_with_template(self, init_handler, tmp_project):
        """Init with template scaffolds template-specific files."""
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = InitProjectCommand(
                    root=tmp_project,
                    template="backend-service",
                    force=False,
                    no_git=False,
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_init_no_git(self, init_handler, tmp_project):
        """Init with --no-git skips git init."""
        cmd = InitProjectCommand(
            root=tmp_project,
            no_git=True,
            force=False,
        )
        result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.git_initted is False

    def test_exception_returns_error(self, init_handler, tmp_project):
        """Unexpected exception returns error."""
        with patch(
            "harness.cli.helpers.write_minimal_constitution",
            side_effect=RuntimeError("boom"),
        ):
            cmd = InitProjectCommand(
                root=tmp_project,
                force=False,
            )
            result = init_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error

    def test_file_as_project_dir(self, init_handler, tmp_project):
        """Using a file path as project_dir returns error."""
        file_path = tmp_project / "afile.txt"
        file_path.write_text("test")
        cmd = InitProjectCommand(
            root=tmp_project,
            project_dir="afile.txt",
            force=False,
        )
        result = init_handler.handle(cmd)

        assert result.success is False
        assert "is a file" in result.error


# ═══════════════════════════════════════════════════════════════════════
# PhaseManagementTypedHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhaseManagementTypedHandler:
    """Tests for PhaseManagementTypedHandler — list, navigate, feedback, etc."""

    def test_list_no_phases(self, phase_handler, tmp_project):
        """List with no recorded phases returns empty list."""
        with patch("harness.domain.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="list",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert "No phases recorded" in result.message or "0 phase" in result.message

    def test_list_with_phases(self, phase_handler, tmp_project):
        """List returns phase names and states."""
        from harness.domain.engagement.phase_state import PhaseState
        mock_phases = {
            "design": MagicMock(state=PhaseState.ACTIVE),
            "requirements": MagicMock(state=PhaseState.COMPLETED),
        }
        with patch("harness.domain.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = mock_phases
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="list",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        phases = result.phases
        assert len(phases) == 2

    def test_navigate(self, phase_handler, tmp_project):
        """Navigate creates checkpoint and transitions phases."""
        # Create a state file with snapshot
        state_path = tmp_project / "harness-state.yaml"
        from harness.state.snapshot import (
            EngagementSnapshot,
            ProjectSnapshot,
            SnapshotWriter,
        )
        eng = EngagementSnapshot(
            id="my-eng", description="T",
            status="active", gate_mode="auto", phase="design",
        )
        SnapshotWriter.write(
            ProjectSnapshot(project_name="test", version="0.1.0",
                            current_engagement="my-eng", engagements=[eng]),
            state_path,
        )

        with patch("harness.domain.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            with patch("harness.domain.engagement.checkpoint.CheckpointManager") as m_ckm:
                m_ckm.return_value.create.return_value = MagicMock(
                    checkpoint_id="ck-001")
                cmd = ManagePhaseCommand(
                    slug="my-eng",
                    action="navigate",
                    target="implementation",
                    root=str(tmp_project),
                )
                result = phase_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.to_phase == "implementation"
        assert result.checkpoint == "ck-001"

    def test_feedback(self, phase_handler, tmp_project):
        """Feedback creates checkpoint and feedback packet."""
        state_path = tmp_project / "harness-state.yaml"
        from harness.state.snapshot import (
            EngagementSnapshot,
            ProjectSnapshot,
            SnapshotWriter,
        )
        eng = EngagementSnapshot(
            id="my-eng", description="T",
            status="active", gate_mode="auto", phase="design",
        )
        SnapshotWriter.write(
            ProjectSnapshot(project_name="test", version="0.1.0",
                            current_engagement="my-eng", engagements=[eng]),
            state_path,
        )

        with patch("harness.domain.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            with patch("harness.domain.engagement.checkpoint.CheckpointManager") as m_ckm:
                m_ckm.return_value.create.return_value = MagicMock(
                    checkpoint_id="ck-002")
                with patch(
                    "harness.domain.engagement.feedback.FeedbackManager"
                ) as m_fbm:
                    m_fbm.return_value.create.return_value = (
                        tmp_project / "feedback.md"
                    )
                    cmd = ManagePhaseCommand(
                        slug="my-eng",
                        action="feedback",
                        target="testing",
                        feedback_reason="Need better coverage",
                        root=str(tmp_project),
                    )
                    result = phase_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.to_phase == "testing"
        assert result.checkpoint == "ck-002"

    def test_resume_with_checkpoint(self, phase_handler, tmp_project):
        """Resume returns most recent checkpoint."""
        mock_ckpt = MagicMock(checkpoint_id="ck-latest", phase_name="design")
        with patch("harness.domain.engagement.checkpoint.CheckpointManager") as m_ckm:
            m_ckm.return_value.most_recent.return_value = mock_ckpt
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="resume",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert result.resumed is True
        assert result.checkpoint == "ck-latest"

    def test_resume_no_checkpoint(self, phase_handler, tmp_project):
        """Resume with no checkpoints returns not resumed."""
        with patch("harness.domain.engagement.checkpoint.CheckpointManager") as m_ckm:
            m_ckm.return_value.most_recent.return_value = None
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="resume",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert result.resumed is False

    def test_status(self, phase_handler, tmp_project):
        """Status returns phase state dictionary."""
        from harness.domain.engagement.phase_state import PhaseState
        mock_phases = {
            "design": MagicMock(
                state=PhaseState.ACTIVE,
                checkpoint_ref="ck-001",
                feedback_target="",
            ),
        }
        with patch("harness.domain.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = mock_phases
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="status",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert len(result.phases) == 1
        assert result.phases[0]["state"] == "active"

    def test_feedback_list(self, phase_handler, tmp_project):
        """Feedback list returns entries."""
        mock_fb = MagicMock(
            status="pending", from_phase="design", to_phase="testing",
            title="Review needed",
        )
        with patch("harness.domain.engagement.feedback.FeedbackManager") as m_fbm:
            m_fbm.return_value.list_feedback.return_value = [mock_fb]
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="feedback_list",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert len(result.phases) == 1

    def test_feedback_list_empty(self, phase_handler, tmp_project):
        """Empty feedback list returns empty array."""
        with patch("harness.domain.engagement.feedback.FeedbackManager") as m_fbm:
            m_fbm.return_value.list_feedback.return_value = []
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="feedback_list",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert len(result.phases) == 0

    def test_no_action(self, phase_handler, tmp_project):
        """No action specified returns error."""
        cmd = ManagePhaseCommand(
            slug="my-eng",
            action="",
            root=str(tmp_project),
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No action" in result.error

    def test_navigate_no_target(self, phase_handler, tmp_project):
        """Navigate without target returns error."""
        cmd = ManagePhaseCommand(
            slug="my-eng",
            action="navigate",
            root=str(tmp_project),
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No target" in result.error

    def test_feedback_no_target(self, phase_handler, tmp_project):
        """Feedback without target returns error."""
        cmd = ManagePhaseCommand(
            slug="my-eng",
            action="feedback",
            root=str(tmp_project),
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No feedback target" in result.error

    def test_exception_returns_error(self, phase_handler, tmp_project):
        """Unexpected exception returns error."""
        with patch(
            "harness.domain.engagement.phase_state.PhaseStateManager",
            side_effect=RuntimeError("boom"),
        ):
            cmd = ManagePhaseCommand(
                slug="my-eng",
                action="list",
                root=str(tmp_project),
            )
            result = phase_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error
