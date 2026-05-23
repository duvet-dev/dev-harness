"""Temporal state adapter — bridges CLI commands to Temporal workflow state.

In Phase 1, this module delegated to Phase1StateStore.
In Phase 2 (Wave 6), this connects to the Temporal dev server and
interacts with EngagementWorkflow via signals, queries, and client calls.

Architecture §2.2: Temporal workflow memory is the sole runtime source of truth.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from temporalio import client as temporal_client

from harness.state.temporal_server import ensure_temporal_server
from harness.state.temporal_worker import ensure_worker

TEMPORAL_HOST = "localhost:7233"
NAMESPACE = "default"
_client = None


async def _get_client():
    """Get or create a cached Temporal client."""
    global _client
    if _client is None:
        _client = await temporal_client.Client.connect(TEMPORAL_HOST)
    return _client


async def start_engagement(
    engagement_id: str,
    description: str,
    gate_mode: str = "auto",
    start_phase: str = "requirements",
) -> str:
    """Start a new EngagementWorkflow on the Temporal server."""
    ensure_worker()
    client = await _get_client()
    handle = await client.start_workflow(
        "engagement-workflow",
        {
            "engagement_id": engagement_id,
            "description": description,
            "gate_mode": gate_mode,
            "start_phase": start_phase,
        },
        id=f"engagement-{engagement_id}",
        task_queue="harness-task-queue",
    )
    try:
        result: str = await asyncio.wait_for(
            handle.result(), timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        # Workflow didn't complete within timeout; return idempotent result
        return engagement_id


async def send_gate_review(
    engagement_id: str,
    phase: str,
    decision: str,
    notes: str = "",
) -> None:
    """Send a gate review signal to an engagement workflow."""
    from harness.workflows.signals import GateReviewSignal

    ensure_worker()
    client = await _get_client()
    handle = client.get_workflow_handle(f"engagement-{engagement_id}")
    signal = GateReviewSignal(
        engagement_id=engagement_id,
        phase=phase,
        decision=decision,
        notes=notes,
    )
    await handle.signal("gate_review", signal.to_dict())


async def send_work_done(
    engagement_id: str,
    task_id: str,
    status: str = "completed",
    output_files: Optional[list[str]] = None,
    summary: str = "",
) -> None:
    """Send a work done signal to an engagement workflow."""
    if output_files is None:
        output_files = []

    ensure_worker()
    client = await _get_client()
    handle = client.get_workflow_handle(f"engagement-{engagement_id}")
    await handle.signal("work_done", {
        "engagement_id": engagement_id,
        "task_id": task_id,
        "status": status,
        "output_files": output_files,
        "summary": summary,
    })


async def get_summary(engagement_id: str) -> dict:
    """Query the engagement workflow for a summary."""
    ensure_worker()
    client = await _get_client()
    handle = client.get_workflow_handle(f"engagement-{engagement_id}")
    return await handle.query("summary")


async def get_state(engagement_id: str) -> dict:
    """Query the engagement workflow for full state."""
    ensure_worker()
    client = await _get_client()
    handle = client.get_workflow_handle(f"engagement-{engagement_id}")
    return await handle.query("state")
