"""Value objects and enums for the typed command system.

All domain-level value types live here — not in ``domain/enums.py``.
Keeps value semantics close to the command/handler layer.

Design principle: All enums are ``str, Enum`` so they can be serialized
naturally to YAML/JSON and compared with plain strings when needed.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar


# ── PhaseName ──────────────────────────────────────────────────────


class PhaseName:
    """Validated phase identifier.

    Raises ValueError at construction if the phase name is not in the
    set of known phases.
    """

    VALID: ClassVar[frozenset[str]] = frozenset({
        "requirements",
        "design",
        "implementation",
        "testing",
        "review",
        "deployment",
        "assessment-triage",
        # v3 additions — workflow architecture corrections
        "analyse",
        "planning",
        "discover",
        "fix",
        "validate",
        "deliver",
        "assess",
        "audit",
        "report",
        "remediation-requirements",
        "architecture-design",
        "characterise",
        "refactor",
        "verify",
    })

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        if name not in self.VALID:
            raise ValueError(
                f"Invalid phase: {name!r}; valid: {sorted(self.VALID)}"
            )
        self._name = name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"PhaseName({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PhaseName):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)


# ── Engagement / Wave enums ────────────────────────────────────────


class EngStatus(str, Enum):
    """Simplified engagement lifecycle status.

    Used for engagement tracking in the command system.
    Distinct from the richer EngagementStatus in domain/engagement/model.py.
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class SessionType(str, Enum):
    """Session classification for engagement creation."""

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    REFACTORING = "refactoring"
    GET_WELL = "get-well"


class AutoMode(str, Enum):
    """Engagement creation automation mode."""

    AUTO = "auto"
    MANUAL = "manual"
    SUPERVISED = "supervised"


class ReviewDecision(str, Enum):
    """Gate review outcome."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REQUEST_CHANGES = "request_changes"


class AbortMode(str, Enum):
    """Abort strategy."""

    GRACEFUL = "graceful"
    HARD = "hard"


class BranchStrategy(str, Enum):
    """Branch rename behaviour."""

    KEEP = "keep"
    RENAME = "rename"
    DELETE = "delete"
    NEW = "new"


# ── WaveId value object ────────────────────────────────────────────


class WaveId:
    """Wave identifier value object.

    Fields:
        id: Machine-readable wave identifier string (e.g. ``"wave-01"``).
        title: Human-readable wave title.
    """

    __slots__ = ("_id", "_title")

    def __init__(self, id: str, title: str = "") -> None:
        self._id = id
        self._title = title

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    def __str__(self) -> str:
        return f"{self._id}: {self._title}" if self._title else self._id

    def __repr__(self) -> str:
        return f"WaveId({self._id!r}, {self._title!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WaveId):
            return self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)


__all__ = [
    "PhaseName",
    "EngStatus",
    "SessionType",
    "AutoMode",
    "ReviewDecision",
    "AbortMode",
    "BranchStrategy",
    "WaveId",
]
