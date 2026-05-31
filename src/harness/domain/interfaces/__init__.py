"""Domain interfaces — protocol classes for boundary abstractions.

Defines the interface contracts (protocols) that infrastructure
implementations must satisfy. Following the DDD layering, domain
interfaces are owned by the domain layer, not the infrastructure layer.
"""

from harness.domain.interfaces.repositories import (
    EngagementRepository,
    PlanRepository,
    SnapshotRepository,
)

__all__ = [
    "EngagementRepository",
    "PlanRepository",
    "SnapshotRepository",
]
