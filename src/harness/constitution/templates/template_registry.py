"""Project-template registry for scaffolding new projects.

Exposes two APIs:

1. **Functional API** (used by ``constitution.loader``)
   - ``get_template(name)`` — deep-copied dict for Constitution construction.
   - ``list_templates()`` — sorted names.
   - ``merge_overrides(base, overrides)`` — deep-merge into template dicts.

2. **Class API** (legacy, used by ``TemplateRegistry`` tests)
   - ``TemplateRegistry.get(name)`` — old-style template definition.
   - ``TemplateRegistry.list_templates()`` — summary entries.
   - ``TemplateRegistry.scaffold(name, project_name, target)`` — creates
     directory structure on disk.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from harness.constitution.models import PhilosophyConfig
from harness.paths import get_agents_dir
from harness.templates.agent_templates import (
    AGENT_ROLES,
    COMMUNITY_STANDARDS_MD_TEMPLATE,
    IDENTITY_MD_TEMPLATE,
    PROCEDURES_MD_TEMPLATE,
)


# ──────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────


class TemplateNotFoundError(KeyError):
    """Raised when the registry is queried with an unknown template name."""


# ══════════════════════════════════════════════
# Functional API — dict-based templates for Constitution construction
# ══════════════════════════════════════════════

_CONSTITUTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "backend-service": {
        "project": {
            "name": "my-project",
            "template": "backend-service",
            "description": "A backend service project",
        },
        "philosophy": {
            "requires_ddd": False,
            "requires_clean_architecture": True,
            "requires_hexagonal": True,
            "strict_deps": True,
            "encoding_notes": "",
        },
        "gates": {
            "default_mode": "auto",
        },
        "coding": {
            "default_backend": "custom-llm",
            "backends": [
                {
                    "name": "custom-llm",
                    "backend_type": "cli",
                    "command": "./llm/generate.sh",
                    "provider": "custom",
                    "model": "llama3",
                },
            ],
        },
        "analysis": {
            "fast_scan_triggers": ["on_summary", "post_merge"],
        },
        "agents": [
            {"name": "requirements-builder", "phase": "planning", "agent_type": "built-in"},
            {"name": "planner", "phase": "planning", "agent_type": "built-in"},
            {"name": "researcher", "phase": "research", "agent_type": "built-in"},
            {"name": "architect", "phase": "design", "agent_type": "built-in"},
            {"name": "architect-critic", "phase": "design", "agent_type": "built-in"},
            {"name": "coder", "phase": "implementation", "agent_type": "built-in"},
            {"name": "tester", "phase": "testing", "agent_type": "built-in"},
            {"name": "reviewer", "phase": "review", "agent_type": "built-in"},
        ],
    },
    "library": {
        "project": {
            "name": "my-library",
            "template": "library",
            "description": "A shared library project",
        },
        "philosophy": {
            "requires_ddd": False,
            "requires_clean_architecture": False,
            "requires_hexagonal": False,
            "strict_deps": True,
            "encoding_notes": "Library -- consumer-agnostic",
        },
        "gates": {
            "default_mode": "auto",
        },
        "coding": {
            "default_backend": "custom-llm",
            "backends": [],
        },
        "analysis": {
            "fast_scan_triggers": ["on_summary"],
        },
        "agents": [
            {"name": "requirements-builder", "phase": "planning", "agent_type": "built-in"},
            {"name": "planner", "phase": "planning", "agent_type": "built-in"},
            {"name": "researcher", "phase": "research", "agent_type": "built-in"},
            {"name": "architect", "phase": "design", "agent_type": "built-in"},
            {"name": "coder", "phase": "implementation", "agent_type": "built-in"},
            {"name": "tester", "phase": "testing", "agent_type": "built-in"},
            {"name": "reviewer", "phase": "review", "agent_type": "built-in"},
        ],
    },
    "cli-tool": {
        "project": {
            "name": "my-cli",
            "template": "cli-tool",
            "description": "A command-line tool",
        },
        "philosophy": {
            "requires_ddd": False,
            "requires_clean_architecture": False,
            "requires_hexagonal": False,
            "strict_deps": False,
            "encoding_notes": "CLI -- minimal ceremony",
        },
        "gates": {
            "default_mode": "wild",
        },
        "coding": {
            "default_backend": "custom-llm",
            "backends": [],
        },
        "analysis": {
            "fast_scan_triggers": ["on_summary", "post_merge"],
        },
        "agents": [
            {"name": "planner", "phase": "planning", "agent_type": "built-in"},
            {"name": "researcher", "phase": "research", "agent_type": "built-in"},
            {"name": "architect", "phase": "design", "agent_type": "built-in"},
            {"name": "coder", "phase": "implementation", "agent_type": "built-in"},
            {"name": "tester", "phase": "testing", "agent_type": "built-in"},
            {"name": "reviewer", "phase": "review", "agent_type": "built-in"},
        ],
    },
    "data-pipeline": {
        "project": {
            "name": "my-pipeline",
            "template": "data-pipeline",
            "description": "A data pipeline project",
        },
        "philosophy": {
            "requires_ddd": False,
            "requires_clean_architecture": False,
            "requires_hexagonal": False,
            "strict_deps": True,
            "encoding_notes": "Pipeline-oriented with explicit source/sink boundaries",
        },
        "gates": {
            "default_mode": "auto",
        },
        "coding": {
            "default_backend": "custom-llm",
            "backends": [],
        },
        "analysis": {
            "fast_scan_triggers": ["on_summary", "post_merge"],
        },
        "agents": [
            {"name": "requirements-builder", "phase": "planning", "agent_type": "built-in"},
            {"name": "planner", "phase": "planning", "agent_type": "built-in"},
            {"name": "researcher", "phase": "research", "agent_type": "built-in"},
            {"name": "architect", "phase": "design", "agent_type": "built-in"},
            {"name": "architect-critic", "phase": "design", "agent_type": "built-in"},
            {"name": "coder", "phase": "implementation", "agent_type": "built-in"},
            {"name": "tester", "phase": "testing", "agent_type": "built-in"},
            {"name": "reviewer", "phase": "review", "agent_type": "built-in"},
        ],
    },
    "general-research": {
        "project": {
            "name": "my-research",
            "template": "general-research",
            "description": "A research project",
        },
        "philosophy": {
            "requires_ddd": False,
            "requires_clean_architecture": False,
            "requires_hexagonal": False,
            "strict_deps": False,
            "encoding_notes": "Research-only -- documentation focused",
        },
        "gates": {
            "default_mode": "wild",
        },
        "coding": {
            "default_backend": "custom-llm",
            "backends": [],
        },
        "analysis": {
            "fast_scan_triggers": ["on_summary"],
        },
        "agents": [
            {"name": "requirements-builder", "phase": "planning", "agent_type": "built-in"},
            {"name": "planner", "phase": "planning", "agent_type": "built-in"},
            {"name": "researcher", "phase": "research", "agent_type": "built-in"},
            {"name": "coder", "phase": "implementation", "agent_type": "built-in"},
            {"name": "reviewer", "phase": "review", "agent_type": "built-in"},
        ],
    },
}


def get_template(name: str) -> dict[str, Any]:
    """Return a deep copy of the named template (Constitution-format dict).

    Raises ``KeyError`` if the template does not exist.
    """
    if name not in _CONSTITUTION_TEMPLATES:
        raise KeyError(
            f"Unknown template: {name!r} (available: {list(_CONSTITUTION_TEMPLATES)})"
        )
    return copy.deepcopy(_CONSTITUTION_TEMPLATES[name])


def list_constitution_templates() -> list[str]:
    """Return sorted list of registered constitution template names."""
    return sorted(_CONSTITUTION_TEMPLATES)


def merge_overrides(
    base: dict[str, Any],
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deep-merge *overrides* into *base* (mutates base in place).

    Only dict values are recursed; lists and scalars are replaced outright.
    Returns *base* for convenience.
    """
    if not overrides:
        return base

    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            merge_overrides(base[key], value)
        else:
            base[key] = value
    return base


def available_templates_str() -> str:
    """Human-readable summary of available templates."""
    return ", ".join(_CONSTITUTION_TEMPLATES)


# ══════════════════════════════════════════════
# Legacy Class API — directory-scaffolding templates
# ══════════════════════════════════════════════

_TEMPLATES: dict[str, dict] = {
    "backend-service": {
        "name": "Backend Service",
        "description": (
            "API layer with hexagonal architecture and DDD-lite. "
            "Scaffolds domain, application, infrastructure, and "
            "interface layers with unit and integration test stubs."
        ),
        "default_philosophy": PhilosophyConfig(
            requires_ddd=True,
            requires_clean_architecture=True,
            requires_hexagonal=True,
            strict_deps=True,
            encoding_notes="Hexagonal architecture with DDD aggregates",
        ),
        "default_gate_mode": "auto",
        "directories": [
            "src/{project}/domain",
            "src/{project}/application",
            "src/{project}/infrastructure",
            "src/{project}/interfaces",
            "tests/unit",
            "tests/integration",
            "docs",
        ],
    },
    "data-pipeline": {
        "name": "Data Pipeline",
        "description": (
            "Batch or streaming data pipeline. Scaffolds pipeline "
            "definitions, transforms, sources, and sinks with "
            "test stubs and documentation."
        ),
        "default_philosophy": PhilosophyConfig(
            requires_ddd=False,
            requires_clean_architecture=False,
            requires_hexagonal=False,
            strict_deps=True,
            encoding_notes="Pipeline-oriented with explicit source/sink boundaries",
        ),
        "default_gate_mode": "auto",
        "directories": [
            "src/{project}/pipelines",
            "src/{project}/transforms",
            "src/{project}/sources",
            "src/{project}/sinks",
            "tests",
            "docs",
        ],
    },
    "library": {
        "name": "Library",
        "description": (
            "A pure domain library with no framework or IO "
            "dependencies. Scaffolds a single domain module with "
            "test stubs and documentation."
        ),
        "default_philosophy": PhilosophyConfig(
            requires_ddd=True,
            requires_clean_architecture=False,
            requires_hexagonal=False,
            strict_deps=True,
            encoding_notes="Pure domain -- no framework or IO dependencies",
        ),
        "default_gate_mode": "full",
        "directories": [
            "src/{project}/domain",
            "tests",
            "docs",
        ],
    },
    "cli-tool": {
        "name": "CLI Tool",
        "description": (
            "Thin command-line wrapper around existing "
            "libraries. Scaffolds command definitions with "
            "test stubs and documentation."
        ),
        "default_philosophy": PhilosophyConfig(
            requires_ddd=False,
            requires_clean_architecture=False,
            requires_hexagonal=False,
            strict_deps=False,
            encoding_notes="Thin CLI wrapper -- delegate logic to libraries",
        ),
        "default_gate_mode": "wild",
        "directories": [
            "src/{project}/commands",
            "tests",
            "docs",
        ],
    },
    "general-research": {
        "name": "General Research",
        "description": (
            "Documentation-only research project with no code "
            "scaffolding. Creates docs and research directories."
        ),
        "default_philosophy": PhilosophyConfig(
            requires_ddd=False,
            requires_clean_architecture=False,
            requires_hexagonal=False,
            strict_deps=False,
            encoding_notes="Research-only -- documentation focused",
        ),
        "default_gate_mode": "wild",
        "directories": [
            "docs",
            "research",
        ],
    },
}


# ══════════════════════════════════════════════
# Agent profile seeding
# ══════════════════════════════════════════════


_PROVIDERS_YAML_CONTENT = """# Provider configuration (project defaults)
#
# Reference API keys via environment variables using ${{VAR_NAME}} syntax.
# Actual keys go in ~/.harness/providers.yaml -- never committed.

default_backend: api

providers:
  deepseek:
    type: openai-compatible
    api_key: ${{DEEPSEEK_API_KEY}}
    base_url: https://api.deepseek.com
    models:
      default: deepseek-v4-flash
      reasoner: deepseek-reasoner
      fast: deepseek-chat

  openai:
    type: openai
    api_key: ${{OPENAI_API_KEY}}
    base_url: https://api.openai.com/v1
    models:
      default: gpt-4o
      fast: gpt-4o-mini
"""


def seed_providers_yaml(project_path: Path) -> Path | None:
    """Create ``.harness/providers.yaml`` in *project_path* if it does not exist.

    Returns the file path if created, or ``None`` if it already existed
    (never overwrites).
    """
    target = project_path / ".harness" / "providers.yaml"
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_PROVIDERS_YAML_CONTENT, encoding="utf-8")
    return target


def seed_agent_profiles(project_path: Path, constitution_agents: list[dict]) -> Path:
    """Seed agent behaviour profile files from templates.

    Creates:
    - ``agents/standards/community-standards.md`` inside ``.harness/``
    - For each agent role: ``.harness/agents/<role>/identity.md`` and
      ``.harness/agents/<role>/procedures.md``, plus ``*memory/.gitkeep``
    - ``.harness/providers.yaml`` (if missing -- never overwrites)

    Parameters
    ----------
    project_path:
        Root of the project directory.
    constitution_agents:
        List of agent dicts from the constitution (each has at least a
        ``name`` key).

    Returns
    -------
    Path
        The created agents directory.
    """
    agents_dir = get_agents_dir(project_path)
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Community standards
    standards_dir = agents_dir / "standards"
    standards_dir.mkdir(parents=True, exist_ok=True)
    (standards_dir / "community-standards.md").write_text(
        COMMUNITY_STANDARDS_MD_TEMPLATE, encoding="utf-8"
    )

    # Per-agent profile files
    for agent in constitution_agents:
        role = agent["name"]
        display_name = AGENT_ROLES.get(role, role.capitalize())
        agent_dir = agents_dir / role
        agent_dir.mkdir(parents=True, exist_ok=True)

        (agent_dir / "identity.md").write_text(
            IDENTITY_MD_TEMPLATE.format(agent_name=display_name),
            encoding="utf-8",
        )
        (agent_dir / "procedures.md").write_text(
            PROCEDURES_MD_TEMPLATE.format(agent_name=display_name),
            encoding="utf-8",
        )

        memory_dir = agent_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / ".gitkeep").write_text("", encoding="utf-8")

    # .harness/providers.yaml -- created if missing, never overwrites
    seed_providers_yaml(project_path)

    return agents_dir


def refresh_agent_profiles(
    project_path: Path,
    force: bool = False,
) -> dict[str, list[str]]:
    """Sync agent profiles with the harness's current agent registry.

    Reads the authoritative ``AgentSpec`` list from
    ``harness.agents.agent_registry.AGENTS`` and writes updated
    ``identity.md`` and ``procedures.md`` files for each agent.

    Preserves the following:
    - ``agents/<role>/memory/`` directories and their contents
    - ``.harness/engagements/`` entirely (never touched)
    - ``.harness/providers.yaml`` (never overwritten, as env-var refs only)

    Parameters
    ----------
    project_path
        Root of the project directory.
    force
        If True, overwrite existing profile files. If False, only
        create files for agents that don't already have them.

    Returns
    -------
    dict[str, list[str]]
        Summary of actions taken, keyed by ``"created"``, ``"updated"``,
        and ``"existing"``. Each value is a list of agent role names.
    """
    from harness.agents.agent_registry import AGENTS, AgentRole

    result: dict[str, list[str]] = {
        "created": [],
        "updated": [],
        "existing": [],
    }

    agents_dir = get_agents_dir(project_path)
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Migrate old agents/ directory from project root if it exists
    _migrate_legacy_agents_dir(project_path, agents_dir)

    # Community standards (always fresh)
    standards_dir = agents_dir / "standards"
    standards_dir.mkdir(parents=True, exist_ok=True)
    (standards_dir / "community-standards.md").write_text(
        COMMUNITY_STANDARDS_MD_TEMPLATE, encoding="utf-8"
    )

    for spec in AGENTS:
        role = spec.role.value
        agent_dir = agents_dir / role
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Preserve memory/ dir
        memory_dir = agent_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        gitkeep = memory_dir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

        identity_path = agent_dir / "identity.md"
        procedures_path = agent_dir / "procedures.md"

        # Detect whether this is new, update, or skip
        is_new = not identity_path.exists()

        if not is_new and not force:
            result["existing"].append(role)
            continue

        # Build identity.md from spec
        perm_lines: list[str] = []
        if spec.tool_permissions is not None:
            tp = spec.tool_permissions
            perm_lines.append(f"- Read access: {tp.read}")
            perm_lines.append(f"- Write access: {tp.write}")
            if tp.write_prefixes is not None:
                for prefix in tp.write_prefixes:
                    perm_lines.append(f"  - Write prefix: {prefix}")
            else:
                perm_lines.append(f"  - Write prefixes: any path")

        tags_line = (
            ", ".join(spec.tags) if spec.tags else "(none)"
        )

        identity_content = f"""# Identity — {spec.name}

## Role
{spec.role.value}

## Description
{spec.description}

## Tags
{tags_line}

## Tool Permissions
{"".join(perm_lines)}
"""
        identity_path.write_text(
            identity_content.strip() + "\n", encoding="utf-8"
        )

        # Build procedures.md from SOP
        if spec.sop_summary:
            sop_items = "\n".join(
                f"{i+1}. {item}"
                for i, item in enumerate(spec.sop_summary)
            )
        else:
            sop_items = "(No SOP defined)"

        mem_path = f"agents/{role}/memory/"
        procedures_content = f"""# Procedures — {spec.name}

## Standard Operating Procedure
{sop_items}

## Memory Discipline
- Write to {mem_path} at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
"""
        procedures_path.write_text(
            procedures_content.strip() + "\n", encoding="utf-8"
        )

        if is_new:
            result["created"].append(role)
        else:
            result["updated"].append(role)

    # Ensure .harness/providers.yaml exists (never overwrite)
    seed_providers_yaml(project_path)

    return result


def _migrate_legacy_agents_dir(project_path: Path, target_dir: Path) -> None:
    """Migrate agent profiles from the legacy ``agents/`` at project
    root into the new location at ``.harness/agents/``.

    This is a one-shot migration: if the legacy directory exists and
    the new one does not, each agent profile (memory/ subdirectories
    and their contents) is copied over. The legacy directory is not
    removed.

    Once the project has run a new ``harness refresh-agents``, the new
    location takes over and the legacy directory can be removed manually.
    """
    legacy_dir = project_path / "agents"
    if not legacy_dir.is_dir():
        return
    if target_dir.is_file() or any(target_dir.iterdir()):
        # Target already has content — don't stomp
        return

    import shutil
    import logging

    logger = logging.getLogger(__name__)

    for entry in legacy_dir.iterdir():
        if entry.is_dir() and entry.name != "built-in":
            dst = target_dir / entry.name
            if not dst.exists():
                shutil.copytree(str(entry), str(dst))
                logger.debug("Migrated agents/%s to .harness/agents/%s",
                             entry.name, entry.name)


class TemplateRegistry:
    """Static registry of canonical project templates.

    All methods are static — the registry is read-only and immutable.
    """

    @staticmethod
    def list_templates() -> list[dict]:
        """Return a summary of all registered templates.

        Each entry contains ``id``, ``name``, and ``description`` keys.
        """
        return [
            {
                "id": tid,
                "name": tpl["name"],
                "description": tpl["description"],
            }
            for tid, tpl in sorted(_TEMPLATES.items())
        ]

    @staticmethod
    def get(name: str) -> dict:
        """Return the full template definition for *name*.

        Raises
        ------
        TemplateNotFoundError
            If *name* is not a registered template id.
        """
        if name not in _TEMPLATES:
            raise TemplateNotFoundError(name)
        return dict(_TEMPLATES[name])

    @staticmethod
    def scaffold(name: str, project_name: str, target: Path) -> list[Path]:
        """Scaffold a project directory tree from the named template.

        Parameters
        ----------
        name
            Template identifier (e.g. ``"backend-service"``).
        project_name
            The project name used to substitute ``{project}`` placeholders
            in directory paths.
        target
            Root directory under which the scaffold will be created.

        Returns
        -------
        list[Path]
            All directories created (including ``target`` itself), in
            the order they were created.

        Raises
        ------
        TemplateNotFoundError
            If *name* is not a registered template id.
        """
        template = TemplateRegistry.get(name)
        created: list[Path] = []

        for rel_dir in template["directories"]:
            resolved = rel_dir.replace("{project}", project_name)
            full_path = target / resolved
            full_path.mkdir(parents=True, exist_ok=True)
            created.append(full_path)

        return created
