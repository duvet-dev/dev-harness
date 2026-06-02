"""Consolidated domain enums — all status and type enums used across the codebase.

This module replaces the scattered enum definitions that were previously
in ``command/values.py`` and various model files. It is the single source
of truth for domain-level enumerated types.

Design principle: All enums are ``str, Enum`` so they can be serialized
naturally to YAML/JSON and compared with plain strings when needed.
"""

from __future__ import annotations

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


# ── Session / Engagement enums ─────────────────────────────────────


from enum import Enum


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


# ── Backend execution enums ────────────────────────────────────────


class BackendStatus(str, Enum):
    """Execution status returned by agent backends."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class StepStatus(str, Enum):
    """Execution status for a single step."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class StepType(str, Enum):
    """Role/type of a step within a loop iteration."""

    PRODUCE = "produce"
    CRITIQUE = "critique"
    GATE = "gate"
    CONSULT = "consult"


# ── Feedback enums ─────────────────────────────────────────────────


class FeedbackStatus(str, Enum):
    """Lifecycle status of a feedback packet."""

    OPEN = "open"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


# ── Analysis / Finding enums ───────────────────────────────────────


class Severity(str, Enum):
    """Severity level for analysis findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SnapshotStatus(str, Enum):
    """Status values for engagement snapshots."""

    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class HealthSeverity(str, Enum):
    """Severity levels for health checks."""

    CRITICAL = "CRITICAL"
    BRANCH = "BRANCH"
    WARN = "WARN"
    INFO = "INFO"


class ProjectType(str, Enum):
    """Project archetype for architecture conformance checks."""

    PYTHON = "python"
    BACKEND_SERVICE = "backend-service"
    LIBRARY = "library"
    FRONTEND = "frontend"
    UNKNOWN = "unknown"


__all__ = [
    "PhaseName",
    "SessionType",
    "AutoMode",
    "ReviewDecision",
    "AbortMode",
    "BranchStrategy",
    "BackendStatus",
    "StepStatus",
    "StepType",
    "FeedbackStatus",
    "Severity",
    "SnapshotStatus",
    "HealthSeverity",
    "ProjectType",
]
