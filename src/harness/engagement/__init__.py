"""Engagement lifecycle management.

Modules:

- ``resolver`` — Active engagement resolver (branch → slug detection)
- ``lifecycle`` — Engagement lifecycle operations (create, close, set-active)
"""

from harness.engagement.lifecycle import (
    close_engagement,
    create_engagement_dir,
    set_active_engagement,
    slugify,
    write_engagement_metadata,
)
from harness.engagement.resolver import resolve_active_engagement

__all__ = [
    "resolve_active_engagement",
    "create_engagement_dir",
    "write_engagement_metadata",
    "set_active_engagement",
    "close_engagement",
    "slugify",
]
