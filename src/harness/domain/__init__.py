"""Domain package — core domain types, enums, and value objects.

Part of the DDD layering: domain layer contains business-logic types
that are independent of infrastructure concerns.
"""

from harness.domain.enums import (
    AbortMode,
    AutoMode,
    BackendStatus,
    BranchStrategy,
    FeedbackStatus,
    HealthSeverity,
    PhaseName,
    ReviewDecision,
    Severity,
    SessionType,
    SnapshotStatus,
    StepStatus,
    StepType,
)
from harness.domain.identifiers import (
    BackendName,
    EngagementId,
    PhaseId,
    Slug,
    TaskId,
    WaveId,
)

__all__ = [
    "AbortMode",
    "AutoMode",
    "BackendStatus",
    "BranchStrategy",
    "FeedbackStatus",
    "HealthSeverity",
    "PhaseName",
    "ReviewDecision",
    "Severity",
    "SessionType",
    "SnapshotStatus",
    "StepStatus",
    "StepType",
    # Identifiers
    "BackendName",
    "EngagementId",
    "PhaseId",
    "Slug",
    "TaskId",
    "WaveId",
]
