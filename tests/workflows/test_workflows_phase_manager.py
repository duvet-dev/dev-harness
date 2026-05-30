"""Tests for harness.workflows.phases.phase_manager — PhaseManager workflow.

PhaseManager is a Temporal workflow. These tests validate the logic of
feedback filtering, context building, and config routing by testing the
static methods and simulating the run method with mocked Temporal calls.
"""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class AwaitableResult:
    """A non-coroutine awaitable wrapper for sync values.

    When ``AsyncMock._execute_mock_call`` returns this as a side_effect
    result, the outer ``await`` in ``outputs = await mock_exec(...)``
    yields this object, NOT a coroutine. The result is that ``outputs``
    is an ``AwaitableResult`` instance (not the inner value), but the
    value is accessible via ``await outputs`` or ``outputs.value``.

    Unlike plain coroutines (``_async_val``), an ``AwaitableResult``
    never triggers ``RuntimeWarning: coroutine ... was never awaited``
    when garbage collected, because it is NOT a coroutine object.
    """

    def __init__(self, value):
        self._v = value

    @property
    def value(self):
        return self._v

    def __await__(self):
        yield
        return self._v

    def __repr__(self):
        return f"<AwaitableResult {self._v!r}>"


from harness.workflows.phases.phase_manager import (
    PhaseManager,
    _REEXECUTION_SEVERITIES,
)
from harness.workflows.signals import FeedbackItem


class TestPhaseManagerConstants:
    """Tests for module-level constants."""

    def test_reexecution_severities(self):
        assert _REEXECUTION_SEVERITIES == frozenset({"blocker", "major"})


class TestPhaseManagerFilterAgents:
    """Tests for the static _filter_agents method."""

    def test_no_feedback_returns_all(self):
        agents = [
            {"target_directory": "src/", "task_id": "t1"},
            {"target_directory": "tests/", "task_id": "t2"},
        ]
        result = PhaseManager._filter_agents(agents, [], True)
        assert result == agents

    def test_partial_approval_false_returns_all(self):
        agents = [{"target_directory": "src/", "task_id": "t1"}]
        feedback = [
            FeedbackItem(
                finding="Bug",
                severity="blocker",
                artifact_ref="src/main.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, False)
        assert result == agents

    def test_only_minor_feedback_returns_empty(self):
        agents = [{"target_directory": "src/", "task_id": "t1"}]
        feedback = [
            FeedbackItem(
                finding="Cosmetic",
                severity="minor",
                artifact_ref="src/main.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert result == []

    def test_blocker_feedback_filters(self):
        agents = [
            {"target_directory": "src/", "task_id": "t1"},
            {"target_directory": "docs/", "task_id": "t2"},
        ]
        feedback = [
            FeedbackItem(
                finding="Security issue",
                severity="blocker",
                artifact_ref="src/main.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert len(result) == 1
        assert result[0]["task_id"] == "t1"

    def test_major_feedback_filters(self):
        agents = [
            {"target_directory": "api/", "task_id": "api-task"},
            {"target_directory": "ui/", "task_id": "ui-task"},
        ]
        feedback = [
            FeedbackItem(
                finding="Performance issue",
                severity="major",
                artifact_ref="api/routes.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert len(result) == 1
        assert result[0]["task_id"] == "api-task"

    def test_multiple_blockers_returns_unique_agents(self):
        agents = [
            {"target_directory": "src/", "task_id": "dev-task"},
            {"target_directory": "tests/", "task_id": "test-task"},
        ]
        feedback = [
            FeedbackItem(
                finding="Bug A",
                severity="blocker",
                artifact_ref="src/main.py",
            ),
            FeedbackItem(
                finding="Bug B",
                severity="major",
                artifact_ref="tests/test_main.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert len(result) == 2

    def test_fallback_when_filtered_empty(self):
        """When filter matches nothing, _filter_agents returns agents unchanged."""
        agents = [{"target_directory": "xyz/", "task_id": "xyz"}]
        feedback = [
            FeedbackItem(
                finding="Issue",
                severity="blocker",
                artifact_ref="abc/",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert result == agents

    def test_agent_ref_is_task_id(self):
        """Match on task_id when target_directory is absent."""
        agents = [
            {"task_id": "src-component"},
            {"task_id": "docs-component"},
        ]
        feedback = [
            FeedbackItem(
                finding="Bug",
                severity="blocker",
                artifact_ref="src-component",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        assert len(result) == 1
        assert result[0]["task_id"] == "src-component"


class TestPhaseManagerBuildFeedbackContextLines:
    """Tests for the static _build_feedback_context_lines method."""

    def test_empty_feedback(self):
        result = PhaseManager._build_feedback_context_lines([])
        assert result == []

    def test_single_item_with_suggestion(self):
        feedback = [
            FeedbackItem(
                finding="Typo",
                severity="minor",
                artifact_ref="README.md",
                suggestion="Fix spelling",
            ),
        ]
        lines = PhaseManager._build_feedback_context_lines(feedback)
        assert len(lines) > 0
        assert "Feedback from previous iteration" in lines[1]
        assert "suggestion: Fix spelling" in lines[-2]

    def test_single_item_without_suggestion(self):
        feedback = [
            FeedbackItem(
                finding="Bug",
                severity="blocker",
                artifact_ref="main.py",
            ),
        ]
        lines = PhaseManager._build_feedback_context_lines(feedback)
        assert len(lines) > 0
        assert "suggestion:" not in "\n".join(lines)

    def test_multiple_items(self):
        feedback = [
            FeedbackItem(
                finding="Error A", severity="blocker", artifact_ref="a.py"
            ),
            FeedbackItem(
                finding="Error B", severity="major", artifact_ref="b.py"
            ),
        ]
        lines = PhaseManager._build_feedback_context_lines(feedback)
        assert "[blocker]" in "\n".join(lines)
        assert "[major]" in "\n".join(lines)

    def test_output_format(self):
        feedback = [
            FeedbackItem(
                finding="Fix formatting",
                severity="minor",
                artifact_ref="src/utils.py",
                suggestion="Use black",
            ),
        ]
        lines = PhaseManager._build_feedback_context_lines(feedback)
        assert lines[0] == "---"
        assert lines[-1] == "---"

    def test_all_severities_included(self):
        feedback = [
            FeedbackItem(finding="A", severity=s, artifact_ref="f.py")
            for s in ("blocker", "major", "minor", "suggestion")
        ]
        lines = PhaseManager._build_feedback_context_lines(feedback)
        full = "\n".join(lines)
        for s in ("blocker", "major", "minor", "suggestion"):
            assert f"[{s}]" in full


class TestPhaseManagerRun:
    """Tests for the PhaseManager.run method with mocked Temporal calls.

    We replace ``asyncio.gather`` with a fake that awaits all coroutine
    arguments (consuming mock coroutines to prevent unawaited-coroutine
    warnings), then returns predetermined results.

    Side effect items for ``workflow.execute_activity``:
    - Agent-future items: plain dicts (the gather consumes the
      ``_execute_mock_call`` coroutine but doesn't care about the result).
    - Actually-``await``-ed items (collect_outputs, aggregate, etc.):
      ``AwaitableResult`` wrappers. These are NOT coroutine objects,
      so they never trigger the ``was never awaited`` GC warning.
    """

    @staticmethod
    def _make_gather(*gather_results):
        """Return an async gather-compatible function.

        Awaits each argument (consuming mock coroutines), catches
        exceptions, returns *gather_results* as-is.
        """
        async def gather(*args, **kwargs):
            results = []
            for arg in args:
                try:
                    if asyncio.iscoroutine(arg):
                        r = await arg
                        results.append(r)
                    elif hasattr(arg, '__await__'):
                        r = await arg
                        results.append(r)
                    else:
                        results.append(arg)
                except BaseException as e:
                    results.append(e)
            return list(gather_results)
        return gather

    @pytest.mark.asyncio
    async def test_run_parallel_execution(self):
        gather_fn = self._make_gather(
            {"engagement_id": "eng-1", "task_id": "task-0", "status": "completed",
             "output_files": ["out/file1.txt"]},
            {"engagement_id": "eng-1", "task_id": "task-1", "status": "completed",
             "output_files": ["out/file2.txt"]},
        )

        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio.gather", gather_fn
        ):

            mock_exec.side_effect = [
                {},  # agent future 0 (plain dict — coroutine consumed by gather)
                {},  # agent future 1
                AwaitableResult({}),  # collect_outputs agent 0
                AwaitableResult({}),  # collect_outputs agent 1
                AwaitableResult({"total_files": 2, "total_size_bytes": 100, "agents": 1}),
                AwaitableResult({"passed": True, "coverage": 95.0, "target": 0.9}),
                AwaitableResult({}),  # snapshot_state
            ]

            pm = PhaseManager()
            result = await pm.run({
                "engagement_id": "eng-1",
                "phase_name": "build",
                "agents": [
                    {"task_id": "task-0", "spec_content": "Build task 0"},
                    {"task_id": "task-1", "spec_content": "Build task 1"},
                ],
            })

            assert result["phase"] == "build"
            assert result["agents_total"] == 2
            assert result["agents_succeeded"] == 2
            assert result["agents_failed"] == 0

    @pytest.mark.asyncio
    async def test_run_with_feedback_and_partial_approval(self):
        gather_fn = self._make_gather(
            {"engagement_id": "eng-1", "task_id": "task-0", "status": "completed",
             "output_files": ["out/file.txt"]},
        )

        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio.gather", gather_fn
        ):

            mock_exec.side_effect = [
                {},  # agent future 0
                AwaitableResult({}),  # collect_outputs
                AwaitableResult({"total_files": 2, "total_size_bytes": 100, "agents": 1}),
                AwaitableResult({"passed": True, "coverage": 95.0, "target": 0.9}),
                AwaitableResult({}),  # snapshot_state
            ]

            pm = PhaseManager()
            result = await pm.run({
                "engagement_id": "eng-1",
                "phase_name": "build",
                "agents": [
                    {"target_directory": "src/", "task_id": "task-0",
                     "spec_content": "Fix src"},
                    {"target_directory": "docs/", "task_id": "task-1",
                     "spec_content": "Fix docs"},
                ],
                "feedback": [
                    {
                        "finding": "Logic error",
                        "severity": "blocker",
                        "artifact_ref": "src/main.py",
                    },
                ],
                "partial_approval": True,
            })

            assert result["phase"] == "build"

    @pytest.mark.asyncio
    async def test_run_with_errors(self):
        """One agent succeeds, one raises/fails."""
        gather_fn = self._make_gather(
            {"engagement_id": "e", "task_id": "t1", "status": "completed",
             "output_files": []},
            RuntimeError("Agent crashed"),
        )

        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio.gather", gather_fn
        ):

            mock_exec.side_effect = [
                {},  # agent future 0
                {},  # agent future 1
                AwaitableResult({}),  # collect_outputs (1 successful → 1 iteration)
                AwaitableResult({"total_files": 2, "total_size_bytes": 100, "agents": 1}),
                AwaitableResult({"passed": True, "coverage": 95.0, "target": 0.9}),
                AwaitableResult({}),  # snapshot_state
            ]

            pm = PhaseManager()
            result = await pm.run({
                "engagement_id": "eng-1",
                "phase_name": "test",
                "agents": [
                    {"task_id": "t1", "spec_content": "Do task 1"},
                    {"task_id": "t2", "spec_content": "Do task 2"},
                ],
            })

            assert result["agents_succeeded"] == 1
            assert result["agents_failed"] == 1
            assert result["status"] == "completed_with_errors"
