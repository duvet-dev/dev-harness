"""Mono-repo detection for generate-docs.

Detects sub-projects within a repository by looking for
language-specific workspace markers and directory conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────────

BUILD_PYPROJECT_TOML = "pyproject.toml"

from harness.agents.detectors import BUILD_SETUP_CFG, BUILD_SETUP_PY


@dataclass
class SubProject:
    """A detected sub-project within a mono-repo.

    Attributes:
        name: Human-readable sub-project name.
        root: Directory path relative to project root.
        language: Detected language (if any).
        description: Description inferred from context.
    """

    name: str
    root: Path
    language: Optional[str] = None
    description: str = ""


@dataclass
class MonorepoResult:
    """Result of mono-repo detection.

    Attributes:
        is_monorepo: True if multiple sub-projects were detected.
        sub_projects: List of detected sub-projects.
        relationships: Description of how sub-projects relate.
    """

    is_monorepo: bool = False
    sub_projects: list[SubProject] = field(default_factory=list)
    relationships: str = ""
    errors: list[str] = field(default_factory=list)


# ── Detection functions ─────────────────────────────────────────────────────


def _detect_language(project_dir: Path) -> Optional[str]:
    """Detect the primary language of a project directory."""
    markers: dict[str, str] = {
        BUILD_PYPROJECT_TOML: "Python",
        BUILD_SETUP_PY: "Python",
        BUILD_SETUP_CFG: "Python",
        "requirements.txt": "Python",
        "Cargo.toml": "Rust",
        "package.json": "JavaScript/TypeScript",
        "go.mod": "Go",
        "go.sum": "Go",
        "Gemfile": "Ruby",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "build.gradle.kts": "Kotlin",
        "CMakeLists.txt": "C/C++",
        "Makefile": "Make",
        "composer.json": "PHP",
    }
    for marker, lang in markers.items():
        if (project_dir / marker).is_file():
            return lang
    return None


def _find_workspace_markers(root: Path) -> list[Path]:
    """Find language-specific workspace configuration files."""
    markers = [
        "pnpm-workspace.yaml",
        "pnpm-lock.yaml",
        "Cargo.workspace",
        "go.work",
    ]
    found = []
    for marker in markers:
        p = root / marker
        if p.is_file():
            found.append(p)
    return found


def _has_subproject_directories(root: Path) -> list[Path]:
    """Check for common sub-project directory conventions."""
    candidates = []
    for dirname in ("packages", "apps", "services", "projects", "modules"):
        d = root / dirname
        if d.is_dir():
            for child in sorted(d.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    candidates.append(child)
    return candidates


def detect_sub_projects(root: Path) -> MonorepoResult:
    """Detect sub-projects in a repository.

    Uses a combination of workspace markers and directory conventions
    to identify sub-projects.

    Args:
        root: Project root directory.

    Returns:
        A ``MonorepoResult`` with detected sub-projects.
    """
    result = MonorepoResult()

    # Check workspace markers
    workspace_files = _find_workspace_markers(root)
    if workspace_files:
        result.is_monorepo = True
        result.relationships += (
            f"Workspace detected: {', '.join(p.name for p in workspace_files)}. "
        )

    # Check directory conventions
    subdirs = _has_subproject_directories(root)
    for sd in subdirs:
        lang = _detect_language(sd)
        name = sd.name.replace("_", " ").replace("-", " ").title()
        result.sub_projects.append(
            SubProject(
                name=name,
                root=sd.relative_to(root) if sd != root else sd,
                language=lang,
            )
        )

    # Also check root-level markers for a single-project repo
    if not result.sub_projects:
        root_lang = _detect_language(root)
        if root_lang:
            result.sub_projects.append(
                SubProject(
                    name=root.name,
                    root=Path("."),
                    language=root_lang,
                )
            )

    if len(result.sub_projects) > 1:
        result.is_monorepo = True

    if result.is_monorepo and len(result.sub_projects) > 1:
        # Generate basic relationship description
        sub_names = [s.name for s in result.sub_projects]
        result.relationships += (
            f"Repository contains {len(result.sub_projects)} sub-projects: "
            f"{', '.join(sub_names)}."
        )

    return result


def relationship_map(sub_projects: list[SubProject]) -> str:
    """Generate a textual description of sub-project relationships.

    Args:
        sub_projects: List of sub-projects.

    Returns:
        A string describing how sub-projects relate.
    """
    if len(sub_projects) <= 1:
        return "Single project — no sub-project relationships."

    lines = [f"Found {len(sub_projects)} sub-projects:"]
    for sp in sub_projects:
        lang_str = f" ({sp.language})" if sp.language else ""
        lines.append(f"  - {sp.name}{lang_str} — {sp.description or sp.root}")
    return "\n".join(lines)
