# Temporal activity definitions
# These run in the Temporal worker's sandboxed environment.
# Use `from temporalio import activity` pattern, not `from temporalio.activity`.

import glob as _glob
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from temporalio import activity

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ActivityError(Exception):
    """Base exception for all Temporal activity errors in dev-harness."""


class ValidationError(ActivityError):
    """Raised when input validation fails."""


class OutputCollectionError(ActivityError):
    """Raised when output collection encounters a fatal problem."""


class SnapshotError(ActivityError):
    """Raised when snapshot creation fails."""


# ---------------------------------------------------------------------------
# Required fields for context packet validation
# ---------------------------------------------------------------------------

_REQUIRED_PACKET_FIELDS = {"engagement_id", "phase_name", "task_id", "spec_content"}

# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def validate_inputs(context_packet: dict) -> dict:
    """Validate a serialised ContextPacket dict.

    Checks that all required fields are present and non-empty.
    Timeout: 10 seconds (fast validation).
    """
    try:
        if not isinstance(context_packet, dict):
            raise ValidationError(
                f"Expected dict, got {type(context_packet).__name__}"
            )

        missing = _REQUIRED_PACKET_FIELDS - set(context_packet.keys())
        if missing:
            raise ValidationError(
                f"Missing required field(s): {', '.join(sorted(missing))}"
            )

        empty_fields = [
            k for k in _REQUIRED_PACKET_FIELDS
            if not context_packet.get(k)
        ]
        if empty_fields:
            raise ValidationError(
                f"Empty value(s) for required field(s): {', '.join(sorted(empty_fields))}"
            )

        return {"valid": True, "packet": context_packet}
    except ValidationError:
        raise
    except Exception as exc:
        raise ActivityError(f"Input validation failed: {exc}") from exc


@activity.defn
async def run_single_agent(context_packet: dict) -> dict:
    """Run a single agent on the given context packet.

    Uses AgentOrchestrator with the configured backend. Falls back through
    backend chain if the preferred backend is unavailable.

    Timeout: 32 minutes, heartbeat: 15 seconds.
    """
    try:
        try:
            validated = await validate_inputs(context_packet)
        except ValidationError as ve:
            return {
                "status": "failure",
                "errors": [f"Input validation failed: {ve}"],
            }
        if not validated["valid"]:
            return {
                "status": "failure",
                "errors": ["Input validation failed"],
            }

        # Reconstruct ContextPacket from the serialised dict
        from pathlib import Path

        from harness.agents.context import ContextPacket, OutputContract
        from harness.application.services.agent_service import AgentService
        from harness.infrastructure.plugins.registry import PluginRegistry

        architecture_rules = context_packet.get("architecture_rules", [])
        if isinstance(architecture_rules, str):
            architecture_rules = [architecture_rules]

        packet = ContextPacket(
            engagement_id=context_packet["engagement_id"],
            phase_name=context_packet.get("phase_name", "build"),
            task_id=context_packet["task_id"],
            spec_content=context_packet.get("spec_content", ""),
            architecture_rules=architecture_rules,
            target_directory=Path(
                _agent_output_dir(
                    context_packet["engagement_id"],
                    context_packet.get("phase_name", "build"),
                    context_packet["task_id"],
                )
            ),
            output_contract=OutputContract(
                required_files=context_packet.get("required_files", []),
                coverage_target=context_packet.get("coverage_target", 0.9),
            ),
            constraint_section=context_packet.get("constraint_section", {}),
            input_artifacts=context_packet.get("input_artifacts", {}),
        )

        # Resolve backend name from packet or default
        backend_name = context_packet.get("backend") or context_packet.get(
            "constraint_section", {}
        ).get("backend")

        # Run through AgentService
        _registry = PluginRegistry()
        _registry.initialize()
        service = AgentService(_registry)
        result = await service.run(packet, backend_name=backend_name)

        return {
            "status": result.status,
            "engagement_id": packet.engagement_id,
            "phase_name": packet.phase_name,
            "task_id": packet.task_id,
            "output_dir": result.output_dir,
            "artifacts": result.artifacts,
            "errors": result.errors,
            "metrics": result.metrics,
            "packet_valid": validated["valid"],
        }
    except ActivityError:
        raise
    except Exception as exc:
        raise ActivityError(f"Agent execution failed: {exc}") from exc


@activity.defn
async def collect_outputs(
    target_directory: str, required_files: List[str]
) -> dict:
    """Scan *target_directory* for files matching *required_files* globs.

    Returns a dict of ``{filename: content_or_size}``.  Missing files
    are omitted from the result (no error raised).
    """
    try:
        if not os.path.isdir(target_directory):
            return {}  # non-existent dir -> empty

        results: Dict[str, Any] = {}
        for pattern in required_files:
            # Support recursive ** globs
            full_pattern = os.path.join(target_directory, pattern)
            matches = sorted(_glob.glob(full_pattern, recursive=True))
            for match_path in matches:
                rel = os.path.relpath(match_path, target_directory)
                try:
                    with open(match_path, "rb") as fh:
                        content = fh.read()
                    # Store small files as content, large as size
                    if len(content) < 1024 * 1024:  # < 1 MiB
                        results[rel] = content.decode("utf-8", errors="replace")
                    else:
                        results[rel] = len(content)
                except OSError:
                    # File vanished between glob and open — skip gracefully
                    results[rel] = 0

        return results
    except Exception as exc:
        raise OutputCollectionError(
            f"Failed to collect outputs from {target_directory}: {exc}"
        ) from exc


@activity.defn
async def aggregate_phase_outputs(agent_outputs: List[dict]) -> dict:
    """Combine multiple agent outputs into a single phase artifact index.

    Returns a summary with file count, total size, and agents involved.
    """
    if not agent_outputs:
        return {
            "total_files": 0,
            "total_size_bytes": 0,
            "agents": 0,
            "agent_ids": [],
            "phases": [],
        }

    total_files = 0
    total_size = 0
    agent_ids: List[str] = []
    phases: List[str] = []

    for output in agent_outputs:
        aid = output.get("engagement_id", "unknown")
        if aid not in agent_ids:
            agent_ids.append(aid)

        phase = output.get("phase_name", "unknown")
        if phase not in phases:
            phases.append(phase)

        # Try to count files if the output contains files info
        outputs_map = output.get("outputs", {})
        if isinstance(outputs_map, dict):
            total_files += len(outputs_map)
            for _, v in outputs_map.items():
                if isinstance(v, int):
                    total_size += v
                elif isinstance(v, str):
                    total_size += len(v.encode("utf-8"))

    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "agents": len(agent_ids),
        "agent_ids": agent_ids,
        "phases": list(phases),
    }


@activity.defn
async def check_phase_coverage(coverage_target: float) -> dict:
    """Stub coverage check — returns pass/fail based on *coverage_target*.

    In Phase 4 this will run pytest-cov against the generated scaffold.
    For now always returns a fixed result set.
    """
    passed = coverage_target <= 95.0
    achieved = 95.0 if passed else 0.0

    return {
        "passed": passed,
        "coverage": achieved,
        "target": coverage_target,
        "findings": [],
    }


@activity.defn
async def snapshot_state(
    engagement_id: str,
    status: str,
    phase: str,
    project_path: str,
) -> dict:
    """Write a human-readable YAML snapshot to ``harness-state.yaml``.

    The snapshot is marked as HUMAN READABLE ONLY — NOT READ BY RUNTIME CODE.

    Returns a dict with the snapshot path and field values.
    """
    import yaml  # lazy import to keep sandbox happy

    if not os.path.isdir(project_path):
        raise SnapshotError(f"Project path does not exist: {project_path}")

    snapshot = {
        "format": "HUMAN READABLE ONLY — NOT READ BY RUNTIME CODE",
        "engagement_id": engagement_id,
        "status": status,
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    snapshot_path = os.path.join(project_path, "harness-state.yaml")
    try:
        with open(snapshot_path, "w") as fh:
            yaml.dump(snapshot, fh, default_flow_style=False, sort_keys=False)
    except OSError as exc:
        raise SnapshotError(
            f"Failed to write snapshot to {snapshot_path}: {exc}"
        ) from exc

    return {
        "snapshot_path": snapshot_path,
        "engagement_id": engagement_id,
        "status": status,
        "phase": phase,
        "timestamp": snapshot["timestamp"],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _agent_output_dir(engagement_id: str, phase_name: str, task_id: str) -> str:
    """Return the filesystem path for agent output artifacts."""
    return os.path.join(
        ".harness",
        "artifacts",
        engagement_id,
        phase_name,
        task_id,
    )


# Note: .harness dir name is a constant. If it ever changes, update here.
