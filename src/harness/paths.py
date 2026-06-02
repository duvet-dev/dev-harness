"""Canonical path resolvers for the harness project layout.

All paths within a harness project are resolved through this module.
If the directory structure ever needs to change (e.g. ``.harness/`` moves
or the agents directory relocates), only the functions here need updating.

Discovery
---------
- ``find_project_root(start)`` — walk up from *start* to find the
  nearest ancestor with a ``.harness/`` directory.
- ``resolve_project_root(start, command_name)`` — same but raises
  ``click.Abort`` on failure.

Harness directory (``.harness/``)
----------------------------------
- ``get_harness_dir(root)``
- ``get_engagements_dir(root)``
- ``get_engagement_dir(root, slug)``
- ``get_engagement_phases_path(root, slug)``
- ``get_engagement_goal_path(root, slug)``
- ``get_context_cache_dir(root, slug)``
- ``get_active_engagements_path(root)``
- ``get_agents_dir(root)``
- ``get_config_path(root)``
- ``get_providers_path(root)``
- ``get_fleets_path(root)``
- ``get_patterns_dir(root)``
- ``get_cache_dir(root)``
- ``get_architecture_goal_path(root)``
- ``get_boundaries_path(root)``
- ``get_docs_backups_dir(root)``
- ``get_freshness_path(root)``
- ``get_harness_state_path(root)``
- ``get_engagement_assessments_dir(root, slug)``
- ``get_engagement_chat_dir(root, slug)``
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# ── Directory / subpath constants ────────────────────────────────────────

_HARNESS_DIR_NAME = ".harness"
_AGENTS_DIR_NAME = "agents"
_ENGAGEMENTS_DIR_NAME = "engagements"
_ACTIVE_ENGAGEMENTS_FILE = "active-engagements.yaml"
_CONFIG_FILE = "config.yaml"
_PROVIDERS_FILE = "providers.yaml"
_SETTINGS_FILE = "settings.yaml"
_FLEETS_FILE = "fleets.yaml"
_PATTERNS_DIR_NAME = "patterns"
_CACHE_DIR_NAME = "cache"
_ARCHITECTURE_GOAL_FILE = "architecture-goal.yaml"
_BOUNDARIES_FILE = "boundaries.yaml"
_DOCS_BACKUPS_DIR_NAME = "docs-backups"
_FRESHNESS_FILE = ".harness-freshness.yaml"
_HARNESS_STATE_FILE = "harness-state.yaml"
_CONTEXT_DIR_NAME = "context"
_PHASES_FILE = "phases.yaml"
_ENGAGEMENT_GOAL_FILE = "architecture-goal.yaml"
_ENGAGEMENT_MD = "engagement.md"
_ENGAGEMENT_YAML = "engagement.yaml"
_PLAN_MD = "plan.md"
_PLAN_YAML = "plan.yaml"
_WAVES_DIR = "waves"
_CHECKPOINTS_DIR = "checkpoints"
_FEEDBACK_DIR = "feedback"
_CHANGELOG_DIR = "changelog"
_ASSESSMENTS_DIR = "assessments"
_CHAT_DIR = "chat"


# ── Public filename constants (used in place of old domain constant duplication) ──

ENGAGEMENTS_DIR = f"{_HARNESS_DIR_NAME}/{_ENGAGEMENTS_DIR_NAME}"
"""Deprecated constant; prefer get_engagements_dir(root)."""

ENGAGEMENT_MD = _ENGAGEMENT_MD
"""Filename for the engagement metadata markdown file."""

ENGAGEMENT_YAML_FILE = _ENGAGEMENT_YAML
"""Filename for the engagement YAML metadata file."""

PLAN_MD = _PLAN_MD
"""Filename for the engagement plan markdown file."""

PLAN_YAML = _PLAN_YAML
"""Filename for the engagement plan YAML file."""

WAVES_DIR = _WAVES_DIR
"""Directory name for engagement wave artifacts."""

ACTIVE_ENGAGEMENTS_FILE = f"{_HARNESS_DIR_NAME}/{_ACTIVE_ENGAGEMENTS_FILE}"
"""Deprecated constant; prefer get_active_engagements_path(root)."""


# ── Project root discovery ───────────────────────────────────────────────


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from *start* (default: CWD) to find the nearest
    directory containing a ``.harness/`` folder.

    Returns the first ancestor with ``.harness/``, or ``None`` if no
    project root is found (the walk stops at filesystem root).
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / _HARNESS_DIR_NAME).is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_project_root(
    start: Optional[Path] = None,
    command_name: str = "this command",
) -> Path:
    """Same as ``find_project_root`` but raises on failure.

    Args:
        start: Directory to start walking from (default: CWD).
        command_name: Human-readable command name for the error message.

    Raises:
        SystemExit: If no harness project root is found.
    """
    root = find_project_root(start)
    if root is not None:
        return root
    import sys

    print(
        f"Error: Not inside a harness project"
        f" (no {_HARNESS_DIR_NAME}/ folder).",
        file=sys.stderr,
    )
    print(
        f"  Run `harness init` first, or change to a project"
        f" directory with an existing {_HARNESS_DIR_NAME}/ folder.",
        file=sys.stderr,
    )
    sys.exit(1)


def resolve_explicit_project_root(
    explicit_path: Path,
    command_name: str = "this command",
) -> Path:
    """Resolve an explicitly-provided project path.

    The path must directly contain ``.harness/`` (no upward walk).
    Raises ``SystemExit`` if it doesn't.
    """
    candidate = explicit_path.resolve()
    if (candidate / _HARNESS_DIR_NAME).is_dir():
        return candidate
    import sys

    print(
        f"Error: {candidate} is not a harness project directory"
        f" (no {_HARNESS_DIR_NAME}/ folder).",
        file=sys.stderr,
    )
    sys.exit(1)


# ── Harness directory ────────────────────────────────────────────────────


def get_harness_dir(root: Path) -> Path:
    """Return ``root/.harness/`` — the harness's private directory."""
    return root / _HARNESS_DIR_NAME


def get_harness_gitkeep_path(root: Path) -> Path:
    """Return ``root/.harness/.gitkeep``."""
    return get_harness_dir(root) / ".gitkeep"


# ── Engagements ──────────────────────────────────────────────────────────


def get_engagements_dir(root: Path) -> Path:
    """Return ``root/.harness/engagements/``."""
    return get_harness_dir(root) / _ENGAGEMENTS_DIR_NAME


def get_engagement_dir(root: Path, slug: str) -> Path:
    """Return ``root/.harness/engagements/<slug>/``."""
    return get_engagements_dir(root) / slug


def get_engagement_md(root: Path, slug: str) -> Path:
    """Return the engagement metadata markdown file."""
    return get_engagement_dir(root, slug) / _ENGAGEMENT_MD


def get_engagement_yaml(root: Path, slug: str) -> Path:
    """Return the engagement structured metadata file."""
    return get_engagement_dir(root, slug) / _ENGAGEMENT_YAML


def get_engagement_phases_path(root: Path, slug: str) -> Path:
    """Return ``root/.harness/engagements/<slug>/phases.yaml``."""
    return get_engagement_dir(root, slug) / _PHASES_FILE


def get_engagement_goal_path(root: Path, slug: str) -> Path:
    """Return the per-engagement architecture-goal file (may not exist)."""
    return get_engagement_dir(root, slug) / _ENGAGEMENT_GOAL_FILE


def get_engagement_plan_md(root: Path, slug: str) -> Path:
    """Return the engagement plan markdown file."""
    return get_engagement_dir(root, slug) / _PLAN_MD


def get_engagement_plan_yaml(root: Path, slug: str) -> Path:
    """Return the engagement plan YAML file."""
    return get_engagement_dir(root, slug) / _PLAN_YAML


def get_engagement_waves_dir(root: Path, slug: str) -> Path:
    """Return the engagement waves directory."""
    return get_engagement_dir(root, slug) / _WAVES_DIR


def get_engagement_checkpoints_dir(root: Path, slug: str) -> Path:
    """Return the engagement checkpoints directory."""
    return get_engagement_dir(root, slug) / _CHECKPOINTS_DIR


def get_engagement_feedback_dir(root: Path, slug: str) -> Path:
    """Return the engagement feedback directory."""
    return get_engagement_dir(root, slug) / _FEEDBACK_DIR


def get_engagement_changelog_dir(root: Path, slug: str) -> Path:
    """Return the engagement changelog directory."""
    return get_engagement_dir(root, slug) / _CHANGELOG_DIR


def get_engagement_assessments_dir(root: Path, slug: str) -> Path:
    """Return the engagement assessments directory."""
    return get_engagement_dir(root, slug) / _ASSESSMENTS_DIR


def get_engagement_chat_dir(root: Path, slug: str) -> Path:
    """Return the engagement chat transcript directory."""
    return get_engagement_dir(root, slug) / _CHAT_DIR


def get_context_cache_dir(root: Path, slug: str) -> Path:
    """Return the context cache directory for an engagement."""
    return get_engagement_dir(root, slug) / _CONTEXT_DIR_NAME


# ── Active engagement ────────────────────────────────────────────────────


def get_active_engagements_path(root: Path) -> Path:
    """Return the active engagements mapping file."""
    return get_harness_dir(root) / _ACTIVE_ENGAGEMENTS_FILE


# ── Agents ────────────────────────────────────────────────────────────────


def get_agents_dir(root: Path) -> Path:
    """Return ``root/.harness/agents/`` — the agent profile directory.

    This is within the harness private dir so that the project root
    stays clean.  Previously it was at ``root/agents/``.
    """
    return get_harness_dir(root) / _AGENTS_DIR_NAME


def get_agent_dir(root: Path, role: str) -> Path:
    """Return the per-agent profile directory under ``.harness/agents/``."""
    return get_agents_dir(root) / role


def get_agent_standards_dir(root: Path) -> Path:
    """Return the standards directory under agents."""
    return get_agents_dir(root) / "standards"


def get_agent_memory_dir(root: Path, role: str) -> Path:
    """Return the per-agent memory directory."""
    return get_agent_dir(root, role) / "memory"


def get_agent_identity_path(root: Path, role: str) -> Path:
    """Return the per-agent identity.md path."""
    return get_agent_dir(root, role) / "identity.md"


def get_agent_procedures_path(root: Path, role: str) -> Path:
    """Return the per-agent procedures.md path."""
    return get_agent_dir(root, role) / "procedures.md"


# ── Configuration ────────────────────────────────────────────────────────


def get_config_path(root: Path) -> Path:
    """Return the project-level config file path."""
    return get_harness_dir(root) / _CONFIG_FILE


def get_settings_path(root: Path) -> Path:
    """Return the project-level settings file path."""
    return get_harness_dir(root) / _SETTINGS_FILE


def get_providers_path(root: Path) -> Path:
    """Return the project-level providers file path."""
    return get_harness_dir(root) / _PROVIDERS_FILE


def get_fleets_path(root: Path) -> Path:
    """Return the project-level fleets file path."""
    return get_harness_dir(root) / _FLEETS_FILE


def get_patterns_dir(root: Path) -> Path:
    """Return the project-level patterns directory."""
    return get_harness_dir(root) / _PATTERNS_DIR_NAME


def get_cache_dir(root: Path) -> Path:
    """Return the harness cache directory."""
    return get_harness_dir(root) / _CACHE_DIR_NAME


def get_architecture_goal_path(root: Path) -> Path:
    """Return the project-level architecture-goal file path."""
    return get_harness_dir(root) / _ARCHITECTURE_GOAL_FILE


def get_boundaries_path(root: Path) -> Path:
    """Return the project-level boundaries file path."""
    return get_harness_dir(root) / _BOUNDARIES_FILE


# ── Docs ─────────────────────────────────────────────────────────────────


def get_docs_backups_dir(root: Path) -> Path:
    """Return the docs backups directory under .harness/."""
    return get_harness_dir(root) / _DOCS_BACKUPS_DIR_NAME


# ── State ────────────────────────────────────────────────────────────────


def get_freshness_path(root: Path) -> Path:
    """Return the freshness file at the project root (not inside .harness/)."""
    return root / _FRESHNESS_FILE


def get_harness_state_path(root: Path) -> Path:
    """Return the harness state snapshot at the project root."""
    return root / _HARNESS_STATE_FILE
