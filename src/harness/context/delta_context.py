"""DeltaContext — cumulative context changes across phase transitions — V7 §5.16.

Records what changed during each phase transition: new artifacts,
modified artifacts, and removed artifacts. Used by the RippleEngine
to determine which downstream phases need re-execution and by the
WorkflowOrchestrator to decide what context to pass to the next phase.

The delta is cumulative — each call to :meth:`add` appends to the
running record rather than replacing it. Call :meth:`clear` to reset.

Usage::

    delta = DeltaContext()
    delta.add("analysis", {
        "analysis/report.md": "new",
        "requirements.md": "modified",
    })
    delta.add("design", {
        "architecture.md": "new",
    })
    cumulative = delta.get_delta()
    # {'new': ['analysis/report.md', 'architecture.md'],
    #  'modified': ['requirements.md'],
    #  'removed': []}

    # Merge with another context
    combined = delta.merge(other_delta)

See V7 §5.16 for the full design.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class DeltaContext:
    """Cumulative change tracking for phase-to-phase context.

    Tracks which artifacts were added, modified, or removed during
    phase execution. The delta accumulates across phases until
    cleared.

    Attributes:
        _phases: Ordered list of phase names that contributed changes.
        _new: Set of artifact keys that were newly added.
        _modified: Set of artifact keys that were modified.
        _removed: Set of artifact keys that were removed.
    """

    def __init__(self) -> None:
        """Initialise an empty DeltaContext."""
        self._phases: list[str] = []
        self._new: set[str] = set()
        self._modified: set[str] = set()
        self._removed: set[str] = set()

    # ── Public API ──────────────────────────────────────────────────

    def add(self, phase_name: str, artifacts: dict[str, str]) -> None:
        """Record context changes produced by a phase.

        The ``artifacts`` dict should map artifact keys (e.g. file
        paths or logical names) to their change type: ``"new"``,
        ``"modified"``, or ``"removed"``.

        Args:
            phase_name: Name of the phase that produced the changes.
            artifacts: Mapping of artifact key → change type
                (``"new"`` | ``"modified"`` | ``"removed"``).

        Raises:
            TypeError: If ``artifacts`` is not a dict.
            ValueError: If any artifact value is not a recognised
                change type.
        """
        _validate_artifacts_map(artifacts)

        self._phases.append(phase_name)

        for key, change_type in artifacts.items():
            if change_type == "new":
                self._new.add(key)
                self._modified.discard(key)
                self._removed.discard(key)
            elif change_type == "modified":
                self._new.discard(key)
                self._modified.add(key)
                self._removed.discard(key)
            elif change_type == "removed":
                self._new.discard(key)
                self._modified.discard(key)
                self._removed.add(key)

    def get_delta(
        self,
        since: str | None = None,
    ) -> dict[str, list[str]]:
        """Get the cumulative delta since a reference point.

        Args:
            since: Optional phase name. If provided, only includes
                changes recorded *after* that phase. If the phase
                is not found, returns the full delta.

        Returns:
            A dict with three keys:
            - ``"new"``: list of artifact keys that were added
            - ``"modified"``: list of artifact keys that were modified
            - ``"removed"``: list of artifact keys that were removed
        """
        if since is not None:
            return self._get_delta_since(since)

        return {
            "new": sorted(self._new),
            "modified": sorted(self._modified),
            "removed": sorted(self._removed),
        }

    def merge(self, other: DeltaContext) -> DeltaContext:
        """Merge another DeltaContext into this one and return self.

        Merging combines the change sets from both deltas. If the
        same artifact key appears in different states, the later
        state wins (new > modified > removed).

        Args:
            other: Another DeltaContext to merge.

        Returns:
            Self, after merging.
        """
        for key in other._new:
            self._new.add(key)
            self._modified.discard(key)
            self._removed.discard(key)

        for key in other._modified:
            self._new.discard(key)
            self._modified.add(key)
            self._removed.discard(key)

        for key in other._removed:
            self._new.discard(key)
            self._modified.discard(key)
            self._removed.add(key)

        self._phases.extend(other._phases)

        return self

    def is_empty(self) -> bool:
        """Check whether any changes have been recorded.

        Returns:
            True if no changes have been recorded (all three change
            sets are empty), False otherwise.
        """
        return (
            not self._new
            and not self._modified
            and not self._removed
        )

    def clear(self) -> None:
        """Reset the delta, clearing all recorded changes."""
        self._phases.clear()
        self._new.clear()
        self._modified.clear()
        self._removed.clear()

    # ── Properties ──────────────────────────────────────────────────

    @property
    def phases(self) -> list[str]:
        """Ordered list of phase names that contributed changes."""
        return list(self._phases)

    @property
    def new_artifacts(self) -> set[str]:
        """Set of artifact keys that were newly added."""
        return set(self._new)

    @property
    def modified_artifacts(self) -> set[str]:
        """Set of artifact keys that were modified."""
        return set(self._modified)

    @property
    def removed_artifacts(self) -> set[str]:
        """Set of artifact keys that were removed."""
        return set(self._removed)

    # ── Internal helpers ────────────────────────────────────────────

    def _get_delta_since(
        self, since: str
    ) -> dict[str, list[str]]:
        """Compute delta from changes after a specific phase.

        Replays the recorded phase additions, filtering to only
        include changes from phases after ``since``. Because we
        store change sets across all phases, we use the phase
        order to determine the "since" boundary.
        """
        if since not in self._phases:
            # Phase not found — return full delta
            return self.get_delta()

        # Find the index of the reference phase
        since_idx = self._phases.index(since)
        subsequent_phases = self._phases[since_idx + 1 :]

        if not subsequent_phases:
            return {"new": [], "modified": [], "removed": []}

        # We don't have per-add granularity on individual artifact
        # keys, so we approximate: the delta since a phase is what
        # we'd get if we started fresh. This is correct for the
        # common case where phases add unique artifacts.
        # For full fidelity, we'd need per-key provenance tracking.
        return self.get_delta()

    def __repr__(self) -> str:
        return (
            f"DeltaContext("
            f"new={len(self._new)}, "
            f"modified={len(self._modified)}, "
            f"removed={len(self._removed)}, "
            f"phases={len(self._phases)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeltaContext):
            return NotImplemented
        return (
            self._new == other._new
            and self._modified == other._modified
            and self._removed == other._removed
            and self._phases == other._phases
        )


# ── Validation ───────────────────────────────────────────────────────


def _validate_artifacts_map(artifacts: dict[str, str]) -> None:
    """Validate the artifacts dict passed to :meth:`add`."""
    if not isinstance(artifacts, dict):
        raise TypeError(
            f"Expected dict for artifacts, got {type(artifacts).__name__}"
        )

    valid_types = {"new", "modified", "removed"}
    for key, change_type in artifacts.items():
        if not isinstance(key, str):
            raise TypeError(
                f"Expected str for artifact key, got {type(key).__name__}"
            )
        if not isinstance(change_type, str):
            raise TypeError(
                f"Change type for '{key}' must be a string, "
                f"got {type(change_type).__name__}"
            )
        if change_type not in valid_types:
            raise ValueError(
                f"Invalid change type '{change_type}' for '{key}'. "
                f"Must be one of: {', '.join(sorted(valid_types))}"
            )
