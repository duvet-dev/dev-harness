"""Domain events — base classes and event infrastructure.

Supports the DDD domain events pattern: aggregates publish events
when state changes, and event handlers react to those events.
"""

from harness.domain.events.event_bus import EventBus, EventHandler
from harness.domain.events.engagement_events import (
    EngagementAborted,
    EngagementCompleted,
    EngagementCreated,
    EngagementStarted,
    EngagementStatusChanged,
    PhaseTransitioned,
    WaveCommitted,
)

__all__ = [
    "EventBus",
    "EventHandler",
    "EngagementAborted",
    "EngagementCompleted",
    "EngagementCreated",
    "EngagementStarted",
    "EngagementStatusChanged",
    "PhaseTransitioned",
    "WaveCommitted",
]
