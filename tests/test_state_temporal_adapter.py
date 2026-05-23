"""Tests for harness.state.temporal_adapter — CLI-to-Temporal bridge.

These tests mock the Temporal client, server, and worker to avoid needing
an actual Temporal deployment.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harness.state.temporal_adapter import (
    _get_client,
    start_engagement,
    send_gate_review,
    send_work_done,
    get_summary,
    get_state,
    TEMPORAL_HOST,
    NAMESPACE,
    _client,
)


class TestGetClient:
    """Tests for the internal _get_client helper."""

    async def test_creates_client_on_first_call(self):
        with patch("harness.state.temporal_adapter.temporal_client.Client.connect",
                   new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = "fake-client"

            # Reset global
            import harness.state.temporal_adapter as mod
            mod._client = None

            client = await _get_client()

            assert client == "fake-client"
            mock_connect.assert_called_once_with(TEMPORAL_HOST)

    async def test_caches_client(self):
        with patch("harness.state.temporal_adapter.temporal_client.Client.connect",
                   new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = "fake-client"

            import harness.state.temporal_adapter as mod
            mod._client = None

            c1 = await _get_client()
            c2 = await _get_client()

            assert c1 == c2
            mock_connect.assert_called_once()

    async def test_uses_same_host_constant(self):
        with patch("harness.state.temporal_adapter.temporal_client.Client.connect",
                   new_callable=AsyncMock) as mock_connect:
            import harness.state.temporal_adapter as mod
            mod._client = None

            await _get_client()

            mock_connect.assert_called_once_with(TEMPORAL_HOST)


class TestStartEngagement:
    """Tests for start_engagement()."""

    async def test_starts_workflow(self):
        mock_handle = MagicMock()
        mock_handle.result = AsyncMock(return_value="started")

        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            result = await start_engagement(
                engagement_id="eng-1",
                description="Test engagement",
                gate_mode="auto",
                start_phase="requirements",
            )

            assert result == "started"
            mock_client.start_workflow.assert_called_once()
            args, kwargs = mock_client.start_workflow.call_args
            assert kwargs["id"] == "engagement-eng-1"
            assert kwargs["task_queue"] == "harness-task-queue"
            assert args[0] == "engagement-workflow"

    async def test_passes_config(self):
        mock_handle = MagicMock()
        mock_handle.result = AsyncMock(return_value="started")

        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await start_engagement(
                engagement_id="eng-2",
                description="Custom",
                gate_mode="full",
                start_phase="design",
            )

            args, kwargs = mock_client.start_workflow.call_args
            cfg = args[0]  # workflow type name or could be positional
            # The second positional arg is the config dict
            cfg = args[1]
            assert cfg["engagement_id"] == "eng-2"
            assert cfg["description"] == "Custom"
            assert cfg["gate_mode"] == "full"
            assert cfg["start_phase"] == "design"

    async def test_returns_engagement_id_on_timeout(self):
        mock_handle = MagicMock()
        mock_handle.result = AsyncMock(side_effect=asyncio.TimeoutError("timed out"))

        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            result = await start_engagement(
                engagement_id="eng-timeout",
                description="Timeout test",
            )

            assert result == "eng-timeout"

    async def test_uses_defaults(self):
        mock_handle = MagicMock()
        mock_handle.result = AsyncMock(return_value="started")

        mock_client = MagicMock()
        mock_client.start_workflow = AsyncMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await start_engagement(
                engagement_id="eng-default",
                description="Defaults",
            )

            args, kwargs = mock_client.start_workflow.call_args
            cfg = args[1]
            assert cfg["gate_mode"] == "auto"
            assert cfg["start_phase"] == "requirements"


class TestSendGateReview:
    """Tests for send_gate_review()."""

    async def test_sends_signal(self):
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await send_gate_review(
                engagement_id="eng-1",
                phase="build",
                decision="approved",
                notes="Good work!",
            )

            mock_handle.signal.assert_called_once()
            args, kwargs = mock_handle.signal.call_args
            assert args[0] == "gate_review"
            assert args[1]["decision"] == "approved"
            assert args[1]["notes"] == "Good work!"

    async def test_get_workflow_handle(self):
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await send_gate_review(
                engagement_id="eng-special",
                phase="design",
                decision="rejected",
            )

            mock_client.get_workflow_handle.assert_called_once_with(
                "engagement-eng-special"
            )


class TestSendWorkDone:
    """Tests for send_work_done()."""

    async def test_sends_signal_with_minimal_args(self):
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await send_work_done(
                engagement_id="eng-1",
                task_id="task-1",
                status="completed",
            )

            mock_handle.signal.assert_called_once()
            args, kwargs = mock_handle.signal.call_args
            assert args[0] == "work_done"
            assert args[1]["task_id"] == "task-1"

    async def test_with_output_files(self):
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await send_work_done(
                engagement_id="eng-1",
                task_id="task-1",
                status="partial",
                output_files=["out1.txt", "out2.txt"],
                summary="Partial completion",
            )

            args, kwargs = mock_handle.signal.call_args
            signal_data = args[1]
            assert signal_data["output_files"] == ["out1.txt", "out2.txt"]
            assert signal_data["summary"] == "Partial completion"

    async def test_default_output_files(self):
        mock_handle = MagicMock()
        mock_handle.signal = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            await send_work_done(
                engagement_id="eng-1",
                task_id="task-1",
            )

            args, kwargs = mock_handle.signal.call_args
            assert args[1]["output_files"] == []


class TestGetSummary:
    """Tests for get_summary()."""

    async def test_queries_summary(self):
        mock_handle = MagicMock()
        mock_handle.query = AsyncMock(return_value={"status": "in_progress"})

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            result = await get_summary("eng-1")

            assert result == {"status": "in_progress"}
            mock_handle.query.assert_called_once_with("summary")


class TestGetState:
    """Tests for get_state()."""

    async def test_queries_state(self):
        mock_handle = MagicMock()
        mock_handle.query = AsyncMock(
            return_value={"status": "completed", "phase": "review"}
        )

        mock_client = MagicMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        with patch(
            "harness.state.temporal_adapter.ensure_worker",
            return_value=True,
        ), patch(
            "harness.state.temporal_adapter._get_client",
            return_value=mock_client,
        ):
            result = await get_state("eng-1")

            assert result == {"status": "completed", "phase": "review"}
            mock_handle.query.assert_called_once_with("state")
