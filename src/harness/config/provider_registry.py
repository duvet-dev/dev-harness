"""Provider registry — loads, merges, and resolves provider configurations.

Resolution order:
1. Project-level providers.yaml (env-var refs only, committed)
2. User-level providers.yaml (actual keys, never committed)
3. ``HARNESS_PROVIDERS_PATH`` env var can override the user config path

User config wins on conflicts (deep merge per provider).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from harness.paths import get_providers_path
from harness.config.provider_models import (
    ProviderConfig,
    ProviderConfigSet,
    ProviderError,
    provider_config_from_dict,
    resolve_env_ref,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_PROJECT_FILE_NAME = ".harness/providers.yaml"  # deprecated — use get_providers_path()
_USER_CONFIG_DIR = ".harness"
_USER_CONFIG_FILE_NAME = "providers.yaml"
_ENV_OVERRIDE = "HARNESS_PROVIDERS_PATH"


# ── Public API ───────────────────────────────────────────────────────────────


def load_providers(
    project_dir: Path,
    user_config_path: Path | None = None,
    *,
    resolve_env: bool = True,
) -> ProviderConfigSet:
    """Load, merge, and optionally resolve provider configurations.

    Loads providers.yaml from the project root, then merges the user-level
    config on top. User config wins on conflicts.

    The ``HARNESS_PROVIDERS_PATH`` env var overrides the default user
    config path.

    Args:
        project_dir: Path to the project root directory.
        user_config_path: Explicit path to user config. If ``None``,
            resolves from ``HARNESS_PROVIDERS_PATH`` env var or defaults
            to the user config directory.
        resolve_env: If ``True``, resolve ``${VAR}`` references in all
            config values (default). Set to ``False`` to keep references
            unresolved.

    Returns:
        A :class:`ProviderConfigSet` containing the merged configuration.

    Raises:
        ProviderError: If the merged config is invalid.
    """
    project_config = _load_yaml_config(get_providers_path(project_dir))
    user_config = _load_user_config(user_config_path)

    merged = merge_providers(
        _extract_providers(project_config),
        _extract_providers(user_config),
    )

    configs: dict[str, ProviderConfig] = {}
    for name, data in merged.items():
        configs[name] = provider_config_from_dict(name, data)

    result = ProviderConfigSet(providers=configs)

    errors = result.validate()
    if errors:
        raise ProviderError(
            "Provider configuration is invalid:\n  - "
            + "\n  - ".join(errors)
        )

    # Eagerly resolve env-var refs to catch missing vars early
    if resolve_env:
        for name, provider in result.providers.items():
            try:
                provider.to_resolved_dict()
            except ProviderError as exc:
                raise ProviderError(
                    f"Provider '{name}': {exc}"
                ) from exc

    return result


def merge_providers(
    base: dict[str, dict[str, Any]],
    override: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Deep-merge two provider dicts. ``override`` wins on conflicts.

    Per-provider merge: for each provider in ``override``, its fields are
    merged on top of the same provider in ``base``. Providers only in
    ``base`` are preserved. Providers only in ``override`` are added.

    Args:
        base: Base provider dict (e.g. from project config).
        override: Override provider dict (e.g. from user config).

    Returns:
        A new merged dict of provider name → provider config dict.
    """
    result = {}

    # Copy all base providers first
    for name, config in base.items():
        result[name] = dict(config)

    # Merge override on top
    for name, config in override.items():
        if name in result:
            existing = result[name]
            merged = dict(existing)
            merged.update(config)
            result[name] = merged
        else:
            result[name] = dict(config)

    return result


def resolve_env_refs_in_config(
    data: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Recursively resolve ``${VAR}`` references in all string values.

    Args:
        data: A nested dict of provider configurations.

    Returns:
        A new dict with all env-var references resolved.
    """
    result: dict[str, dict[str, Any]] = {}
    for name, config in data.items():
        result[name] = _resolve_config_values(config)
    return result


# ── Internal helpers ─────────────────────────────────────────────────────────


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict if it doesn't exist.

    Only the ``providers`` key from the root dict is returned. If the
    file exists but has no ``providers`` key, an empty dict is returned.
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ProviderError(
            f"Failed to parse provider config '{path}': {exc}"
        ) from exc

    providers = raw.get("providers", {})
    if not isinstance(providers, dict):
        raise ProviderError(
            f"'providers' key in '{path}' must be a mapping"
        )
    return providers


def _load_user_config(user_config_path: Path | None) -> dict[str, dict[str, Any]]:
    """Load the user-level provider config.

    Resolution order:
    1. ``user_config_path`` parameter (if provided)
    2. ``HARNESS_PROVIDERS_PATH`` env var (if set)
    3. Default user config directory
    """
    if user_config_path is not None:
        return _load_yaml_config(user_config_path)

    env_path = os.environ.get(_ENV_OVERRIDE)
    if env_path:
        return _load_yaml_config(Path(env_path))

    default_path = Path.home() / _USER_CONFIG_DIR / _USER_CONFIG_FILE_NAME
    return _load_yaml_config(default_path)


# ── Extraction helpers ─────────────────────────────────────────────────────


def _extract_providers(
    raw: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract provider entries, skipping invalid entries.

    Expects ``raw`` to be a dict of provider name → provider config dict
    (i.e. already extracted from the YAML file's ``providers`` key).
    """
    providers: dict[str, dict[str, Any]] = {}
    for name, config in raw.items():
        if not isinstance(config, dict):
            logger.warning(
                "Skipping provider '%s': config must be a mapping", name
            )
            continue
        providers[name] = config
    return providers


def _resolve_config_values(
    config: dict[str, Any],
    depth: int = 0,
) -> dict[str, Any]:
    """Recursively resolve ``${VAR}`` references in config values."""
    if depth > 10:
        return config

    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            result[key] = resolve_env_ref(value)
        elif isinstance(value, dict):
            result[key] = _resolve_config_values(value, depth + 1)
        elif isinstance(value, list):
            result[key] = [
                (
                    resolve_env_ref(item)
                    if isinstance(item, str)
                    else _resolve_config_values(item, depth + 1)
                    if isinstance(item, dict)
                    else item
                )
                for item in value
            ]
        else:
            result[key] = value
    return result
