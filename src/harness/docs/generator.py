"""Documentation generation engine for the Dev Harness.

Orchestrates the generation of project documentation from:
- Existing project docs
- Harness analysis data (summary, status, architecture reports)
- Codebase structure analysis
- Architecture proposals

Uses a hybrid approach: templates for structured sections,
and a documentation agent for prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# ── Constants: common file names ───────────────────────────────────────

BUILD_PYPROJECT_TOML = "pyproject.toml"
BUILD_README = "README.md"

from harness.agents.detectors import BUILD_SETUP_PY
from harness.docs.monorepo import detect_sub_projects
from harness.docs.overwrite import OverwriteMode, handle_overwrite
from harness.docs.templates import render_template

# ── TOML fallback parser (Python 3.9 compat) ────────────────────────────────


def _parse_toml(content: bytes) -> dict:
    """Parse TOML content, with Python 3.9 fallback to basic key-value parsing."""
    try:
        import tomli as _tomli
        return _tomli.loads(content.decode("utf-8"))
    except ImportError:
        pass
    try:
        import tomllib as _tomllib
        return _tomllib.loads(content.decode("utf-8"))
    except ImportError:
        pass
    # Basic fallback: parse flat key=value lines under [section] headers
    result = {}
    current_section = result
    current_path = []
    try:
        text = content.decode("utf-8")
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                parts = line[1:-1].strip().split(".")
                current_path = parts
                current_section = result
                for p in parts:
                    if p not in current_section:
                        current_section[p] = {}
                    current_section = current_section[p]
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                current_section[key.strip()] = val.strip().strip("\"'")
    except Exception:
        pass
    return result


class DocType(Enum):
    FULL = "full"
    README = "readme"
    CONTRIBUTING = "contributing"
    ARCHITECTURE = "architecture"
    USAGE = "usage"
    CHANGELOG = "changelog"


class SourceTier(Enum):
    EXISTING_DOCS = 1
    HARNESS_DATA = 2
    CODEBASE = 3
    ARCHITECTURE = 4
    COMMENTS = 5


@dataclass
class DocGenerationContext:
    """Context data for documentation generation.

    This is populated from harness analysis and used to fill templates.
    """

    project_name: str = ""
    project_description: str = ""
    project_structure: str = ""

    # Commands (detected from project config)
    install_command: str = ""
    run_command: str = ""
    test_command: str = "pytest"
    lint_command: str = ""
    setup_command: str = ""
    build_command: str = ""

    # Architecture
    architecture_overview: str = ""
    system_overview: str = ""
    component_map: str = ""
    modules: list[dict] = field(default_factory=list)
    data_flow: str = ""
    decisions: list[dict] = field(default_factory=list)
    deployment_info: str = ""

    # Usage
    basic_usage: str = ""
    advanced_config: str = ""
    integration_patterns: str = ""

    # Contributing
    default_branch: str = "main"
    style_guide: str = "PEP 8"
    test_runner: str = "pytest"
    version: str = "0.1.0"


def populate_context_from_project(
    root: Path,
    source_tier: SourceTier = SourceTier.CODEBASE,
) -> DocGenerationContext:
    """Populate a DocGenerationContext from project analysis.

    Args:
        root: Project root directory.
        source_tier: Maximum source tier to use.

    Returns:
        A populated DocGenerationContext.
    """
    ctx = DocGenerationContext()

    ctx.project_name = root.name

    # Detect project metadata (tier 5+)
    # Project metadata (name, description, version) from existing files
    if source_tier.value >= SourceTier.HARNESS_DATA.value:
        ctx = _detect_project_metadata(ctx, root)

    # Detect commands (tier 3+)
    if source_tier.value >= SourceTier.CODEBASE.value:
        ctx = _detect_commands(ctx, root)

    # Detect project structure (tier 3+)
    if source_tier.value >= SourceTier.CODEBASE.value:
        tree = _generate_file_tree(root)
        ctx.project_structure = tree

    # Detect architecture info (tier 4+)
    if source_tier.value >= SourceTier.CODEBASE.value:
        ctx = _detect_architecture(ctx, root)

    return ctx


def _detect_project_metadata(ctx: DocGenerationContext, root: Path) -> DocGenerationContext:
    """Detect project name, description, version from standard files."""
    # pyproject.toml
    pyproject = root / BUILD_PYPROJECT_TOML
    if pyproject.is_file():
        with open(pyproject, "rb") as f:
            try:
                data = _parse_toml(f.read())
                if not data:
                    data = {}
                project = data.get("project", {}) or data.get("tool", {}).get(
                    "poetry", {}
                )
                if project.get("name"):
                    ctx.project_name = project["name"]
                if project.get("description"):
                    ctx.project_description = project["description"]
                if project.get("version"):
                    ctx.version = str(project["version"])
            except Exception:
                pass

    # package.json (fallback)
    pkg_json = root / "package.json"
    if pkg_json.is_file() and not ctx.project_description:
        try:
            import json
            with open(pkg_json) as f:
                data = json.load(f)
                if data.get("name"):
                    ctx.project_name = data["name"]
                if data.get("description"):
                    ctx.project_description = data["description"]
                if data.get("version"):
                    ctx.version = str(data["version"])
        except Exception:
            pass

    # README.md first line as description fallback
    if not ctx.project_description:
        readme = root / BUILD_README
        if readme.is_file():
            first_line = readme.read_text().strip().split("\n")[0]
            ctx.project_description = first_line.lstrip("# ").strip()

    return ctx


def _detect_commands(ctx: DocGenerationContext, root: Path) -> DocGenerationContext:
    """Detect build, test, run, lint commands from project config."""
    # pyproject.toml
    pyproject = root / BUILD_PYPROJECT_TOML
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = _parse_toml(f.read())

            if not data:
                data = {}

            # Test command
            if not ctx.test_command:
                task = data.get("tool", {}).get("task", {})
                if isinstance(task, dict) and "test" in task:
                    ctx.test_command = task["test"]
                elif isinstance(task, dict) and "check" in task:
                    ctx.test_command = task["check"]

            # Lint command
            lint_section = data.get("tool", {}).get("ruff", {})
            if lint_section:
                ctx.lint_command = "ruff check ."
                ctx.style_guide = "Ruff (PEP 8 + selected rules)"
            elif data.get("tool", {}).get("pylint"):
                ctx.lint_command = "pylint src/"
                ctx.style_guide = "Pylint"

        except Exception:
            pass

    # Makefile
    makefile = root / "Makefile"
    if makefile.is_file():
        if not ctx.install_command:
            ctx.install_command = "make install"
        if not ctx.test_command:
            ctx.test_command = "make test"
        if not ctx.lint_command:
            ctx.lint_command = "make lint"
        if not ctx.build_command:
            ctx.build_command = "make build"

    # Setup/install command defaults
    if not ctx.install_command:
        if (root / "requirements.txt").is_file():
            ctx.install_command = "pip install -r requirements.txt"
        elif (root / BUILD_PYPROJECT_TOML).is_file() or (root / BUILD_SETUP_PY).is_file():
            ctx.install_command = "pip install -e ."
        elif (root / "package.json").is_file():
            ctx.install_command = "npm install"

    # Run command default
    if not ctx.run_command:
        if (root / "main.py").is_file():
            ctx.run_command = "python main.py"
        elif (root / "cli.py").is_file():
            ctx.run_command = "python -m cli"
        elif any(root.glob("src/*/cli.py")):
            ctx.run_command = "harness"

    # Setup command
    ctx.setup_command = ctx.install_command or "pip install -e ."

    return ctx


def _detect_architecture(ctx: DocGenerationContext, root: Path) -> DocGenerationContext:
    """Detect architecture information from project structure."""
    src_dirs = []
    for d in ("src", "lib", "app"):
        p = root / d
        if p.is_dir():
            src_dirs.append(p)

    # Detect key modules
    modules = []
    for src_dir in src_dirs:
        for child in sorted(src_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                modules.append(
                    {"name": child.name, "description": f"Module in {src_dir.name}/"}
                )
            elif child.suffix == ".py" and child.name != "__init__.py":
                modules.append(
                    {"name": child.stem, "description": f"Module in {src_dir.name}/"}
                )

    if modules and not ctx.modules:
        ctx.modules = modules[:10]  # Limit to avoid huge docs

    # Detect data flow patterns
    if not ctx.data_flow:
        for src_dir in src_dirs:
            for py_file in src_dir.rglob("*.py"):
                content = py_file.read_text()
                if "def process" in content or "def transform" in content:
                    ctx.data_flow += (
                        f"- Data processing in {py_file.relative_to(root)}\n"
                    )

    return ctx


def _generate_file_tree(root: Path, max_depth: int = 3) -> str:
    """Generate a text-based file tree."""
    lines = []
    _tree_lines(lines, root, "", max_depth)
    return "\n".join(lines)


def _tree_lines(lines: list, path: Path, prefix: str, depth: int) -> None:
    """Recursive helper for file tree generation."""
    if depth < 0:
        lines.append(f"{prefix}└── ...")
        return

    entries = sorted(
        [e for e in path.iterdir() if not e.name.startswith(".") and e.name != "__pycache__"],
        key=lambda x: (not x.is_dir(), x.name),
    )

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "

        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if is_last else "│   "
            _tree_lines(lines, entry, prefix + extension, depth - 1)
        else:
            lines.append(f"{prefix}{connector}{entry.name}")


# ── Document Generation ────────────────────────────────────────────────────


def generate_doc(
    doc_type: DocType,
    context: DocGenerationContext,
    output_dir: Path,
    root: Path,
    overwrite_mode: OverwriteMode = OverwriteMode.ASK,
    interactive: bool = True,
    source_tier: SourceTier = SourceTier.CODEBASE,
) -> list[Path]:
    """Generate a single documentation file.

    Args:
        doc_type: Type of document to generate.
        context: Context data for template filling.
        output_dir: Output directory.
        root: Project root (for relative path resolution and backups).
        overwrite_mode: Overwrite strategy.
        interactive: Whether to prompt in ASK mode.
        source_tier: Source tier for data collection.

    Returns:
        List of generated file paths.
    """
    output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
    generated: list[Path] = []

    if doc_type == DocType.README:
        path = output_dir / BUILD_README
        content = render_template("README", context.__dict__)
        result = handle_overwrite(path, content, root, overwrite_mode, interactive)
        if result:
            generated.append(result)

    elif doc_type == DocType.CONTRIBUTING:
        path = output_dir / "CONTRIBUTING.md"
        content = render_template("CONTRIBUTING", context.__dict__)
        result = handle_overwrite(path, content, root, overwrite_mode, interactive)
        if result:
            generated.append(result)

    elif doc_type == DocType.ARCHITECTURE:
        docs_dir = output_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = docs_dir / "architecture.md"
        content = render_template("architecture", context.__dict__)
        result = handle_overwrite(path, content, root, overwrite_mode, interactive)
        if result:
            generated.append(result)

    elif doc_type == DocType.USAGE:
        docs_dir = output_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = docs_dir / "usage.md"
        content = render_template("usage", context.__dict__)
        result = handle_overwrite(path, content, root, overwrite_mode, interactive)
        if result:
            generated.append(result)

    elif doc_type == DocType.CHANGELOG:
        path = output_dir / "CHANGELOG.md"
        from harness.docs.changelog import rollup_project_changelog
        result = rollup_project_changelog(root, output_path=path)
        generated.append(result)

    return generated


def generate_all_docs(
    root: Path,
    output_dir: Optional[Path] = None,
    overwrite_mode: OverwriteMode = OverwriteMode.ASK,
    interactive: bool = True,
    source_tier: SourceTier = SourceTier.CODEBASE,
) -> list[Path]:
    """Generate all documentation files.

    Args:
        root: Project root directory.
        output_dir: Output directory. Defaults to root.
        overwrite_mode: Overwrite strategy.
        interactive: Whether to prompt in ASK mode.
        source_tier: Source tier for data collection.

    Returns:
        List of generated file paths.
    """
    if output_dir is None:
        output_dir = root

    # Populate context from project
    context = populate_context_from_project(root, source_tier)

    # Detect mono-repo
    mono_result = detect_sub_projects(root)
    if mono_result.is_monorepo and len(mono_result.sub_projects) > 1:
        context.project_description += (
            f"\n\n_Mono-repo detected: {len(mono_result.sub_projects)} sub-projects._"
        )

    # Generate all doc types
    generated: list[Path] = []
    for doc_type in DocType:
        if doc_type == DocType.FULL:
            continue  # FULL is handled by calling all types
        result = generate_doc(
            doc_type, context, output_dir, root,
            overwrite_mode, interactive, source_tier,
        )
        generated.extend(result)

    return generated
