"""YAML-based SnapshotRepository implementation.

Provides snapshot persistence using YAML files as the backing store.
Implements the SnapshotRepository protocol from domain/interfaces.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from harness.domain.identifiers import EngagementId
from harness.state.snapshot import SnapshotWriter, ProjectSnapshot


class YamlSnapshotRepository:
    """YAML-based snapshot persistence.

    Wraps the existing SnapshotWriter for typing consistency
    with the domain protocol.
    """

    def __init__(self) -> None:
        self._writer = SnapshotWriter()

    def write(self, snapshot: object, path: Path) -> None:
        """Write a ProjectSnapshot to a YAML file."""
        if isinstance(snapshot, ProjectSnapshot):
            self._writer.write(snapshot, path)

    def write_phase_checkpoint(
        self,
        engagement_id: EngagementId,
        phase: str,
        status: object,
        path: Path,
        retry_count: int = 0,
        has_stale_summary: bool = False,
    ) -> None:
        """Write or update a phase checkpoint snapshot."""
        from harness.state.snapshot import _load_or_create
        snapshot = _load_or_create(path)
        from harness.domain.enums import SnapshotStatus
        status_str = status.value if isinstance(status, SnapshotStatus) else str(status)
        self._writer.write_phase_checkpoint(
            engagement_id=str(engagement_id),
            phase=phase,
            status=status_str,
            path=path,
            retry_count=retry_count,
            has_stale_summary=has_stale_summary,
        )
