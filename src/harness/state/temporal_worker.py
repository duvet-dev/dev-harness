"""Temporal worker — auto-started in a background daemon thread.

Manages lifecycle: start on demand, reuse across CLI commands, graceful
shutdown on process exit.  Completely invisible to the end user — the
install package handles it.

Usage (the only public API)::

    from harness.state.temporal_worker import ensure_worker

    if ensure_worker():
        # Temporal operations are now being serviced
        ...
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

from harness.state.temporal_server import ensure_temporal_server

if TYPE_CHECKING:
    from temporalio.worker import Worker

logger = logging.getLogger(__name__)

# ── Module-level state ──────────────────────────────────────────────────

_worker_thread: Optional[threading.Thread] = None
_worker_ref: Optional[Worker] = None
_worker_loop: Optional[asyncio.AbstractEventLoop] = None
_worker_lock = threading.Lock()
_shutdown_event = threading.Event()

TASK_QUEUE = "harness-task-queue"
TEMPORAL_HOST = "localhost:7233"
NAMESPACE = "default"
_WORKER_TIMEOUT = 5.0  # seconds to wait for worker to start polling


# ── Public API ──────────────────────────────────────────────────────────


def ensure_worker() -> bool:
    """Ensure the Temporal worker is running in a background thread.

    Idempotent — safe to call before every Temporal operation.
    Returns ``True`` if the worker is (or just became) available.
    Returns ``False`` if Temporal server is unreachable or startup failed.
    """
    global _worker_thread

    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return True

        # ── Step 1: make sure the Temporal server is running ──────────
        if not ensure_temporal_server():
            logger.warning("Temporal server unavailable — worker not started")
            return False

        # Reset the shutdown event so the new thread runs
        _shutdown_event.clear()

        # ── Step 2: start the worker background thread ────────────────
        _worker_thread = threading.Thread(
            target=_run_worker_loop,
            name="temporal-worker",
            daemon=True,
        )
        _worker_thread.start()

    # ── Step 3: brief wait for connection confirmation ────────────────
    deadline = time.monotonic() + _WORKER_TIMEOUT
    while time.monotonic() < deadline:
        if _worker_ref is not None:
            return True
        time.sleep(0.1)

    # Worker thread is alive but hasn't connected yet — optimistically
    # return True so the caller proceeds; the actual Temporal operation
    # will fail at the client.connect() stage with a helpful error.
    logger.info(
        "Worker thread started but not yet connected "
        "(caller will retry if needed)"
    )
    return True


def stop_worker(timeout: float = 5.0) -> None:
    """Signal the worker to shut down gracefully.

    Schedules ``worker.shutdown()`` on the background thread's event loop,
    then waits for the thread to join.

    Called automatically by ``atexit`` — you shouldn't need to call this
    directly.
    """
    global _worker_ref, _worker_thread, _worker_loop

    w = _worker_ref
    loop = _worker_loop

    if w is not None and loop is not None and not loop.is_closed():
        try:
            # Schedule shutdown on the worker's event loop.
            # shutdown() is a coroutine; asyncio.run_coroutine_threadsafe
            # hands it to the right loop and returns a concurrent.futures.Future.
            fut = asyncio.run_coroutine_threadsafe(w.shutdown(), loop)
            fut.result(timeout=timeout)
        except Exception:
            pass

    # Also set the event in case the loop checks it
    _shutdown_event.set()

    t = _worker_thread
    if t and t.is_alive():
        t.join(timeout=timeout)

    _worker_ref = None
    _worker_loop = None
    _worker_thread = None


def is_worker_running() -> bool:
    """Check whether the worker thread is alive and connected."""
    return (
        _worker_thread is not None
        and _worker_thread.is_alive()
        and _worker_ref is not None
    )


# ── Background thread ──────────────────────────────────────────────────


def _run_worker_loop() -> None:
    """Entry point for the background thread."""
    global _worker_loop

    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)

    try:
        _worker_loop.run_until_complete(_run_worker_async())
    except Exception:
        logger.exception("Temporal worker crashed")
    finally:
        _worker_loop.close()
        _worker_loop = None


async def _run_worker_async() -> None:
    """Connect to Temporal and start the polling worker."""
    global _worker_ref

    from temporalio.client import Client
    from temporalio.worker import Worker

    from harness.workflows.activities import (
        aggregate_phase_outputs,
        check_phase_coverage,
        collect_outputs,
        snapshot_state,
        validate_inputs,
    )
    from harness.workflows.engagement import EngagementWorkflow
    from harness.workflows.phases.phase_manager import PhaseManager
    from harness.workflows.phases.run_single_agent import (
        run_single_agent as run_single_agent_activity,
    )

    try:
        client = await Client.connect(TEMPORAL_HOST, namespace=NAMESPACE)
    except Exception as exc:
        logger.error("Failed to connect to Temporal at %s: %s", TEMPORAL_HOST, exc)
        return

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EngagementWorkflow, PhaseManager],
        activities=[
            validate_inputs,
            run_single_agent_activity,
            collect_outputs,
            aggregate_phase_outputs,
            check_phase_coverage,
            snapshot_state,
        ],
    )

    _worker_ref = worker
    logger.info("Temporal worker started on task queue %s", TASK_QUEUE)

    # Block until shutdown is requested.
    # Worker.run() raises CancelledError (or returns gracefully) on
    # shutdown().
    try:
        await worker.run()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Temporal worker.run() exited with error")
    finally:
        logger.info("Temporal worker stopped")


# ── Auto-register shutdown on module import ─────────────────────────────

atexit.register(stop_worker)
