"""Harness configuration management.

Reads and resolves configuration from:
- Project-level config file
- Engagement-level override engagement.yaml
- Settings YAML file
- Architecture goal file

Key setting: ``allow_refactoring_suggestions`` (bool, default ``True``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_config_path, get_engagement_dir, get_settings_path

# ── Defaults ───────────────────────────────────────────────────────────────

_DEFAULT_ALLOW_REFACTORING = True

# ── Settings dataclasses (V7 §7, Wave 8b) ──────────────────────────────────


@dataclass
class NLTranslatorSettings:
    """Settings for the NL Translator (V7 §5.21).

    Attributes:
        confidence_threshold: Minimum confidence for auto-dispatch
            (0.0–1.0, default 0.75).
    """

    confidence_threshold: float = 0.75


@dataclass
class WebSearchSettings:
    """Settings for web search providers (V7 §5.22).

    Attributes:
        provider: The active provider - "duckduckgo" or "searxng".
        searxng_url: Base URL for self-hosted SearXNG instance.
        max_results: Default maximum results per search.
        cache_ttl_seconds: Cache time-to-live in seconds.
    """

    provider: str = "duckduckgo"
    searxng_url: str = "http://localhost:8888"
    max_results: int = 5
    cache_ttl_seconds: int = 300


# ── Config manager ─────────────────────────────────────────────────────────


# ── Settings helpers ───────────────────────────────────────────────────────


def _load_settings_dict(root: Path) -> dict:
    """Lazy-load the settings.yaml file as a dict.

    Args:
        root: Project root directory.

    Returns:
        Parsed settings dict, or empty dict if file not found.
    """
    path = get_settings_path(root)
    if path.is_file():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_settings(root: Path) -> tuple[NLTranslatorSettings, WebSearchSettings]:
    """Load NL translator and web search settings from ``.harness/settings.yaml``.

    Args:
        root: Project root directory.

    Returns:
        A tuple of (NLTranslatorSettings, WebSearchSettings) with values
        merged from the settings file, or defaults if the file is missing.
    """
    raw = _load_settings_dict(root)

    # NL Translator settings
    nl_raw = raw.get("nl_translator", {})
    nl_settings = NLTranslatorSettings(
        confidence_threshold=float(
            nl_raw.get("confidence_threshold", NLTranslatorSettings.confidence_threshold)
        ),
    )

    # Web search settings
    ws_raw = raw.get("web_search", {})
    ws_settings = WebSearchSettings(
        provider=str(ws_raw.get("provider", WebSearchSettings.provider)),
        searxng_url=str(ws_raw.get("searxng_url", WebSearchSettings.searxng_url)),
        max_results=int(ws_raw.get("max_results", WebSearchSettings.max_results)),
        cache_ttl_seconds=int(ws_raw.get("cache_ttl_seconds", WebSearchSettings.cache_ttl_seconds)),
    )

    return nl_settings, ws_settings


class HarnessConfigManager:
    """Loads and resolves harness configuration.

    Usage::

        mgr = HarnessConfigManager(root)
        mgr.allow_refactoring_suggestions()           # project-level
        mgr.allow_refactoring_suggestions(slug)        # engagement-resolved
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._project_config: Optional[dict] = None
        self._project_config_path = get_config_path(root)

    # ── Project-level ──────────────────────────────────────────────────

    def _load_project_config(self) -> dict:
        """Lazy-load and cache the project-level config."""
        if self._project_config is not None:
            return self._project_config

        if self._project_config_path.is_file():
            with open(self._project_config_path) as f:
                self._project_config = yaml.safe_load(f) or {}
        else:
            self._project_config = {}

        return self._project_config

    # ── Refactoring suggestions ────────────────────────────────────────

    def allow_refactoring_suggestions(
        self, slug: Optional[str] = None
    ) -> bool:
        """Check if refactoring suggestions are allowed.

        Resolution order:
        1. Engagement-level override (if slug provided)
        2. Project-level config
        3. Default (True)

        Args:
            slug: Optional engagement slug for per-engagement check.

        Returns:
            True if refactoring suggestions are allowed.
        """
        # 1. Engagement-level override
        if slug is not None:
            eng_val = self._engagement_allow_refactoring(slug)
            if eng_val is not None:
                return eng_val

        # 2. Project-level config
        config = self._load_project_config()
        project_val = config.get("allow_refactoring_suggestions")
        if project_val is not None:
            return bool(project_val)

        # 3. Default
        return _DEFAULT_ALLOW_REFACTORING

    def _engagement_allow_refactoring(self, slug: str) -> Optional[bool]:
        """Check per-engagement override for refactoring suggestions."""
        eng_yaml = get_engagement_dir(self._root, slug) / "engagement.yaml"
        if not eng_yaml.is_file():
            return None

        with open(eng_yaml) as f:
            data = yaml.safe_load(f) or {}

        raw = data.get("allow_refactoring_suggestions")
        if raw is not None:
            return bool(raw)
        return None

    # ── Write helpers ──────────────────────────────────────────────────

    def set_project_allow_refactoring(self, value: bool) -> None:
        """Set ``allow_refactoring_suggestions`` in the project config."""
        config = self._load_project_config()
        config["allow_refactoring_suggestions"] = value

        self._project_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._project_config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def set_engagement_allow_refactoring(
        self, slug: str, value: bool
    ) -> None:
        """Set ``allow_refactoring_suggestions`` in an engagement's file."""
        eng_yaml = get_engagement_dir(self._root, slug) / "engagement.yaml"
        if eng_yaml.is_file():
            with open(eng_yaml) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        data["allow_refactoring_suggestions"] = value
        eng_yaml.parent.mkdir(parents=True, exist_ok=True)
        with open(eng_yaml, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# ── Module-level helpers ───────────────────────────────────────────────────


def allow_refactoring_suggestions(
    root: Path, slug: Optional[str] = None
) -> bool:
    """Module-level convenience for the refactoring suggestions check.

    Resolution order:
    1. Engagement-level override (if slug provided)
    2. Project-level config
    3. Default (True)

    Args:
        root: Project root directory.
        slug: Optional engagement slug for per-engagement check.

    Returns:
        True if refactoring suggestions are allowed.
    """
    return HarnessConfigManager(root).allow_refactoring_suggestions(slug)


def load_project_config(root: Path) -> dict:
    """Load the project-level config file.

    Returns empty dict if file doesn't exist.
    """
    path = get_config_path(root)
    if path.is_file():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def ensure_project_config(root: Path) -> None:
    """Create a project config file with defaults if one doesn't exist."""
    path = get_config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        with open(path, "w") as f:
            yaml.dump(
                {"allow_refactoring_suggestions": True},
                f,
                default_flow_style=False,
                sort_keys=False,
            )
