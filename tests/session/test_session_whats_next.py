"""Tests for WhatsNextEngine — query available actions for an engagement.

Covers:
- WhatsNextEngine.query() returns correct state for various statuses
- available_commands() lists valid commands based on state
- Blocked detection (completed, aborted → blocked)
- Stub mode (no dependencies configured)
- Error handling
"""

from __future__ import annotations

import pytest

from harness.session.whats_next import WhatsNextEngine, WhatsNextResult


# ── Stubs ────────────────────────────────────────────────────────────


class _StubEngagement:
    """Minimal Engagement stub."""

    def __init__(
        self,
        slug: str = "test-eng",
        status: str = "active",
        current_phase: str | None = "design",
    ):
        self.slug = slug
        self.status = _StubStatus(status)
        self.current_phase = current_phase


class _StubStatus:
    """Minimal status value object."""

    def __init__(self, value: str):
        self.value = value


class _StubEngagementRepository:
    """Stub EngagementRepository."""

    def __init__(self, engagement=None, raises: type | None = None):
        self._engagement = engagement
        self._raises = raises

    def load(self, slug: str):
        if self._raises:
            raise self._raises(f"Test error: {slug}")
        return self._engagement


class _StubWorkflowState:
    """Minimal workflow state stub."""

    def __init__(
        self,
        current_phase: str | None = "design",
        pending: list[str] | None = None,
        completed: list[str] | None = None,
        status: str = "active",
    ):
        self.current_phase = current_phase
        self.pending_phases = pending or ["test", "review"]
        self.completed_phases = completed or ["discover"]
        self._status = status

    @property
    def status(self):
        class S:
            def __init__(self, v):
                self.value = v
        return S(self._status)


class _StubWorkflowOrchestrator:
    """Stub WorkflowOrchestrator."""

    def __init__(self):
        self._states: dict[str, _StubWorkflowState] = {}

    def get_state(self, slug: str):
        return self._states.get(slug)

    def set_state(self, slug: str, state: _StubWorkflowState):
        self._states[slug] = state


# ── Tests ────────────────────────────────────────────────────────────


class TestWhatsNextEngine:
    """WhatsNextEngine — query engagement state."""

    def test_query_stub_mode(self):
        """No dependencies configured → stub result."""
        engine = WhatsNextEngine()
        result = engine.query("my-eng")

        assert result.success is True
        assert result.slug == "my-eng"
        assert result.status == "stub"
        assert "next" in result.available_commands

    def test_query_active_engagement(self):
        """Active engagement with repository + orchestrator."""
        eng = _StubEngagement(slug="active-eng", status="active")
        repo = _StubEngagementRepository(engagement=eng)
        wf = _StubWorkflowOrchestrator()
        wf.set_state(
            "active-eng",
            _StubWorkflowState(
                current_phase="design",
                pending=["test", "review"],
                completed=["discover"],
            ),
        )
        engine = WhatsNextEngine(
            engagement_repository=repo,
            workflow_orchestrator=wf,
        )

        result = engine.query("active-eng")

        assert result.success is True
        assert result.slug == "active-eng"
        assert result.status == "active"
        assert result.current_phase == "design"
        assert result.pending_phases == ["test", "review"]
        assert result.completed_phases == ["discover"]
        assert not result.blocked

    def test_query_created_engagement(self):
        """Created engagement → available commands include next and abort."""
        eng = _StubEngagement(slug="new-eng", status="created")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("new-eng")

        assert result.success is True
        assert result.status == "created"
        assert "next" in result.available_commands
        assert "abort_engagement" in result.available_commands

    def test_query_paused_engagement(self):
        """Paused engagement → available commands include resume and abort."""
        eng = _StubEngagement(slug="paused-eng", status="paused")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("paused-eng")

        assert result.success is True
        assert result.status == "paused"
        assert "resume_engagement" in result.available_commands
        assert "abort_engagement" in result.available_commands

    def test_query_completed_engagement_is_blocked(self):
        """Completed engagement → blocked, no action commands."""
        eng = _StubEngagement(slug="done-eng", status="completed")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("done-eng")

        assert result.success is True
        assert result.status == "completed"
        assert result.blocked is True
        assert result.block_reason != ""
        # Only base commands available
        assert "query_status" in result.available_commands
        assert "query_whats_next" in result.available_commands

    def test_query_aborted_engagement_is_blocked(self):
        """Aborted engagement → blocked."""
        eng = _StubEngagement(slug="aborted-eng", status="aborted")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("aborted-eng")

        assert result.success is True
        assert result.status == "aborted"
        assert result.blocked is True

    def test_query_engagement_not_found(self):
        """Repository raises → error result."""
        repo = _StubEngagementRepository(raises=Exception)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("missing-eng")

        assert result.success is False
        assert result.error != ""

    def test_available_commands_convenience(self):
        """available_commands() returns just the command list."""
        eng = _StubEngagement(slug="cmd-eng", status="active")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        commands = engine.available_commands("cmd-eng")

        assert isinstance(commands, list)
        assert len(commands) > 0
        assert "next" in commands
        assert "abort_engagement" in commands

    def test_stale_engagement_not_blocked(self):
        """Valid engagement → not blocked."""
        eng = _StubEngagement(slug="ok-eng", status="active")
        repo = _StubEngagementRepository(engagement=eng)
        engine = WhatsNextEngine(engagement_repository=repo)

        result = engine.query("ok-eng")

        assert result.blocked is False


class TestWhatsNextResult:
    """WhatsNextResult dataclass."""

    def test_defaults(self):
        result = WhatsNextResult(success=True, slug="test")
        assert result.slug == "test"
        assert result.status == ""
        assert result.current_phase is None
        assert result.pending_phases == []
        assert result.completed_phases == []
        assert result.available_commands == []
        assert result.blocked is False
        assert result.block_reason == ""

    def test_available_commands_list(self):
        result = WhatsNextResult(
            success=True,
            slug="test",
            status="active",
            available_commands=["next", "abort", "status"],
        )
        assert result.available_commands == ["next", "abort", "status"]
