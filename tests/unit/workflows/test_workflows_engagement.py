"""Tests for harness.workflows.engagement — EngagementWorkflow.

EngagementWorkflow depends on the Temporal SDK's workflow runtime. These
tests validate the workflow's state machine logic by directly exercising
signal/query methods and the iteration logic, mocking the Temporal
workflow context where needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock

from harness.workflows.engagement import (
    EngagementWorkflow,
    ALLOWED_PHASES,
    GATE_TIMEOUT,
)


class TestEngagementWorkflowConstants:
    """Tests for module-level constants."""

    def test_allowed_phases(self):
        assert ALLOWED_PHASES == [
            "requirements", "understanding", "design", "build", "review"
        ]

    def test_gate_timeout(self):
        assert GATE_TIMEOUT.total_seconds() == 72 * 3600


class TestEngagementWorkflowInit:
    """Tests for EngagementWorkflow.__init__."""

    def test_default_state(self):
        wf = EngagementWorkflow()
        assert wf._status == "planning"
        assert wf._phase == "requirements"
        assert wf._gate_mode == "auto"
        assert wf._engagement_id == ""
        assert wf._max_iterations == 5
        assert wf._current_iteration == 0
        assert wf._pending_items == []
        assert wf._retry_count == 0
        assert wf._phases == []
        assert wf._tasks == []
        assert wf._decisions == []
        assert wf._pending_feedback == []
        assert wf._escalation_after_max is True
        assert wf._partial_approval is True


class TestEngagementWorkflowGateReview:
    """Tests for the gate_review signal handler."""

    @pytest.mark.asyncio
    async def test_approved_signal(self):
        wf = EngagementWorkflow()
        wf._phase = "build"

        from harness.workflows.signals import GateReviewSignal, FeedbackItem

        signal = GateReviewSignal(
            engagement_id="eng-1",
            phase="build",
            decision="approved",
            notes="Looks good!",
            feedback=[
                FeedbackItem(
                    finding="Minor typo",
                    severity="minor",
                    artifact_ref="README.md",
                    suggestion="Fix spelling",
                )
            ],
        )
        await wf.gate_review(signal)

        assert wf._gate_decision == "approved"
        assert len(wf._decisions) == 1
        assert wf._decisions[0]["decision"] == "approved"
        assert wf._decisions[0]["notes"] == "Looks good!"
        assert len(wf._decisions[0]["feedback"]) == 1
        assert wf._retry_count == 0

    @pytest.mark.asyncio
    async def test_rejected_signal(self):
        wf = EngagementWorkflow()
        wf._phase = "design"

        from harness.workflows.signals import GateReviewSignal

        signal = GateReviewSignal(
            engagement_id="eng-1",
            phase="design",
            decision="rejected",
            notes="Not acceptable",
        )
        await wf.gate_review(signal)

        assert wf._gate_decision == "rejected"
        assert wf._retry_count == 1

    @pytest.mark.asyncio
    async def test_request_changes_signal(self):
        wf = EngagementWorkflow()
        wf._phase = "build"

        from harness.workflows.signals import GateReviewSignal, FeedbackItem

        signal = GateReviewSignal(
            engagement_id="eng-1",
            phase="build",
            decision="request_changes",
            notes="Need fixes",
            feedback=[
                FeedbackItem(
                    finding="Incorrect logic",
                    severity="blocker",
                    artifact_ref="src/main.py",
                    suggestion="Fix the loop",
                ),
            ],
        )
        await wf.gate_review(signal)

        assert wf._gate_decision == "request_changes"
        assert wf._retry_count == 0  # Only rejected increments retry_count


class TestEngagementWorkflowWorkDone:
    """Tests for the work_done signal handler."""

    @pytest.mark.asyncio
    async def test_work_done_signal(self):
        wf = EngagementWorkflow()

        from harness.workflows.signals import WorkDoneSignal

        signal = WorkDoneSignal(
            engagement_id="eng-1",
            task_id="task-1",
            status="completed",
            summary="All tests pass",
        )
        await wf.work_done(signal)

        assert len(wf._tasks) == 1
        assert wf._tasks[0]["task_id"] == "task-1"
        assert wf._tasks[0]["status"] == "completed"
        assert wf._tasks[0]["summary"] == "All tests pass"


class TestEngagementWorkflowStateReconcile:
    """Tests for the state_reconcile signal handler."""

    @pytest.mark.asyncio
    async def test_state_reconcile_updates_status(self):
        wf = EngagementWorkflow()
        wf._status = "in_progress"

        from harness.workflows.signals import StateReconcileSignal

        signal = StateReconcileSignal(
            engagement_id="eng-1",
            corrected_fields={"status": "blocked"},
        )
        await wf.state_reconcile(signal)

        assert wf._status == "blocked"
        assert wf._pending_items == []

    @pytest.mark.asyncio
    async def test_state_reconcile_updates_phase(self):
        wf = EngagementWorkflow()
        wf._phase = "build"

        from harness.workflows.signals import StateReconcileSignal

        signal = StateReconcileSignal(
            engagement_id="eng-1",
            corrected_fields={"phase": "review"},
        )
        await wf.state_reconcile(signal)

        assert wf._phase == "review"


class TestEngagementWorkflowQueries:
    """Tests for workflow queries."""

    def test_summary_returns_expected_structure(self):
        wf = EngagementWorkflow()
        wf._engagement_id = "eng-1"
        wf._description = "Test engagement"
        wf._status = "in_progress"
        wf._phase = "design"

        summary = wf.summary()
        assert summary["engagement_id"] == "eng-1"
        assert summary["status"] == "in_progress"
        assert summary["phase"] == "design"
        assert summary["gate_mode"] == "auto"
        assert summary["description"] == "Test engagement"

    def test_summary_includes_tasks_and_phases(self):
        wf = EngagementWorkflow()
        wf._phases = [{"phase": "requirements", "status": "completed"}]
        wf._tasks = [{"task_id": "t1", "status": "completed", "summary": "ok"}]

        summary = wf.summary()
        assert len(summary["phases"]) == 1
        assert len(summary["tasks"]) == 1

    def test_state_returns_full_state(self):
        wf = EngagementWorkflow()
        wf._engagement_id = "eng-1"
        wf._description = "Full test"
        wf._status = "in_progress"
        wf._phase = "build"
        wf._gate_mode = "full"
        wf._max_iterations = 3
        wf._current_iteration = 1

        state = wf.state()
        assert state["engagement_id"] == "eng-1"
        assert state["max_iterations"] == 3
        assert state["current_iteration"] == 1
        assert state["phase"] == "build"

    def test_state_includes_pending_feedback(self):
        wf = EngagementWorkflow()

        from harness.workflows.signals import FeedbackItem

        wf._pending_feedback = [
            FeedbackItem(finding="Bug", severity="blocker", artifact_ref="src/main.py"),
        ]

        state = wf.state()
        assert len(state["pending_feedback"]) == 1
        assert state["pending_feedback"][0]["finding"] == "Bug"


class TestEngagementWorkflowRunPhase:
    """Tests for the _run_phase internal method."""

    @pytest.mark.asyncio
    async def test_run_phase_no_feedback(self):
        with patch("harness.workflows.engagement.workflow.logger"):
            wf = EngagementWorkflow()
            wf._phase = "build"
            wf._current_iteration = 0

            result = await wf._run_phase()
            assert result["phase"] == "build"
            assert result["status"] == "completed"
            assert result["iteration"] == 0
            assert result["feedback_count"] == 0

    @pytest.mark.asyncio
    async def test_run_phase_with_feedback(self):
        with patch("harness.workflows.engagement.workflow.logger"):
            wf = EngagementWorkflow()
            wf._phase = "design"
            wf._current_iteration = 2

            from harness.workflows.signals import FeedbackItem

            feedback = [
                FeedbackItem(finding="Fix this", severity="major", artifact_ref="file.py"),
            ]
            result = await wf._run_phase(feedback)
            assert result["phase"] == "design"
            assert result["iteration"] == 2
            assert result["feedback_count"] == 1


class TestEngagementWorkflowRun:
    """Tests for the main run method with mocked Temporal runtime.

    These tests patch workflow.wait_condition and workflow.logger to avoid
    needing an actual Temporal runtime.
    """

    @pytest.mark.asyncio
    async def test_run_auto_gate_approve_all_phases(self):
        """With gate_mode=auto and no pending items, flow completes all phases."""
        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:
            wf = EngagementWorkflow()

            # Set gate_decision immediately so wait returns
            wf._gate_decision = "approved"

            result = await wf.run({
                "engagement_id": "eng-1",
                "description": "Test",
                "gate_mode": "auto",
                "start_phase": "requirements",
            })

            assert result["engagement_id"] == "eng-1"
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_rejected_phase_returns_early(self):
        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger, \
             patch.object(EngagementWorkflow, "_wait_for_gate", new=AsyncMock(return_value=None)):
            wf = EngagementWorkflow()
            wf._gate_decision = "rejected"

            result = await wf.run({
                "engagement_id": "eng-1",
                "description": "Test",
                "gate_mode": "full",
                "start_phase": "requirements",
            })

            assert result["status"] == "rejected"
            assert result["phase"] == "requirements"

    @pytest.mark.asyncio
    async def test_run_with_custom_iteration_config(self):
        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:
            wf = EngagementWorkflow()

            result = await wf.run({
                "engagement_id": "eng-1",
                "description": "Test",
                "gate_mode": "auto",
                "start_phase": "requirements",
                "iteration_config": {
                    "max_iterations": 3,
                    "escalation_after_max": False,
                    "partial_approval": False,
                },
            })

            assert wf._max_iterations == 3
            assert wf._escalation_after_max is False
            assert wf._partial_approval is False
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_with_unknown_engagement_id(self):
        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:
            wf = EngagementWorkflow()

            result = await wf.run({
                "description": "No ID provided",
                "gate_mode": "auto",
                "start_phase": "requirements",
            })

            assert result["engagement_id"] == "unknown"
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_starts_from_later_phase(self):
        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:
            wf = EngagementWorkflow()
            wf._gate_decision = "approved"

            result = await wf.run({
                "engagement_id": "eng-1",
                "description": "Start from design",
                "gate_mode": "auto",
                "start_phase": "design",
            })

            assert result["status"] == "completed"
            assert wf._phases[0]["phase"] == "design"

    @pytest.mark.asyncio
    async def test_run_iteration_loop_request_changes(self):
        """When request_changes is received, the phase should loop."""
        decision_sequence = iter(["request_changes", "approved"])

        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:

            async def set_decision():
                wf._gate_decision = next(decision_sequence)

            mock_wait.side_effect = set_decision

            wf = EngagementWorkflow()

            result = await wf.run({
                "engagement_id": "eng-1",
                "description": "Iteration test",
                "gate_mode": "full",
                "start_phase": "requirements",
            })

            assert result["status"] == "completed"


class TestEngagementWorkflowWaitForGate:
    """Tests for the _wait_for_gate internal method (without actual Temporal)."""

    @pytest.mark.asyncio
    async def test_wait_for_gate_clears_state(self):
        wf = EngagementWorkflow()
        wf._gate_decision = "approved"
        wf._pending_items = ["some-item"]

        with patch("harness.workflows.engagement.workflow.wait_condition") as mock_wait, \
             patch("harness.workflows.engagement.workflow.logger") as mock_logger:
            await wf._wait_for_gate()

        assert wf._gate_decision is None
        assert wf._pending_items == []
