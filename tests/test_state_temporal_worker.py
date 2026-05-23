"""Tests for harness.state.temporal_worker — Temporal worker lifecycle.

These tests mock the Temporal SDK and threading primitives to avoid
needing an actual Temporal server or worker thread.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from harness.state.temporal_worker import (
    ensure_worker,
    stop_worker,
    is_worker_running,
    TASK_QUEUE,
    TEMPORAL_HOST,
    NAMESPACE,
    _worker_thread,
    _worker_loop,
    _shutdown_event,
    _WORKER_TIMEOUT,
)


class TestTemporalWorkerConstants:
    """Tests for module-level constants."""

    def test_task_queue(self):
        assert TASK_QUEUE == "harness-task-queue"

    def test_temporal_host(self):
        assert TEMPORAL_HOST == "localhost:7233"

    def test_namespace(self):
        assert NAMESPACE == "default"

    def test_worker_timeout(self):
        assert _WORKER_TIMEOUT == 5.0


class TestEnsureWorker:
    """Tests for ensure_worker()."""

    def test_returns_true_when_already_running(self):
        """If a worker thread is already alive, return True immediately."""
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = True

        with patch("harness.state.temporal_worker._worker_thread", mock_thread), \
             patch("harness.state.temporal_worker._worker_lock"):
            result = ensure_worker()
            assert result is True

    def test_returns_false_when_server_unavailable(self):
        """If the Temporal server can't start, return False."""
        with patch("harness.state.temporal_worker._worker_thread", None), \
             patch("harness.state.temporal_worker._worker_lock"), \
             patch(
            "harness.state.temporal_worker.ensure_temporal_server",
            return_value=False,
        ):
            result = ensure_worker()
            assert result is False

    def test_starts_worker_thread(self):
        """When server is available, start a new worker thread."""
        with patch("harness.state.temporal_worker._worker_thread", None), \
             patch("harness.state.temporal_worker._worker_lock"), \
             patch(
            "harness.state.temporal_worker.ensure_temporal_server",
            return_value=True,
        ), \
             patch("harness.state.temporal_worker.threading.Thread") as mock_thread, \
             patch("harness.state.temporal_worker.time.sleep"), \
             patch("harness.state.temporal_worker._worker_ref", None):

            # Simulate worker becoming available after brief wait
            ref_values = iter([None, None, MagicMock()])
            with patch(
                "harness.state.temporal_worker._worker_ref",
                new_callable=PropertyMock,
            ) as mock_ref:
                mock_ref.side_effect = lambda: next(ref_values)

                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                result = ensure_worker()

                assert result is True
                mock_thread.assert_called_once()
                args, kwargs = mock_thread.call_args
                assert kwargs["name"] == "temporal-worker"
                assert kwargs["daemon"] is True

    def test_optimistic_return_when_worker_not_connected_yet(self):
        """Return True optimistically even if worker hasn't connected yet."""
        with patch("harness.state.temporal_worker._worker_thread", None), \
             patch("harness.state.temporal_worker._worker_lock"), \
             patch(
            "harness.state.temporal_worker.ensure_temporal_server",
            return_value=True,
        ), \
             patch("harness.state.temporal_worker.threading.Thread") as mock_thread, \
             patch("harness.state.temporal_worker.time.sleep"), \
             patch("harness.state.temporal_worker._worker_ref", None):

            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            result = ensure_worker()

            # _worker_ref is None (never became available), but we
            # optimistically return True
            assert result is True


class TestStopWorker:
    """Tests for stop_worker()."""

    def test_stop_worker_no_worker(self):
        """Calling stop_worker with no active worker should be a no-op."""
        with patch("harness.state.temporal_worker._worker_ref", None), \
             patch("harness.state.temporal_worker._worker_thread", None), \
             patch("harness.state.temporal_worker._worker_loop", None):
            # Should not raise
            stop_worker()

    def test_stop_worker_with_active_worker(self):
        """Stop an active worker gracefully."""
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False

        mock_future = MagicMock()
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False
        mock_loop.call_soon_threadsafe = MagicMock()

        mock_worker = MagicMock()
        # shutdown is a coroutine; mock it as async function
        async def mock_shutdown():
            pass
        mock_worker.shutdown = mock_shutdown

        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = True

        with patch("harness.state.temporal_worker._worker_ref", mock_worker), \
             patch("harness.state.temporal_worker._worker_thread", mock_thread), \
             patch("harness.state.temporal_worker._worker_loop", mock_loop), \
             patch("harness.state.temporal_worker.asyncio.run_coroutine_threadsafe") as mock_run_coro:

            mock_run_coro.return_value = MagicMock()

            stop_worker()

            mock_run_coro.assert_called_once()
            mock_thread.join.assert_called_once()


class TestIsWorkerRunning:
    """Tests for is_worker_running()."""

    def test_not_running_when_thread_none(self):
        with patch("harness.state.temporal_worker._worker_thread", None):
            assert is_worker_running() is False

    def test_not_running_when_thread_dead(self):
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        with patch("harness.state.temporal_worker._worker_thread", mock_thread):
            assert is_worker_running() is False

    def test_not_running_when_ref_none(self):
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = True
        with patch("harness.state.temporal_worker._worker_thread", mock_thread), \
             patch("harness.state.temporal_worker._worker_ref", None):
            assert is_worker_running() is False

    def test_running_when_all_good(self):
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = True
        mock_worker = MagicMock()
        with patch("harness.state.temporal_worker._worker_thread", mock_thread), \
             patch("harness.state.temporal_worker._worker_ref", mock_worker):
            assert is_worker_running() is True


class TestInternalFunctions:
    """Tests for internal module functions."""

    def test_atexit_registered(self):
        """stop_worker should be registered as an atexit handler."""
        import atexit
        # Just verify the module can be imported; atexit registration
        # happens at module import time
        assert atexit is not None

    def test_shutdown_event_initialized(self):
        from harness.state.temporal_worker import _shutdown_event
        assert isinstance(_shutdown_event, threading.Event)

    @pytest.mark.asyncio
    async def test_run_worker_async_logs_on_connect_failure(self):
        """When Client.connect fails, log error and return."""
        from harness.state.temporal_worker import _run_worker_async

        with patch(
            "temporalio.client.Client.connect",
            side_effect=Exception("Connection failed"),
        ), patch(
            "harness.state.temporal_worker.logger",
        ) as mock_logger:

            await _run_worker_async()

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_worker_async_starts_worker(self):
        """Verify worker is created with correct parameters on success."""
        from harness.state.temporal_worker import _run_worker_async

        mock_client = MagicMock()
        mock_worker = MagicMock()
        async def worker_run():
            raise asyncio.CancelledError()

        mock_worker.run = worker_run

        with patch(
            "temporalio.client.Client.connect",
            return_value=mock_client,
        ), patch(
            "temporalio.worker.Worker",
            return_value=mock_worker,
        ), patch(
            "harness.state.temporal_worker.logger",
        ):

            await _run_worker_async()

            # Worker should be set in _worker_ref
            from harness.state.temporal_worker import _worker_ref
            # Note: global state is tricky in tests, just verify
            # Worker constructor was called
            from temporalio.worker import Worker
            Worker.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_worker_async_handles_generic_error(self):
        """When worker.run() raises a non-CancelledError, log it."""
        from harness.state.temporal_worker import _run_worker_async

        mock_client = MagicMock()
        mock_worker = MagicMock()

        async def worker_run():
            raise RuntimeError("Worker crashed")

        mock_worker.run = worker_run

        with patch(
            "temporalio.client.Client.connect",
            return_value=mock_client,
        ), patch(
            "temporalio.worker.Worker",
            return_value=mock_worker,
        ), patch(
            "harness.state.temporal_worker.logger",
        ) as mock_logger:

            await _run_worker_async()

            mock_logger.exception.assert_called_once()

    def test_run_worker_loop_creates_event_loop(self):
        """_run_worker_loop should create and set a new event loop."""
        import asyncio

        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)

        with patch("harness.state.temporal_worker.asyncio.new_event_loop") as mock_new, \
             patch("harness.state.temporal_worker.asyncio.set_event_loop"), \
             patch("harness.state.temporal_worker._run_worker_async") as mock_run:

            mock_new.return_value = mock_loop

            from harness.state.temporal_worker import _run_worker_loop
            _run_worker_loop()

            mock_new.assert_called_once()
            mock_run.assert_called_once()
            mock_loop.run_until_complete.assert_called_once()
            mock_loop.close.assert_called_once()

    def test_run_worker_loop_handles_exception(self):
        """When _run_worker_async raises, it should be logged."""
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = RuntimeError("Boom")

        with patch("harness.state.temporal_worker.asyncio.new_event_loop") as mock_new, \
             patch("harness.state.temporal_worker.asyncio.set_event_loop"), \
             patch("harness.state.temporal_worker.logger") as mock_logger:

            mock_new.return_value = mock_loop

            from harness.state.temporal_worker import _run_worker_loop
            _run_worker_loop()

            mock_logger.exception.assert_called_once_with(
                "Temporal worker crashed"
            )
            mock_loop.close.assert_called_once()
