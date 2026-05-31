"""Repository protocol interfaces for domain persistence.

Defines the contracts that all repository implementations must satisfy,
allowing the domain layer to remain agnostic of the storage technology.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol

from harness.domain.identifiers import EngagementId, Slug, WaveId


class EngagementRepository(Protocol):
    """Repository for engagement persistence.

    Implementations handle YAML/JSON serialization to the filesystem
    or an alternative storage backend.
    """

    def save(self, engagement: object) -> None:
        """Persist an engagement aggregate."""

    def get(self, slug: Slug) -> Optional[object]:
        """Retrieve an engagement by slug. Returns None if not found."""

    def exists(self, slug: Slug) -> bool:
        """Check if an engagement exists."""

    def delete(self, slug: Slug) -> None:
        """Delete an engagement by slug."""

    def list_all(self) -> list[object]:
        """List all engagements."""

    def update_status(self, slug: Slug, status: object) -> object:
        """Update engagement status and return the updated engagement."""


class PlanRepository(Protocol):
    """Repository for plan persistence."""

    def save(self, plan: object) -> None:
        """Persist a plan."""

    def get(self, engagement_slug: str, root: Path) -> Optional[object]:
        """Retrieve a plan by engagement slug."""

    def commit_wave(self, wave_id: WaveId) -> bool:
        """Mark a wave as committed."""

    def set_wave_state(self, wave_id: WaveId, state: str) -> bool:
        """Update wave state."""


class SnapshotRepository(Protocol):
    """Repository for snapshot persistence."""

    def write(self, snapshot: object, path: Path) -> None:
        """Write a snapshot to a file."""

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


class YamlReader(Protocol):
    """Interface for reading and parsing YAML files."""

    def read(self, path: Path) -> Any: ...


class EnvProvider(Protocol):
    """Interface for reading environment variables."""

    def get(self, name: str) -> Optional[str]: ...
