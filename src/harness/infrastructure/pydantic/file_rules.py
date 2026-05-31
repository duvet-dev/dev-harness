"""Pydantic model for file rules in architecture configurations.

Provides typed models for file inclusion/exclusion rules used
in architecture and configuration validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileRule(BaseModel):
    """A single file inclusion/exclusion rule.

    Used in architecture configuration to specify which files
    should be scanned, ignored, or have specific treatment.
    """

    pattern: str = ""
    """Glob pattern matching file paths (e.g. '**/*.py')."""

    include: bool = True
    """If True, matching files are included; if False, excluded."""

    reason: str = ""
    """Why this rule exists (documentation purpose)."""

    category: str = ""
    """Optional categorisation label for grouping rules."""
