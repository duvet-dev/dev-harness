"""Configuration validation service.

Provides ``ConfigValidator`` for validating providers.yaml and API key
resolution through injected interfaces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Protocol

from harness.domain.health import HealthCheck, _result
from harness.paths import get_providers_path


class YamlReader(Protocol):
    """Interface for reading and parsing YAML files."""

    def read(self, path: Path) -> Any: ...


class EnvProvider(Protocol):
    """Interface for resolving environment variables."""

    def get(self, name: str) -> Optional[str]: ...


class ConfigValidator:
    """Validator for harness configuration files and environment variables.

    Args:
        yaml_reader: An object with a ``read(path)`` method that returns
            parsed YAML content (e.g. a dict or None).
        env_provider: An object with a ``get(name)`` method that returns
            the environment variable value or ``None``.
    """

    def __init__(self, yaml_reader: YamlReader, env_provider: EnvProvider) -> None:
        self._yaml = yaml_reader
        self._env = env_provider

    def check_providers_yaml(self, root: Path) -> HealthCheck:
        """Verify ``providers.yaml`` exists, is valid YAML, and has providers."""
        providers_path = get_providers_path(root)
        if not providers_path.is_file():
            return _result(
                "providers-yaml", "fail",
                "``providers.yaml`` not found. The harness needs at least one LLM provider.",
                severity="CRITICAL",
                fix="Create .harness/providers.yaml with provider configuration",
            )

        try:
            data = self._yaml.read(providers_path)
        except Exception as exc:
            return _result(
                "providers-yaml", "fail",
                f"``providers.yaml`` is not valid YAML: {exc}",
                severity="CRITICAL",
                fix=f"Fix syntax errors in {providers_path}",
            )

        if not data or "providers" not in data or not data["providers"]:
            return _result(
                "providers-yaml", "fail",
                "``providers.yaml`` has no providers configured.",
                severity="CRITICAL",
                fix="Add at least one provider to .harness/providers.yaml",
            )

        provider_names = list(data["providers"].keys())
        return _result(
            "providers-yaml", "pass",
            f"``providers.yaml`` is valid with {len(provider_names)} provider(s): "
            f"{', '.join(provider_names)}",
        )

    def check_api_keys(self, root: Path) -> HealthCheck:
        """Verify all ``${VAR}`` references in providers.yaml resolve to env vars."""
        providers_path = get_providers_path(root)
        if not providers_path.is_file():
            return _result(
                "api-keys", "warn",
                "No providers.yaml — skipping API key check.",
            )

        try:
            data = self._yaml.read(providers_path)
        except Exception:
            return _result(
                "api-keys", "warn",
                "Cannot parse providers.yaml — skipping API key check.",
            )

        if not data or "providers" not in data:
            return _result("api-keys", "pass", "No providers configured — skip.")

        var_pattern = re.compile(r"\$\{(\w+)\}")
        missing: list[str] = []
        resolved_count = 0

        for provider_name, provider_config in data["providers"].items():
            if isinstance(provider_config, dict):
                api_key = provider_config.get("api_key", "")
                if isinstance(api_key, str):
                    matches = var_pattern.findall(api_key)
                    for var_name in matches:
                        if self._env.get(var_name) is None:
                            missing.append(var_name)
                        else:
                            resolved_count += 1

        if missing:
            unique_missing = sorted(set(missing))
            return _result(
                "api-keys", "fail",
                f"Environment variables not set: {', '.join(unique_missing)}. "
                f"API keys will fail to resolve.",
                severity="CRITICAL",
                fix=f"export {unique_missing[0]}=*** (or set in .env file)",
            )

        return _result(
            "api-keys", "pass",
            f"All {resolved_count} API key reference(s) resolve to environment variables.",
        )


__all__ = [
    "ConfigValidator",
    "YamlReader",
    "EnvProvider",
]
