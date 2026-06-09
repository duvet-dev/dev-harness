"""Wave model — provenance, type, state, and plan structure.

Each wave in a development plan carries metadata that tracks its origin,
purpose, and current state. This enables the harness to:
- Distinguish committed waves from in-progress or planned work
- Track adjustment/refactor waves with full provenance
- Measure rework patterns across engagements
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class WaveType(Enum):
    """The nature of a wave's work.

    - ``STANDARD``: A normal feature or implementation wave
    - ``ADJUSTMENT``: Fixes or changes to an already-committed wave
    - ``REFACTOR``: Structural rework without functional change
    """

    STANDARD = "standard"
    ADJUSTMENT = "adjustment"
    REFACTOR = "refactor"

    def __str__(self) -> str:
        return self.value


class WaveState(Enum):
    """Lifecycle state of a wave.

    - ``PLANNED``: Defined in the plan but not yet started
    - ``IN_PROGRESS``: Currently being worked on
    - ``COMMITTED``: Code merged, tests passing, closed to direct modification
    """

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"

    def __str__(self) -> str:
        return self.value


@dataclass
class WaveTask:
    """A single task within a wave."""

    id: str
    description: str

    def to_dict(self) -> dict:
        return {"id": self.id, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "WaveTask":
        return cls(id=d["id"], description=d["description"])


@dataclass
class WaveProvenance:
    """Provenance metadata for adjustment/refactor waves.

    Captures which discovery triggered the rework, so the harness
    can measure what causes the most rework across engagements.
    """

    trigger_phase: str
    """The phase that produced the discovery triggering this wave
    (e.g. ``"testing"``, ``"design"``, ``"implementation"``)."""

    trigger_reason: str
    """Free-text explanation of why this rework was needed."""

    original_wave_id: Optional[str] = None
    """The ID of the wave being adjusted or refactored, if any."""

    def to_dict(self) -> dict:
        d = {
            "trigger_phase": self.trigger_phase,
            "trigger_reason": self.trigger_reason,
        }
        if self.original_wave_id is not None:
            d["original_wave"] = self.original_wave_id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WaveProvenance":
        return cls(
            trigger_phase=d["trigger_phase"],
            trigger_reason=d["trigger_reason"],
            original_wave_id=d.get("original_wave"),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Wave:
    """A single development wave within a plan.

    Waves are self-contained units of work that include both
    implementation and testing. Each wave carries metadata
    for provenance tracking and state management.
    """

    id: str
    """Unique identifier within the plan (e.g. ``"wave-01"``)."""

    title: str
    """Human-readable title."""

    type: WaveType = WaveType.STANDARD
    state: WaveState = WaveState.PLANNED
    provenance: Optional[WaveProvenance] = None
    resolves: list[str] = field(default_factory=list)
    """Finding IDs (e.g. ``"F-001"``) that this wave resolves."""

    tasks: list[WaveTask] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    committed_at: Optional[str] = None

    def commit(self) -> None:
        """Mark this wave as committed."""
        self.state = WaveState.COMMITTED
        self.committed_at = _now_iso()

    def is_committed(self) -> bool:
        """True if this wave has been committed."""
        return self.state == WaveState.COMMITTED

    def is_modifiable(self) -> bool:
        """True if this wave can still be modified directly.

        Only uncommitted waves are freely modifiable.
        Committed waves need new adjustment/refactor waves.
        """
        return self.state in (WaveState.PLANNED, WaveState.IN_PROGRESS)

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "state": self.state.value,
            "created_at": self.created_at,
        }
        if self.provenance is not None:
            d["provenance"] = self.provenance.to_dict()
        if self.tasks:
            d["tasks"] = [t.to_dict() for t in self.tasks]
        if self.resolves:
            d["resolves"] = self.resolves
        if self.committed_at is not None:
            d["committed_at"] = self.committed_at
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Wave":
        provenance = None
        if "provenance" in d:
            provenance = WaveProvenance.from_dict(d["provenance"])

        tasks = [
            WaveTask.from_dict(t) for t in d.get("tasks", [])
        ]

        return cls(
            id=d["id"],
            title=d["title"],
            type=WaveType(d.get("type", "standard")),
            state=WaveState(d.get("state", "planned")),
            provenance=provenance,
            resolves=d.get("resolves", []),
            tasks=tasks,
            created_at=d.get("created_at", _now_iso()),
            committed_at=d.get("committed_at"),
        )


@dataclass
class Plan:
    """A development plan containing a sequence of waves.

    The plan sits at the centre of the engagement lifecycle:
    - Created during the planning phase
    - Consumed by the session loop for per-wave implementation+testing
    - Updated as adjustment/refactor waves are added
    - Provides input to the self-improvement loop
    """

    waves: list[Wave] = field(default_factory=list)
    """Ordered list of waves to execute."""

    priorities: dict[str, float] = field(default_factory=dict)
    """Project-level weighted priorities (0.0–1.0), e.g.
    ``{"security": 0.9, "simplicity": 0.6}``."""

    constraints: dict[str, str] = field(default_factory=dict)
    """Hard constraints, e.g.
    ``{"tech_stack": "python,postgresql"}``."""

    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def add_wave(self, wave: Wave) -> None:
        """Add a wave to the end of the plan."""
        self.waves.append(wave)
        self.updated_at = _now_iso()

    def get_wave(self, wave_id: str) -> Optional[Wave]:
        """Look up a wave by ID."""
        for w in self.waves:
            if w.id == wave_id:
                return w
        return None

    def count_by_type(self, wave_type: WaveType) -> int:
        """Count waves of a given type."""
        return sum(1 for w in self.waves if w.type == wave_type)

    def rework_count(self) -> int:
        """Count adjustment + refactor waves (rework)."""
        return self.count_by_type(WaveType.ADJUSTMENT) + self.count_by_type(
            WaveType.REFACTOR
        )

    def to_dict(self) -> dict:
        return {
            "waves": [w.to_dict() for w in self.waves],
            "priorities": self.priorities,
            "constraints": self.constraints,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        waves = [Wave.from_dict(w) for w in d.get("waves", [])]
        return cls(
            waves=waves,
            priorities=d.get("priorities", {}),
            constraints=d.get("constraints", {}),
            created_at=d.get("created_at", _now_iso()),
            updated_at=d.get("updated_at", _now_iso()),
        )
