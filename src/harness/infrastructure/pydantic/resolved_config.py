"""Pydantic model for resolved provider configuration.

Replaces raw ``dict[str, Any]`` for ``Invocation.resolved_config``
with a typed model that validates all provider configuration fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResolvedConfig(BaseModel):
    """Fully resolved provider configuration.

    Populated by the agent runner before invoking a backend.
    Contains resolved api_key, base_url, model, command, and any
    other provider-specific fields.

    Extra fields are allowed to support provider-specific config
    values that aren't part of the core schema.
    """

    model_config = {"extra": "allow"}  # Allow provider-specific extras

    api_key: str = ""
    """Resolved API key (environment variables already expanded)."""

    base_url: str = ""
    """Provider API base URL."""

    model: str = ""
    """Model identifier (e.g. 'deepseek-v4-pro', 'gpt-4o')."""

    provider: str = ""
    """Provider type (e.g. 'deepseek', 'openai', 'anthropic')."""

    command: str = ""
    """Shell command for CLI backends."""

    timeout_seconds: int = 600
    """Per-request timeout in seconds."""

    api_key_env: str = ""
    """Environment variable name for the API key (informational)."""

    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backwards compatibility."""
        return getattr(self, key, "")

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict-style .get() for backwards compatibility."""
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        """Support dict-style 'in' for backwards compatibility."""
        return hasattr(self, key) or key in self.model_fields_set

    def as_dict(self) -> dict[str, Any]:
        """Return as a plain dict for compatibility with dict consumers."""
        return self.model_dump()
