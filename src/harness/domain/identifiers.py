"""Typed domain identifiers using NewType.

All domain IDs are NewType-wrapped str or int values for type safety
at the boundary level. These prevent accidental mixing of ID types
between different domain concepts.

Usage::

    from harness.domain.identifiers import EngagementId, Slug

    def get_engagement(eid: EngagementId) -> Engagement: ...

    eid = EngagementId("eng-123")
    get_engagement(eid)  # OK
    get_engagement("eng-123")  # type error (but allowed at runtime)
"""

from __future__ import annotations

from typing import NewType


# ── Domain identifiers ─────────────────────────────────────────────

EngagementId = NewType("EngagementId", str)
"""Unique identifier for an engagement. Format: auto-incrementing int str."""

WaveId = NewType("WaveId", str)
"""Unique identifier for a wave within an engagement."""

TaskId = NewType("TaskId", str)
"""Unique identifier for a task within a phase/wave."""

PhaseId = NewType("PhaseId", str)
"""Unique identifier for a phase instance."""

BackendName = NewType("BackendName", str)
"""Backend name (e.g. 'api', 'cli', 'editor')."""

Slug = NewType("Slug", str)
"""Human-readable engagement identifier (URL-safe, unique per project)."""


# ── Helper: printable repr ─────────────────────────────────────────

def repr_id(value: str, prefix: str = "") -> str:
    """Human-readable representation of an ID."""
    return f"{prefix}{value}" if prefix else value
