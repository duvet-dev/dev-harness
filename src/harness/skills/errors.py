"""Skill-specific error types — V7 §8.

WebSearchUnavailableError is defined in harness.errors for the shared
error hierarchy. This module provides skill-specific errors beyond
the core hierarchy.
"""

from __future__ import annotations

from harness.errors import HarnessError, UnknownSkillError, WebSearchUnavailableError


class SkillExecutionError(HarnessError):
    """A skill failed during execution (not registration/lookup)."""


__all__ = [
    "SkillExecutionError",
    "UnknownSkillError",
    "WebSearchUnavailableError",
]
