"""Engagement lifecycle management.

Modules:

- ``resolver`` — Active engagement resolver (branch → slug detection)
- ``lifecycle`` — Engagement lifecycle operations (create, close, set-active)
- ``repository`` — EngagementRepository (file-based persistence)
- ``health`` — EngagementHealthCheck (health checks for engagements)
- ``startup`` — StartupResumeFlow (engagement creation, resumption, auto mode)
"""

from harness.domain.engagement.health import EngagementHealthCheck, HealthReport, check_engagement_health
from harness.domain.engagement.lifecycle import (
    close_engagement,
    create_engagement_dir,
    set_active_engagement,
    slugify,
    write_engagement_metadata,
)
from harness.domain.engagement.repository import EngagementRepository
from harness.domain.engagement.resolver import resolve_active_engagement
from harness.domain.engagement.startup import (
    StartupResumeFlow,
    StartupResult,
    create_engagement,
    load_engagement,
    resume_engagement,
)

__all__ = [
    "EngagementHealthCheck",
    "HealthReport",
    "check_engagement_health",
    "EngagementRepository",
    "resolve_active_engagement",
    "create_engagement_dir",
    "write_engagement_metadata",
    "set_active_engagement",
    "close_engagement",
    "slugify",
    "StartupResumeFlow",
    "StartupResult",
    "create_engagement",
    "resume_engagement",
    "load_engagement",
]
