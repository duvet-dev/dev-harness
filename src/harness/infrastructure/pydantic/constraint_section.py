"""Pydantic model for agent constraint sections.

Provides a typed model for the constraint_section dictionary that
flows through ContextPacket and Invocation objects.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ConstraintSection(BaseModel):
    """Agent execution constraints and overrides.

    This model replaces the raw ``dict[str, Any]`` for constraint
    sections throughout the codebase. It provides typed access to
    all constraint fields including ``backend``, ``model``, ``agent_role``,
    ``temperature``, ``max_tokens``, ``available_tools``, and ``budget``.

    The ``get()`` and ``__getitem__`` methods remain for backward
    compatibility with dict-style access patterns.
    """

    backend: str = ""
    """Backend/API name override (e.g. 'api', 'cli')."""

    model: str = ""
    """Model override (e.g. 'deepseek-v4-pro', 'gpt-4o')."""

    agent_role: str = ""
    """Agent role override."""

    temperature: Optional[float] = None
    """Sampling temperature override (0.0–2.0)."""

    max_tokens: Optional[int] = None
    """Maximum tokens in the response."""

    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    """Tool definitions for LLM function-calling."""

    budget: dict[str, Any] = Field(default_factory=dict)
    """Budget constraints for execution."""

    fallbacks: list[Any] = Field(default_factory=list)
    """Fallback backend configurations."""

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict-style .get() for backwards compatibility."""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return default

    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backwards compatibility."""
        val = self.get(key)
        if val is None and key not in self.model_fields_set:
            raise KeyError(key)
        return val
