"""Governance level configuration — project and per-engagement.

Governance controls which agents are active and at what depth:

* ``exploration`` — lead agent only, minimal guidelines
* ``standard`` — lead + sub-agents matched by project type, full guidelines
* ``strict`` — all sub-agents + extra reviewers, maximum depth

Governance is configured at the project level in the project config file
and is overridable at the engagement level.

Wave 17 — Phase 4 (Governance Levels).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from harness.agents.fleet import GovernanceLevel
from harness.paths import get_config_path, get_engagement_dir

# ── Config helpers ────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict:
    """Safely load a YAML file, returning empty dict on failure or absence."""
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Governance Resolver
# ---------------------------------------------------------------------------


def get_project_governance(
    root: Path,
    default: GovernanceLevel = GovernanceLevel.STANDARD,
) -> GovernanceLevel:
    """Read the project-level governance from the project config file.

    The configuration key is ``governance.level``.

    Args:
        root: Project root directory.
        default: Fallback level if not configured.

    Returns:
        The configured or default governance level.
    """
    config = _load_yaml(get_config_path(root))
    gov = config.get("governance", {})
    if isinstance(gov, str):
        return _parse_level(gov, default)
    level_str = gov.get("level") if isinstance(gov, dict) else None
    if level_str is None:
        return default
    return _parse_level(level_str, default)


def set_project_governance(root: Path, level: GovernanceLevel) -> None:
    """Write the governance level to the project config file.

    Preserves other existing config keys.
    """
    config_path = get_config_path(root)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = _load_yaml(config_path)
    config.setdefault("governance", {})
    if isinstance(config["governance"], str):
        config["governance"] = {"level": config["governance"]}
    config["governance"]["level"] = level.value

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_engagement_governance(
    root: Path,
    slug: str,
    default: Optional[GovernanceLevel] = None,
) -> GovernanceLevel:
    """Read the engagement-level governance from engagement.yaml.

    Falls back to the project-level governance if not specified in the
    engagement configuration.

    Args:
        root: Project root directory.
        slug: Engagement slug (directory name).
        default: Fallback if not set at either level. If ``None``,
            defaults to the project-level governance.

    Returns:
        The effective governance level for this engagement.
    """
    if default is None:
        project_level = get_project_governance(root)
    else:
        project_level = default

    eng_config_path = get_engagement_dir(root, slug) / "engagement.yaml"
    eng_config = _load_yaml(eng_config_path)
    gov = eng_config.get("governance", {})
    if isinstance(gov, str):
        return _parse_level(gov, project_level)
    level_str = gov.get("level") if isinstance(gov, dict) else None
    if level_str is not None:
        return _parse_level(level_str, project_level)
    return project_level


def set_engagement_governance(
    root: Path, slug: str, level: GovernanceLevel
) -> None:
    """Write the governance level to an engagement's engagement.yaml.

    Preserves other existing engagement config keys.
    """
    path = get_engagement_dir(root, slug) / "engagement.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    config = _load_yaml(path)
    config.setdefault("governance", {})
    if isinstance(config["governance"], str):
        config["governance"] = {"level": config["governance"]}
    config["governance"]["level"] = level.value

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Active agent resolution
# ---------------------------------------------------------------------------


def get_active_agents_for_project(
    root: Path,
    fleet_name: str,
    project_type: str | None = None,
) -> list[str]:
    """Return active agents for a fleet at the project governance level.

    Convenience wrapper: reads governance from config, resolves active
    agents from the fleet registry.

    Args:
        root: Project root directory.
        fleet_name: Name of the fleet.
        project_type: Optional project type for filtering (e.g.
            ``"ddd-backend"``).

    Returns:
        List of active agent role strings.
    """
    from harness.agents.fleet_registry import FleetRegistry

    level = get_project_governance(root)
    registry = FleetRegistry(root)
    fleet = registry.get_fleet(fleet_name)
    if fleet is None:
        return []
    return fleet.get_active_agents(governance=level, project_type=project_type)


def get_active_agents_for_engagement(
    root: Path,
    fleet_name: str,
    slug: str,
    project_type: str | None = None,
) -> list[str]:
    """Return active agents for a fleet at the engagement governance level.

    Args:
        root: Project root directory.
        fleet_name: Name of the fleet.
        slug: Engagement slug.
        project_type: Optional project type for filtering.

    Returns:
        List of active agent role strings.
    """
    from harness.agents.fleet_registry import FleetRegistry

    level = get_engagement_governance(root, slug)
    registry = FleetRegistry(root)
    fleet = registry.get_fleet(fleet_name)
    if fleet is None:
        return []
    return fleet.get_active_agents(governance=level, project_type=project_type)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_level(
    raw: str,
    default: Optional[GovernanceLevel] = None,
) -> GovernanceLevel:
    """Parse a governance level string into an enum value."""
    try:
        return GovernanceLevel(raw.strip().lower())
    except ValueError:
        return default or GovernanceLevel.STANDARD
