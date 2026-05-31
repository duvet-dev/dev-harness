"""Snapshot — write-only state snapshots for human consumption (architecture §2.2).

Never read by runtime code. These are write-only management artifacts.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml

from harness.domain.enums import SnapshotStatus


@dataclass
class EngagementSnapshot:
    """Immutable record of a single engagement's state at snapshot time."""

    id: str
    description: str
    status: SnapshotStatus = SnapshotStatus.PLANNING  # planning|in_progress|complete|blocked
    gate_mode: str = "auto"  # wild|auto|full
    phase: str = ""
    retry_count: int = 0
    has_stale_summary: bool = False


@dataclass
class ProjectSnapshot:
    """Top-level snapshot encompassing all engagements for a project."""

    project_name: str
    version: str
    current_engagement: Optional[str]
    engagements: List[EngagementSnapshot]
    last_updated: str = ""  # ISO-8601 timestamp, set on write

    def __post_init__(self) -> None:
        if not self.last_updated:
            self.last_updated = datetime.now(timezone.utc).isoformat()


def _engagement_to_dict(e: EngagementSnapshot) -> dict:
    return {
        "id": e.id,
        "description": e.description,
        "status": e.status,
        "gate_mode": e.gate_mode,
        "phase": e.phase,
        "retry_count": e.retry_count,
        "has_stale_summary": e.has_stale_summary,
    }


def _project_to_dict(snapshot: ProjectSnapshot) -> dict:
    return {
        "project_name": snapshot.project_name,
        "version": snapshot.version,
        "current_engagement": snapshot.current_engagement,
        "engagements": [_engagement_to_dict(e) for e in snapshot.engagements],
        "last_updated": snapshot.last_updated,
    }


class SnapshotWriter:
    """Writes human-readable snapshots to YAML files.

    These files are intended for human/monitoring consumption only.
    Runtime code MUST NOT read them (architecture §2.2).
    """

    @staticmethod
    def write(snapshot: ProjectSnapshot, path: Path) -> None:
        """Write a complete ProjectSnapshot to a YAML file."""
        data = _project_to_dict(snapshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def write_phase_checkpoint(
        engagement_id: str,
        phase: str,
        status: str,
        path: Path,
        retry_count: int = 0,
        has_stale_summary: bool = False,
    ) -> None:
        """Write or update a phase checkpoint for a single engagement.

        Loads the existing snapshot at *path* (if any), locates the
        engagement by *engagement_id*, updates its phase/status/retry_count,
        and writes the full snapshot back.
        """
        snapshot = _load_or_create(path)
        for eng in snapshot.engagements:
            if eng.id == engagement_id:
                eng.phase = phase
                eng.status = status
                eng.retry_count = retry_count
                eng.has_stale_summary = has_stale_summary
                break
        else:
            snapshot.engagements.append(
                EngagementSnapshot(
                    id=engagement_id,
                    description="(checkpoint auto-created)",
                    status=status,
                    gate_mode="auto",
                    phase=phase,
                    retry_count=retry_count,
                    has_stale_summary=has_stale_summary,
                )
            )
        snapshot.last_updated = datetime.now(timezone.utc).isoformat()
        SnapshotWriter.write(snapshot, path)


def _load_or_create(path: Path) -> ProjectSnapshot:
    """Load a ProjectSnapshot from *path*, or return a blank default."""
    if path.is_file():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        engagements = [
            EngagementSnapshot(**e) for e in raw.get("engagements", [])
        ]
        return ProjectSnapshot(
            project_name=raw.get("project_name", "unknown"),
            version=raw.get("version", "0.0.0"),
            current_engagement=raw.get("current_engagement"),
            engagements=engagements,
            last_updated=raw.get("last_updated", ""),
        )
    return ProjectSnapshot(
        project_name="unknown",
        version="0.0.0",
        current_engagement=None,
        engagements=[],
    )
