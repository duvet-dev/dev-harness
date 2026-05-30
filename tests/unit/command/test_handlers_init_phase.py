"""Tests for InitProjectHandler and PhaseManagementHandler.

Wave E: Init + Phase management handlers.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from harness.command.handlers import (
    InitProjectHandler,
    PhaseManagementHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandResult


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def init_handler() -> InitProjectHandler:
    return InitProjectHandler()


@pytest.fixture
def phase_handler() -> PhaseManagementHandler:
    return PhaseManagementHandler()


# ═══════════════════════════════════════════════════════════════════════
# InitProjectHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestInitProjectHandler:
    """Tests for InitProjectHandler — project scaffolding."""

    def test_inits_empty_dir(self, init_handler, tmp_project):
        """Happy path: initialises an empty directory."""
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = Command(
                    slug="",
                    command_type="init_project",
                    data={"root": str(tmp_project), "no_git": False,
                          "force": False},
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.data["project"] == tmp_project.name
        assert result.data["git_initted"] is True

        # Verify files were created
        assert (tmp_project / "constitution.yaml").is_file()
        assert (tmp_project / ".gitignore").is_file()
        assert (tmp_project / ".harness").is_dir()
        # get_harness_state_path returns root/harness-state.yaml (not in .harness/)
        assert (tmp_project / "harness-state.yaml").is_file()

    def test_init_with_subdirectory(self, init_handler, tmp_project):
        """Initialises a subdirectory inside the root."""
        subdir = "my-project"
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = Command(
                    slug="",
                    command_type="init_project",
                    data={"root": str(tmp_project), "project_dir": subdir,
                          "no_git": False, "force": False},
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        sub_path = tmp_project / subdir
        assert sub_path.is_dir()
        assert (sub_path / "constitution.yaml").is_file()

    def test_init_already_initted_fails(self, init_handler, tmp_project):
        """Already initialised without force returns error."""
        (tmp_project / ".harness").mkdir()
        cmd = Command(
            slug="",
            command_type="init_project",
            data={"root": str(tmp_project), "force": False},
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
                cmd = Command(
                    slug="",
                    command_type="init_project",
                    data={"root": str(tmp_project), "force": True},
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_init_with_template(self, init_handler, tmp_project):
        """Init with template scaffolds template-specific files."""
        with patch("harness.cli.helpers.init_git") as m_init_git:
            m_init_git.return_value = True
            with patch("harness.cli.helpers.initial_commit"):
                cmd = Command(
                    slug="",
                    command_type="init_project",
                    data={"root": str(tmp_project), "template": "backend-service",
                          "force": False, "no_git": False},
                )
                result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"

    def test_init_no_git(self, init_handler, tmp_project):
        """Init with --no-git skips git init."""
        cmd = Command(
            slug="",
            command_type="init_project",
            data={"root": str(tmp_project), "no_git": True, "force": False},
        )
        result = init_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.data["git_initted"] is False

    def test_exception_returns_error(self, init_handler, tmp_project):
        """Unexpected exception returns error."""
        with patch(
            "harness.cli.helpers.write_minimal_constitution",
            side_effect=RuntimeError("boom"),
        ):
            cmd = Command(
                slug="",
                command_type="init_project",
                data={"root": str(tmp_project), "force": False},
            )
            result = init_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error

    def test_file_as_project_dir(self, init_handler, tmp_project):
        """Using a file path as project_dir returns error."""
        file_path = tmp_project / "afile.txt"
        file_path.write_text("test")
        cmd = Command(
            slug="",
            command_type="init_project",
            data={"root": str(tmp_project), "project_dir": "afile.txt",
                  "force": False},
        )
        result = init_handler.handle(cmd)

        assert result.success is False
        assert "is a file" in result.error


# ═══════════════════════════════════════════════════════════════════════
# PhaseManagementHandler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhaseManagementHandler:
    """Tests for PhaseManagementHandler — list, navigate, feedback, etc."""

    def test_list_no_phases(self, phase_handler, tmp_project):
        """List with no recorded phases returns empty list."""
        with patch("harness.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "list", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert "No phases recorded" in result.message or "0 phase" in result.message

    def test_list_with_phases(self, phase_handler, tmp_project):
        """List returns phase names and states."""
        from harness.engagement.phase_state import PhaseState
        mock_phases = {
            "design": MagicMock(state=PhaseState.ACTIVE),
            "requirements": MagicMock(state=PhaseState.COMPLETED),
        }
        with patch("harness.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = mock_phases
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "list", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        phases = result.data.get("phases", [])
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

        with patch("harness.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            with patch("harness.engagement.checkpoint.CheckpointManager") as m_ckm:
                m_ckm.return_value.create.return_value = MagicMock(
                    checkpoint_id="ck-001")
                cmd = Command(
                    slug="my-eng",
                    command_type="manage_phase",
                    data={"action": "navigate", "target": "implementation",
                          "root": str(tmp_project)},
                )
                result = phase_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.data["to_phase"] == "implementation"
        assert "ck-001" in result.data.get("checkpoint", "")

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

        with patch("harness.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = {}
            with patch("harness.engagement.checkpoint.CheckpointManager") as m_ckm:
                m_ckm.return_value.create.return_value = MagicMock(
                    checkpoint_id="ck-002")
                with patch(
                    "harness.engagement.feedback.FeedbackManager"
                ) as m_fbm:
                    m_fbm.return_value.create.return_value = (
                        tmp_project / "feedback.md"
                    )
                    cmd = Command(
                        slug="my-eng",
                        command_type="manage_phase",
                        data={"action": "feedback", "target": "testing",
                              "feedback_reason": "Need better coverage",
                              "root": str(tmp_project)},
                    )
                    result = phase_handler.handle(cmd)

        assert result.success, f"Expected success, got: {result.error}"
        assert result.data["to_phase"] == "testing"
        assert result.data["checkpoint"] == "ck-002"

    def test_resume_with_checkpoint(self, phase_handler, tmp_project):
        """Resume returns most recent checkpoint."""
        mock_ckpt = MagicMock(checkpoint_id="ck-latest", phase_name="design")
        with patch("harness.engagement.checkpoint.CheckpointManager") as m_ckm:
            m_ckm.return_value.most_recent.return_value = mock_ckpt
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "resume", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert result.data["resumed"] is True
        assert result.data["checkpoint"] == "ck-latest"

    def test_resume_no_checkpoint(self, phase_handler, tmp_project):
        """Resume with no checkpoints returns not resumed."""
        with patch("harness.engagement.checkpoint.CheckpointManager") as m_ckm:
            m_ckm.return_value.most_recent.return_value = None
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "resume", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert result.data["resumed"] is False

    def test_status(self, phase_handler, tmp_project):
        """Status returns phase state dictionary."""
        from harness.engagement.phase_state import PhaseState
        mock_phases = {
            "design": MagicMock(
                state=PhaseState.ACTIVE,
                checkpoint_ref="ck-001",
                feedback_target="",
            ),
        }
        with patch("harness.engagement.phase_state.PhaseStateManager") as m_psm:
            m_psm.return_value.list_phases.return_value = mock_phases
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "status", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert "phases" in result.data
        assert result.data["phases"]["design"]["state"] == "active"

    def test_feedback_list(self, phase_handler, tmp_project):
        """Feedback list returns entries."""
        mock_fb = MagicMock(
            status="pending", from_phase="design", to_phase="testing",
            title="Review needed",
        )
        with patch("harness.engagement.feedback.FeedbackManager") as m_fbm:
            m_fbm.return_value.list_feedback.return_value = [mock_fb]
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "feedback_list", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert len(result.data.get("feedback", [])) == 1

    def test_feedback_list_empty(self, phase_handler, tmp_project):
        """Empty feedback list returns empty array."""
        with patch("harness.engagement.feedback.FeedbackManager") as m_fbm:
            m_fbm.return_value.list_feedback.return_value = []
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "feedback_list", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is True
        assert len(result.data.get("feedback", [])) == 0

    def test_no_action(self, phase_handler, tmp_project):
        """No action specified returns error."""
        cmd = Command(
            slug="my-eng",
            command_type="manage_phase",
            data={"root": str(tmp_project)},
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No action" in result.error

    def test_navigate_no_target(self, phase_handler, tmp_project):
        """Navigate without target returns error."""
        cmd = Command(
            slug="my-eng",
            command_type="manage_phase",
            data={"action": "navigate", "root": str(tmp_project)},
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No target" in result.error

    def test_feedback_no_target(self, phase_handler, tmp_project):
        """Feedback without target returns error."""
        cmd = Command(
            slug="my-eng",
            command_type="manage_phase",
            data={"action": "feedback", "root": str(tmp_project)},
        )
        result = phase_handler.handle(cmd)

        assert result.success is False
        assert "No feedback target" in result.error

    def test_exception_returns_error(self, phase_handler, tmp_project):
        """Unexpected exception returns error."""
        with patch(
            "harness.engagement.phase_state.PhaseStateManager",
            side_effect=RuntimeError("boom"),
        ):
            cmd = Command(
                slug="my-eng",
                command_type="manage_phase",
                data={"action": "list", "root": str(tmp_project)},
            )
            result = phase_handler.handle(cmd)

        assert result.success is False
        assert "boom" in result.error


# ═══════════════════════════════════════════════════════════════════════
# Registration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestRegistration:
    """Verify that new handlers are registered correctly."""

    def test_handlers_are_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert registry.get_handler("init_project") is not None
        assert registry.get_handler("manage_phase") is not None
