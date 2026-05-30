"""Tests for harness.workflows.phases.run_single_agent.

These activities run inside the Temporal worker's sandbox. We test
the core logic by mocking the Temporal activity context.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from harness.workflows.phases.run_single_agent import (
    run_single_agent,
    run_single_agent_with_retry,
    AgentExecutionError,
)


class TestRunSingleAgent:
    """Tests for the run_single_agent activity."""

    @pytest.mark.asyncio
    async def test_basic_execution(self, tmp_path):
        target = str(tmp_path / "output")
        with patch("harness.workflows.phases.run_single_agent.activity.heartbeat"):
            result = await run_single_agent({
                "engagement_id": "eng-1",
                "task_id": "task-1",
                "phase_name": "build",
                "target_directory": target,
            })

        assert result["engagement_id"] == "eng-1"
        assert result["task_id"] == "task-1"
        assert result["phase_name"] == "build"
        assert result["status"] == "completed"

        # Directory should have been created
        assert Path(target).is_dir()

    @pytest.mark.asyncio
    async def test_defaults_when_missing_keys(self):
        with patch("harness.workflows.phases.run_single_agent.activity.heartbeat"):
            result = await run_single_agent({})

        assert result["engagement_id"] == "unknown"
        assert result["task_id"] == "unknown"
        assert result["phase_name"] == "unknown"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_creates_output_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "path"
        target = str(nested)
        with patch("harness.workflows.phases.run_single_agent.activity.heartbeat"):
            result = await run_single_agent({
                "engagement_id": "eng-1",
                "task_id": "task-1",
                "phase_name": "build",
                "target_directory": target,
            })

        assert nested.is_dir()

    @pytest.mark.asyncio
    async def test_heartbeat_called(self):
        mock_heartbeat = MagicMock()
        with patch(
            "harness.workflows.phases.run_single_agent.activity.heartbeat",
            mock_heartbeat,
        ):
            await run_single_agent({
                "engagement_id": "e",
                "task_id": "t",
                "phase_name": "p",
            })

        # Heartbeat should have been called at least at start and complete
        assert mock_heartbeat.call_count >= 2

    @pytest.mark.asyncio
    async def test_returns_nested_paths_correctly(self, tmp_path):
        target = str(tmp_path / "artifacts")
        (Path(target) / "sub").mkdir(parents=True)
        (Path(target) / "sub" / "result.txt").write_text("ok")

        with patch("harness.workflows.phases.run_single_agent.activity.heartbeat"):
            result = await run_single_agent({
                "engagement_id": "e",
                "task_id": "t",
                "phase_name": "p",
                "target_directory": target,
            })

        # output_files should include files directly in target
        assert any("result.txt" in f for f in result["output_files"])


class TestRunSingleAgentWithRetry:
    """Tests for the run_single_agent_with_retry activity."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, tmp_path):
        with patch("harness.workflows.phases.run_single_agent.activity.heartbeat"):
            result = await run_single_agent_with_retry({
                "engagement_id": "e",
                "task_id": "t",
                "phase_name": "p",
                "target_directory": str(tmp_path / "out"),
            })

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_succeeds_after_retries(self, tmp_path):
        """Test that retry mechanism works when first attempt fails."""
        call_count = [0]

        async def flaky_run(packet):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("Transient error")
            return {"status": "completed", "engagement_id": "e",
                    "task_id": "t", "phase_name": "p",
                    "output_files": [], "artifacts_produced": []}

        with patch(
            "harness.workflows.phases.run_single_agent.run_single_agent",
            flaky_run,
        ), patch(
            "harness.workflows.phases.run_single_agent.activity.heartbeat",
        ), patch(
            "asyncio.sleep",
        ):
            result = await run_single_agent_with_retry({
                "engagement_id": "e",
                "task_id": "t",
                "phase_name": "p",
                "target_directory": str(tmp_path / "out"),
            })

        assert call_count[0] == 3
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self):
        call_count = [0]

        async def always_fails(packet):
            call_count[0] += 1
            raise RuntimeError("Always fails")

        with patch(
            "harness.workflows.phases.run_single_agent.run_single_agent",
            always_fails,
        ), patch(
            "harness.workflows.phases.run_single_agent.activity.heartbeat",
        ), patch(
            "asyncio.sleep",
        ):
            with pytest.raises(AgentExecutionError, match="failed after"):
                await run_single_agent_with_retry({
                    "engagement_id": "e",
                    "task_id": "t",
                    "phase_name": "p",
                })

        assert call_count[0] == 5

    @pytest.mark.asyncio
    async def test_retries_use_exponential_backoff(self):
        sleeps = []

        async def mock_sleep(secs):
            sleeps.append(secs)

        async def always_fails(packet):
            raise RuntimeError("boom")

        with patch(
            "harness.workflows.phases.run_single_agent.run_single_agent",
            always_fails,
        ), patch(
            "harness.workflows.phases.run_single_agent.activity.heartbeat",
        ), patch(
            "asyncio.sleep",
            mock_sleep,
        ):
            with pytest.raises(AgentExecutionError):
                await run_single_agent_with_retry({
                    "engagement_id": "e",
                    "task_id": "t",
                    "phase_name": "p",
                })

        # Should sleep 2^0, 2^1, 2^2, 2^3 = 1, 2, 4, 8 seconds
        assert len(sleeps) == 4
        assert sleeps == [1, 2, 4, 8]

    @pytest.mark.asyncio
    async def test_agent_execution_error_class(self):
        error = AgentExecutionError("Agent failed")
        assert isinstance(error, Exception)
        assert "Agent failed" in str(error)
