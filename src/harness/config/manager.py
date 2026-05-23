"""Harness configuration management.

Reads and resolves configuration from:
- Project-level config file
- Engagement-level override engagement.yaml
- Architecture goal file

Key setting: ``allow_refactoring_suggestions`` (bool, default ``True``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_config_path, get_engagement_dir


# ── Defaults ───────────────────────────────────────────────────────────────

_DEFAULT_ALLOW_REFACTORING = True


# ── Config manager ─────────────────────────────────────────────────────────


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
