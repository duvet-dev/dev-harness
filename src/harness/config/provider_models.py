"""Data models for provider/backend configuration.

Pure dataclasses with no external dependencies. Supports env-var reference
notation (``${VAR_NAME}``) which is resolved at runtime.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """Raised when provider configuration fails to load or resolve."""


_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_env_ref(value: str) -> str:
    """Resolve ``${VAR_NAME}`` references to actual environment variables.

    Args:
        value: A string that may contain ``${VAR_NAME}`` references.

    Returns:
        The string with all references resolved. Missing vars raise
        :class:`ProviderError`.

    Example:
        >>> resolve_env_ref("${DEEPSEEK_API_KEY}")
        'sk-actual-key...'
        >>> resolve_env_ref("prefix-${VAR}-suffix")
        'prefix-value-suffix'
    """
    def _replacer(m: re.Match) -> str:
        var_name = m.group(1)
        resolved = os.environ.get(var_name)
        if resolved is None:
            raise ProviderError(
                f"Environment variable '{var_name}' is not set "
                f"(referenced as ${{{var_name}}})"
            )
        return resolved

    return _ENV_REF_PATTERN.sub(_replacer, value)


def has_env_ref(value: str) -> bool:
    """Return ``True`` if the string contains any ``${VAR}`` references."""
    return bool(_ENV_REF_PATTERN.search(value))


def resolve_value(value: str) -> str:
    """Resolve a config field if it contains env-var refs, or return as-is."""
    if has_env_ref(value):
        return resolve_env_ref(value)
    return value


@dataclass
class ModelEntry:
    """A single model key → model name mapping within a provider."""

    key: str
    model: str


@dataclass
class ProviderConfig:
    """Configuration for a single provider (LLM API or CLI tool).

    The ``api_key``, ``base_url``, and ``command`` fields all support
    ``${ENV_VAR_NAME}`` references that are resolved at runtime.
    """

    name: str
    """Unique provider name (e.g. ``deepseek``, ``openai``, ``claude-code``)."""

    type: str = "openai-compatible"
    """One of: ``openai-compatible``, ``openai``, ``anthropic``, ``cli``, ``ide``."""

    api_key: str = ""
    """API key or ``${ENV_VAR_NAME}`` reference. Empty string = no auth."""

    base_url: str = ""
    """Base URL for API providers. Required for ``openai-compatible`` type."""

    models: list[dict[str, Any]] = field(default_factory=list)
    """Map of model keys to model names (e.g. ``default`` → ``gpt-4o``)."""

    command: str = ""
    """Shell command for ``cli`` type providers (e.g. ``claude``, ``aider``)."""

    description: str = ""
    """Human-readable description of this provider."""

    # ── resolved helpers ─────────────────────────────────────

    def resolve_api_key(self) -> str:
        """Resolve the api_key, expanding any env-var reference."""
        return resolve_value(self.api_key) if self.api_key else ""

    def resolve_base_url(self) -> str:
        """Resolve the base_url, expanding any env-var reference."""
        return resolve_value(self.base_url) if self.base_url else ""

    def resolve_command(self) -> str:
        """Resolve the command, expanding any env-var reference."""
        return resolve_value(self.command) if self.command else ""

    def resolve_model(self, model_key: str) -> str:
        """Resolve a model key to an actual model name.

        Args:
            model_key: A key in the ``models`` dict (e.g. ``default``, ``pro``).

        Returns:
            The resolved model name string.

        Raises:
            ProviderError: If the model key is not found.
        """
        # Models can be a name→alias dict or a list of model objects
        if isinstance(self.models, dict):
            if model_key in self.models:
                return self.models[model_key]
            if self.models:
                raise ProviderError(
                    f"Model key '{model_key}' not found in provider '{self.name}'. "
                    f"Available keys: {', '.join(self.models) or '(none)'}"
                )
        elif isinstance(self.models, list):
            names = [m.get("name", "") for m in self.models if isinstance(m, dict)]
            if model_key in names:
                return model_key
            if names:
                # Try using the key directly as a model name
                pass
        return model_key

    def validate(self) -> list[str]:
        """Validate this provider config, returning a list of error strings.

        Empty list means valid.
        """
        errors: list[str] = []

        valid_types = {"openai-compatible", "openai", "anthropic", "cli", "ide"}
        if self.type not in valid_types:
            errors.append(
                f"Invalid provider type '{self.type}' for '{self.name}'. "
                f"Must be one of: {', '.join(sorted(valid_types))}"
            )

        if self.type in ("openai-compatible", "openai", "anthropic"):
            if self.type == "openai-compatible" and not self.base_url:
                errors.append(
                    f"Provider '{self.name}' has type 'openai-compatible' "
                    f"but no base_url set"
                )

        if self.type == "cli" and not self.command:
            errors.append(
                f"Provider '{self.name}' has type 'cli' but no command set"
            )

        return errors

    def to_resolved_dict(self) -> dict[str, Any]:
        """Return a fully resolved dict suitable for backend instantiation.

        All ``${VAR}`` references are expanded.
        """
        return {
            "name": self.name,
            "type": self.type,
            "api_key": self.resolve_api_key(),
            "base_url": self.resolve_base_url(),
            "models": (
                dict(self.models) if isinstance(self.models, dict)
                else self.models
            ),
            "command": self.resolve_command(),
            "description": self.description,
        }


@dataclass
class ProviderConfigSet:
    """A named collection of provider configurations.

    Provides convenient lookup and model resolution.
    """

    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    def resolve_model(self, name: str, model_key: str) -> str:
        """Resolve a provider name + model key to an actual model string.

        Args:
            name: Provider name (e.g. ``deepseek``).
            model_key: Model key within that provider (e.g. ``default``).

        Returns:
            The resolved model name string.

        Raises:
            ProviderError: If the provider or model key is not found.
        """
        provider = self.get(name)
        if provider is None:
            raise ProviderError(
                f"Provider '{name}' not found. "
                f"Available: {', '.join(sorted(self.providers))}"
            )
        return provider.resolve_model(model_key)

    def get(self, name: str) -> ProviderConfig | None:
        """Look up a provider by name."""
        return self.providers.get(name)

    def get_resolved(self, name: str) -> dict[str, Any] | None:
        """Look up a provider and return its fully resolved config dict.

        Returns ``None`` if the provider is not found.
        """
        provider = self.get(name)
        if provider is None:
            return None
        return provider.to_resolved_dict()

    def has(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self.providers

    def validate(self) -> list[str]:
        """Validate all providers, returning accumulated errors."""
        errors: list[str] = []
        for provider in self.providers.values():
            errors.extend(provider.validate())
        return errors


def provider_config_from_dict(
    name: str, data: dict[str, Any]
) -> ProviderConfig:
    """Build a :class:`ProviderConfig` from a plain dict (e.g. from YAML).

    Args:
        name: The provider name (key in the ``providers`` map).
        data: The provider config dict from YAML.

    Returns:
        A new :class:`ProviderConfig`.
    """
    return ProviderConfig(
        name=name,
        type=data.get("type", "openai-compatible"),
        api_key=data.get("api_key", ""),
        base_url=data.get("base_url", ""),
        models=data.get("models", {}),
        command=data.get("command", ""),
        description=data.get("description", ""),
    )
