"""Consolidated domain enums — all status and type enums used across the codebase.

This module replaces the scattered enum definitions that were previously
in ``command/values.py`` and various model files. It is the single source
of truth for domain-level enumerated types.

Design principle: All enums are ``str, Enum`` so they can be serialized
naturally to YAML/JSON and compared with plain strings when needed.
"""

from __future__ import annotations

from enum import Enum


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
    "BackendStatus",
    "StepStatus",
    "StepType",
    "FeedbackStatus",
    "Severity",
    "SnapshotStatus",
    "HealthSeverity",
    "ProjectType",
]
