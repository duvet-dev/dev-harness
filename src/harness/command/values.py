"""Value objects for the typed command subsystem.

Provides typed, validated value objects used across command handlers.
Each value object enforces its constraints at construction time.
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


# ── Enums ──────────────────────────────────────────────────────────


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


class EngStatus(str, Enum):
    """Engagement lifecycle state."""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


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


__all__ = [
    "PhaseName",
    "SessionType",
    "AutoMode",
    "EngStatus",
    "ReviewDecision",
    "AbortMode",
    "BranchStrategy",
]
