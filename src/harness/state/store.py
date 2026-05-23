"""Store — Phase 1 in-memory engagement store (pre-Temporal placeholder).

Will be replaced by Temporal workflow state in Phase 2.
"""

from typing import Dict, Optional

from harness.state.snapshot import EngagementSnapshot


class Phase1StateStore:
    """In-memory engagement store for Phase 1 (pre-Temporal).

    Provides lightweight CRUD for engagement snapshots.  Not thread-safe.
    """

    def __init__(self) -> None:
        self._engagements: Dict[str, EngagementSnapshot] = {}
        self._current_id: Optional[str] = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_engagement(
        self,
        description: str,
        gate_mode: str = "auto",
    ) -> EngagementSnapshot:
        """Create a new engagement and set it as the current one."""
        eng = EngagementSnapshot(
            id=_next_id(self._engagements),
            description=description,
            status="planning",
            gate_mode=gate_mode,
            phase="1",
        )
        self._engagements[eng.id] = eng
        self._current_id = eng.id
        return eng

    def get_engagement(self, id: str) -> Optional[EngagementSnapshot]:
        """Retrieve an engagement by id, or None."""
        return self._engagements.get(id)

    def update_status(self, id: str, status: str) -> None:
        """Update the status of an existing engagement.

        Raises KeyError if *id* does not exist.
        """
        if id not in self._engagements:
            raise KeyError(f"Engagement {id!r} not found")
        old = self._engagements[id]
        self._engagements[id] = EngagementSnapshot(
            id=old.id,
            description=old.description,
            status=status,
            gate_mode=old.gate_mode,
            phase=old.phase,
            retry_count=old.retry_count,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def current(self) -> Optional[EngagementSnapshot]:
        """Return the current (latest) engagement, or None."""
        if self._current_id is None:
            return None
        return self._engagements.get(self._current_id)

    def all(self) -> list:
        """Return all engagements (insertion-order)."""
        return list(self._engagements.values())


def _next_id(existing: Dict[str, object]) -> str:
    """Generate the next monotonic engagement id."""
    return f"eng-{len(existing) + 1}"
