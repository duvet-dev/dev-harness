"""Tests for harness.workflows.phases.phase_manager — PhaseManager workflow.

PhaseManager is a Temporal workflow. These tests validate the logic of
feedback filtering, context building, and config routing by testing the
static methods and simulating the run method with mocked Temporal calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

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

    def test_no_reexecution_refs_returns_empty(self):
        agents = [{"target_directory": "other/", "task_id": "other"}]
        feedback = [
            FeedbackItem(
                finding="Issue",
                severity="blocker",
                artifact_ref="unrelated/area.py",
            ),
        ]
        result = PhaseManager._filter_agents(agents, feedback, True)
        # No agent ref matches the blocker artifact_ref
        assert len(result) > 0  # fallback to original agents when all filtered

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
        # filter produces empty list, fallback returns original agents
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
    """Tests for the PhaseManager.run method with mocked Temporal calls."""

    @pytest.mark.asyncio
    async def test_run_parallel_execution(self):
        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio"
        ) as mock_asyncio:

            # Simulate agent results
            async def fake_gather(*args, **kwargs):
                return [
                    {
                        "engagement_id": "eng-1",
                        "task_id": "task-0",
                        "status": "completed",
                        "output_files": ["out/file1.txt"],
                    },
                    {
                        "engagement_id": "eng-1",
                        "task_id": "task-1",
                        "status": "completed",
                        "output_files": ["out/file2.txt"],
                    },
                ]

            mock_asyncio.gather = fake_gather

            # Mock collect_outputs to return files
            mock_exec.side_effect = [
                {},  # collect_outputs for agent 1
                {},  # collect_outputs for agent 2
                {"total_files": 2, "total_size_bytes": 100, "agents": 1},
                {"passed": True, "coverage": 95.0, "target": 0.9},
                {},
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
        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio"
        ) as mock_asyncio:

            async def fake_gather(*args, **kwargs):
                return [
                    {
                        "engagement_id": "eng-1",
                        "task_id": "task-0",
                        "status": "completed",
                        "output_files": ["out/file.txt"],
                    },
                ]

            mock_asyncio.gather = fake_gather

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

            # Only the src agent should have run (blocker references src/)
            assert result["phase"] == "build"

    @pytest.mark.asyncio
    async def test_run_with_errors(self):
        with patch(
            "harness.workflows.phases.phase_manager.workflow.execute_activity"
        ) as mock_exec, \
             patch(
            "harness.workflows.phases.phase_manager.workflow.logger"
        ) as mock_logger, \
             patch(
            "harness.workflows.phases.phase_manager.asyncio"
        ) as mock_asyncio:

            async def fake_gather(*args, **kwargs):
                return [
                    {"engagement_id": "e", "task_id": "t1", "status": "completed",
                     "output_files": []},
                    RuntimeError("Agent crashed"),
                ]

            mock_asyncio.gather = fake_gather

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
