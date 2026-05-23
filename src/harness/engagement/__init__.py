"""Engagement lifecycle management.

Modules:

- ``resolver`` — Active engagement resolver (branch → slug detection)
- ``lifecycle`` — Engagement lifecycle operations (create, close, set-active)
"""

from harness.engagement.resolver import resolve_active_engagement
from harness.engagement.lifecycle import (
    create_engagement_dir,
    write_engagement_metadata,
    set_active_engagement,
    close_engagement,
    slugify,
)

__all__ = [
    "resolve_active_engagement",
    "create_engagement_dir",
    "write_engagement_metadata",
    "set_active_engagement",
    "close_engagement",
    "slugify",
]
