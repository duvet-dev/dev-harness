"""Tests for AbortHandler — hard abort and graceful stop.

Covers:
- AbortHandler.hard_abort() — immediate stop, no cleanup
- AbortHandler.graceful_stop() — completes current step then stops
- State transitions: engagement status → ABORTED
- Stub mode (no repository configured)
- Error handling for missing engagements
- Previous status tracking
"""

from __future__ import annotations

from datetime import datetime

import pytest

from harness.session.abort import AbortHandler, AbortResult
from harness.domain.engagement.model import Engagement, EngagementStatus


# ── Stubs ────────────────────────────────────────────────────────────


class _StubEngagementRepository:
    """Stub EngagementRepository for testing."""

    def __init__(self, engagements: dict[str, Engagement] | None = None):
        self._engagements = engagements or {}
        self._saved: list[str] = []

    def load(self, slug: str) -> Engagement:
        if slug not in self._engagements:
            from harness.errors import EngagementNotFoundError
            raise EngagementNotFoundError(f"Engagement '{slug}' not found")
        return self._engagements[slug]

    def save(self, engagement: Engagement) -> None:
        self._engagements[engagement.slug] = engagement
        self._saved.append(engagement.slug)

    @property
    def saved_slugs(self) -> list[str]:
        return list(self._saved)


class _StubWorkflowState:
    """Minimal workflow state stub."""

    def __init__(
        self,
        completed_phases: list[str] | None = None,
        current_phase: str | None = "design",
    ):
        self.completed_phases = completed_phases or ["discover"]
        self.current_phase = current_phase

    def mark_phase_failed(self, phase_name: str) -> None:
        self.current_phase = None
        self._failed = True


class _StubWorkflowOrchestrator:
    """Stub WorkflowOrchestrator."""

    def __init__(self):
        self._states: dict[str, _StubWorkflowState] = {}
        self._failed_phases: list[str] = []

    def get_state(self, slug: str):
        return self._states.get(slug)

    def set_state(self, slug: str, state: _StubWorkflowState):
        self._states[slug] = state


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def active_engagement() -> Engagement:
    return Engagement(
        slug="active-eng",
        status=EngagementStatus.ACTIVE,
        current_phase="design",
        created_at=datetime.now(),
        last_active=datetime.now(),
        workflow_name="standard",
    )


@pytest.fixture
def created_engagement() -> Engagement:
    return Engagement(
        slug="new-eng",
        status=EngagementStatus.CREATED,
        current_phase=None,
        created_at=datetime.now(),
        last_active=datetime.now(),
    )


@pytest.fixture
def repo_with_engagements(
    active_engagement: Engagement,
    created_engagement: Engagement,
) -> _StubEngagementRepository:
    return _StubEngagementRepository(
        engagements={
            "active-eng": active_engagement,
            "new-eng": created_engagement,
        }
    )


# ── Tests ────────────────────────────────────────────────────────────


class TestAbortHandler:
    """AbortHandler — abort operations."""

    def test_hard_abort_active_engagement(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Hard abort on active engagement → transition to ABORTED."""
        handler = AbortHandler(engagement_repository=repo_with_engagements)

        result = handler.hard_abort("active-eng")

        assert result.success is True
        assert result.slug == "active-eng"
        assert result.mode == "hard"
        assert result.previous_status == "active"

        # Verify engagement was saved in ABORTED status
        saved = repo_with_engagements._engagements["active-eng"]
        assert saved.status == EngagementStatus.ABORTED
        assert "active-eng" in repo_with_engagements.saved_slugs

    def test_hard_abort_created_engagement(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Hard abort on created (not yet active) engagement."""
        handler = AbortHandler(engagement_repository=repo_with_engagements)

        result = handler.hard_abort("new-eng")

        assert result.success is True
        assert result.slug == "new-eng"
        assert result.previous_status == "created"

        saved = repo_with_engagements._engagements["new-eng"]
        assert saved.status == EngagementStatus.ABORTED

    def test_graceful_stop(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Graceful stop → marks as ABORTED (simulates step completion)."""
        handler = AbortHandler(engagement_repository=repo_with_engagements)

        result = handler.graceful_stop("active-eng")

        assert result.success is True
        assert result.slug == "active-eng"
        assert result.mode == "graceful"

        saved = repo_with_engagements._engagements["active-eng"]
        assert saved.status == EngagementStatus.ABORTED

    def test_abort_with_workflow_orchestrator(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Abort with workflow orchestrator → updates workflow state."""
        wf = _StubWorkflowOrchestrator()
        wf.set_state(
            "active-eng",
            _StubWorkflowState(
                completed_phases=["discover"],
                current_phase="design",
            ),
        )
        handler = AbortHandler(
            engagement_repository=repo_with_engagements,
            workflow_orchestrator=wf,
        )

        result = handler.hard_abort("active-eng")

        assert result.success is True
        assert result.completed_phases == ["discover"]
        assert result.current_phase == "design"

    def test_hard_abort_unknown_engagement(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Abort on non-existent engagement → error result."""
        handler = AbortHandler(engagement_repository=repo_with_engagements)

        result = handler.hard_abort("missing-eng")

        assert result.success is False
        assert result.slug == "missing-eng"
        assert "missing-eng" in result.error

    def test_stub_mode(self):
        """No repository configured → stub result."""
        handler = AbortHandler()

        result = handler.hard_abort("stub-eng")

        assert result.success is True
        assert result.slug == "stub-eng"
        assert result.mode == "hard"
        assert result.previous_status == "stub"

    def test_graceful_stub_mode(self):
        """No repository configured → stub result for graceful."""
        handler = AbortHandler()

        result = handler.graceful_stop("stub-eng")

        assert result.success is True
        assert result.mode == "graceful"

    def test_hard_and_graceful_return_different_modes(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Hard abort and graceful stop return different mode values."""
        handler = AbortHandler(engagement_repository=repo_with_engagements)

        hard_result = handler.hard_abort("active-eng")
        assert hard_result.mode == "hard"

        # Re-create engagement for second test
        repo_with_engagements._engagements["active-eng"] = Engagement(
            slug="active-eng",
            status=EngagementStatus.ACTIVE,
            current_phase="design",
            created_at=datetime.now(),
            last_active=datetime.now(),
        )

        graceful_result = handler.graceful_stop("active-eng")
        assert graceful_result.mode == "graceful"

    def test_completed_phases_from_workflow(
        self,
        repo_with_engagements: _StubEngagementRepository,
    ):
        """Completed phases tracked in abort result."""
        wf = _StubWorkflowOrchestrator()
        wf.set_state(
            "active-eng",
            _StubWorkflowState(
                completed_phases=["discover", "design"],
                current_phase="build",
            ),
        )
        handler = AbortHandler(
            engagement_repository=repo_with_engagements,
            workflow_orchestrator=wf,
        )

        result = handler.graceful_stop("active-eng")

        assert result.success is True
        assert result.completed_phases == ["discover", "design"]
        assert result.current_phase == "build"


class TestAbortResult:
    """AbortResult dataclass."""

    def test_defaults(self):
        result = AbortResult(success=True, slug="test")
        assert result.success is True
        assert result.slug == "test"
        assert result.mode == "hard"
        assert result.previous_status == ""
        assert result.completed_phases == []
        assert result.current_phase is None
        assert result.error == ""

    def test_graceful_mode_default(self):
        result = AbortResult(success=True, slug="test", mode="graceful")
        assert result.mode == "graceful"
