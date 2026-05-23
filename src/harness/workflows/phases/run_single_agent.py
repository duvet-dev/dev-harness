"""Per-agent execution activity with heartbeats and error handling."""

from pathlib import Path

from temporalio import activity


class AgentExecutionError(Exception):
    """Raised when an agent fails to complete its task."""


@activity.defn
async def run_single_agent(context_packet: dict) -> dict:
    """Execute a single agent invocation with heartbeats.

    This is the per-agent wrapper the PhaseManager fans out to.
    In Phase 3 this will invoke actual agent backends (CLI/API/editor).
    For Phase 2: validates packet, creates output dirs, returns success.

    Timeout: 32 min. Heartbeat: 15s. Retry: 5 attempts.
    """
    activity.heartbeat("starting")

    engagement_id = context_packet.get("engagement_id", "unknown")
    task_id = context_packet.get("task_id", "unknown")
    phase_name = context_packet.get("phase_name", "unknown")
    target_dir = context_packet.get("target_directory", ".")

    output_path = Path(target_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    activity.heartbeat("directory created")

    result = {
        "engagement_id": engagement_id,
        "task_id": task_id,
        "phase_name": phase_name,
        "status": "completed",
        "output_files": [str(p) for p in output_path.rglob("*") if p.is_file()],
        "artifacts_produced": [],
    }

    activity.heartbeat("complete")
    return result


@activity.defn
async def run_single_agent_with_retry(context_packet: dict) -> dict:
    """Wrapper with exponential backoff retry."""
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            activity.heartbeat(f"attempt {attempt + 1}/{max_attempts}")
            return await run_single_agent(context_packet)
        except Exception as e:
            if attempt < max_attempts - 1:
                import asyncio
                wait = 2 ** attempt
                activity.heartbeat(f"retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                raise AgentExecutionError(
                    f"Agent failed after {max_attempts} attempts: {e}"
                )
