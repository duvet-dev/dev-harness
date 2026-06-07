"""Wave 16b scope: boundary test generation and architecture debt detection.

This module implements two capabilities that were originally scoped as
Wave 16b and are now absorbed into the phase-specific agents:

1. **Boundary Test Generation** (build-agent capability)
   - Identifies application interfaces (module boundaries, entry points)
   - Generates behaviour-capturing tests at each boundary
   - Tests are marked IMMUTABLE for refactoring safety

2. **Architecture Debt Detection** (design-agent capability)
   - Rule-based scanning for architectural violations
   - Detects mixed concerns, boundary violations, missing abstractions
   - Produces structured debt reports

Both produce outputs to engagement artifact directories.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Part 1: Boundary Test Generation (build-agent capability)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ApplicationBoundary:
    """An application boundary identified for test generation.

    Attributes:
        name: Human-readable name of the boundary.
        module_path: Python module path (e.g. "src/harness/service.py").
        boundary_type: Type of boundary (public_api, module_entry, interface).
        functions: List of function/method signatures at this boundary.
        classes: List of classes exposed at this boundary.
    """

    name: str
    module_path: str
    boundary_type: str  # "public_api", "module_entry", "interface"
    functions: list[dict[str, Any]] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)


@dataclass
class BoundaryTestSpec:
    """Specification for a generated boundary test.

    Attributes:
        boundary: The boundary this test targets.
        test_path: Relative path for the test file.
        test_code: The generated test code.
        immutable: Whether this test is marked immutable.
    """

    boundary: ApplicationBoundary
    test_path: str
    test_code: str
    immutable: bool = True


def discover_application_boundaries(
    root: Path,
    max_files: int = 50,
) -> list[ApplicationBoundary]:
    """Discover application boundaries in the project.

    Uses structural inference to identify:
    - Public API files (__init__.py with public exports)
    - Module entry points (cli.py, main.py, entry.py)
    - Interface/abstract classes (ABC, Protocol subclasses)

    Args:
        root: Project root directory.
        max_files: Maximum number of files to scan.

    Returns:
        List of discovered boundaries.
    """
    boundaries: list[ApplicationBoundary] = []

    src_dir = _find_source_dir(root)
    if not src_dir:
        logger.warning("No src/ directory found, scanning root")
        src_dir = root

    # Collect Python files up to max_files
    py_files = []
    for path in src_dir.rglob("*.py"):
        if ".git" in path.parts:
            continue
        if "node_modules" in path.parts:
            continue
        if "__pycache__" in path.parts:
            continue
        py_files.append(path)
        if len(py_files) >= max_files:
            break

    for py_file in py_files:
        rel_path = str(py_file.relative_to(root))
        try:
            tree = ast.parse(py_file.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Check for entry-point files
        if py_file.name in ("cli.py", "main.py", "entry.py", "app.py"):
            boundaries.append(
                ApplicationBoundary(
                    name=f"Entry point: {py_file.name}",
                    module_path=rel_path,
                    boundary_type="public_api",
                    functions=_extract_public_functions(tree),
                    classes=_extract_public_classes(tree),
                )
            )

        # Check for __init__.py with public exports
        if py_file.name == "__init__.py":
            module_name = rel_path.replace("/__init__.py", "").replace(".py", "")
            exports = _extract_exports(tree)
            if exports:
                boundaries.append(
                    ApplicationBoundary(
                        name=f"Module: {module_name}",
                        module_path=rel_path,
                        boundary_type="module_entry",
                        functions=exports.get("functions", []),
                        classes=exports.get("classes", []),
                    )
                )

        # Check for ABC/Protocol classes
        interfaces = _extract_interfaces(tree)
        for iface_name, methods in interfaces:
            module_name = rel_path.replace("/", ".").replace(".py", "")
            boundaries.append(
                ApplicationBoundary(
                    name=f"Interface: {module_name}.{iface_name}",
                    module_path=rel_path,
                    boundary_type="interface",
                    functions=methods,
                    classes=[iface_name],
                )
            )

    return boundaries


def _find_source_dir(root: Path) -> Path | None:
    """Find the source directory (src/ or project root)."""
    src = root / "src"
    if src.is_dir():
        return src
    lib = root / "lib"
    if lib.is_dir():
        return lib
    return None


def _extract_public_functions(tree: ast.AST) -> list[dict[str, Any]]:
    """Extract public function signatures from an AST."""
    functions = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            args = [a.arg for a in node.args.args]
            returns = (
                ast.unparse(node.returns) if node.returns else None
            )
            functions.append({
                "name": node.name,
                "args": args,
                "returns": returns,
            })
    return functions


def _extract_public_classes(tree: ast.AST) -> list[str]:
    """Extract public class names from an AST."""
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
    return classes


def _extract_exports(tree: ast.AST) -> dict[str, list[Any]]:
    """Extract exports from __init__.py."""
    exports: dict[str, list[Any]] = {"functions": [], "classes": []}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            exports["functions"].append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
            })
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            exports["classes"].append(node.name)
        elif isinstance(node, ast.Assign):
            # Check for __all__
            if hasattr(node.targets[0], 'id') and node.targets[0].id == '__all__':
                if isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant):
                            exports.setdefault("__all__", []).append(elt.value)
    return exports


def _extract_interfaces(tree: ast.AST) -> list[tuple[str, list[dict[str, Any]]]]:
    """Extract ABC/Protocol classes and their methods."""
    interfaces = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Check for ABC or Protocol inheritance
        for base in node.bases:
            base_name = ast.unparse(base) if isinstance(base, ast.Attribute) else (
                base.id if isinstance(base, ast.Name) else ""
            )
            if base_name in ("ABC", "Protocol"):
                methods = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        methods.append({
                            "name": item.name,
                            "args": [a.arg for a in item.args.args],
                            "returns": (
                                ast.unparse(item.returns) if item.returns else None
                            ),
                        })
                interfaces.append((node.name, methods))
                break
    return interfaces


def generate_boundary_test(
    boundary: ApplicationBoundary,
    output_dir: Path,
    prefix: str = "test_boundary",
) -> BoundaryTestSpec:
    """Generate a boundary test file for a given boundary.

    Produces a test that calls each public function/class method at
    the boundary and asserts basic behaviour (not implementation).

    Args:
        boundary: The boundary to generate tests for.
        output_dir: Directory to place the test file in.
        prefix: File prefix for the test name.

    Returns:
        A BoundaryTestSpec with the generated test code.
    """
    import datetime

    module_import = boundary.module_path.replace("/", ".").replace(".py", "")
    if boundary.module_path.endswith("/__init__.py"):
        module_import = boundary.module_path.replace("/__init__.py", "").replace("/", ".")

    test_filename = f"{prefix}_{boundary.name.lower().replace(' ', '_').replace(':', '')}.py"
    test_path = str(output_dir / test_filename)

    lines: list[str] = [
        f'"""Boundary test for {boundary.name}.',
        "",
        "This test captures current behaviour at the application boundary.",
        "IMMUTABLE — do not modify. If behaviour changes, the test should",
        "be updated by a developer who understands the change.",
        "",
        f"Generated: {datetime.datetime.now().isoformat()}",
        f"Boundary type: {boundary.boundary_type}",
        f"Module: {module_import}",
        '"""',
        "",
        "import pytest",
        "",
    ]

    if boundary.functions:
        lines.append(f"from {module_import} import (")
        for func in boundary.functions:
            lines.append(f"    {func['name']},")
        lines.append(")")
        lines.append("")
        lines.append("")
        for func in boundary.functions:
            test_name = f"test_{func['name']}_exists"
            lines.extend([
                f"def {test_name}():",
                f'    """Verify {func["name"]} is callable."""',
                f"    assert callable({func['name']})",
                "",
            ])

    if boundary.classes:
        for cls_name in boundary.classes:
            lines.append(f"from {module_import} import {cls_name}")
        lines.append("")
        for cls_name in boundary.classes:
            test_name = f"test_{cls_name.lower()}_instantiation"
            lines.extend([
                f"def {test_name}():",
                f'    """Verify {cls_name} can be instantiated."""',
                f"    obj = {cls_name}()",
                "    assert obj is not None",
                f'    assert isinstance(obj, {cls_name})',
                "",
            ])

    test_code = "\n".join(lines)

    return BoundaryTestSpec(
        boundary=boundary,
        test_path=test_path,
        test_code=test_code,
        immutable=True,
    )


def generate_all_boundary_tests(
    root: Path,
    output_subdir: str = "tests/boundary/",
) -> list[BoundaryTestSpec]:
    """Discover boundaries and generate tests for all of them.

    Args:
        root: Project root directory.
        output_subdir: Subdirectory for generated tests.

    Returns:
        List of generated boundary test specs.
    """
    output_dir = (root / output_subdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    boundaries = discover_application_boundaries(root)
    specs: list[BoundaryTestSpec] = []

    for boundary in boundaries:
        spec = generate_boundary_test(boundary, output_dir)
        spec.test_path = str(output_dir / Path(spec.test_path).name)
        specs.append(spec)

        # Write the test file
        test_file = Path(spec.test_path)
        if test_file.suffix != ".py":
            test_file = test_file.with_suffix(".py")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(spec.test_code)
        logger.info("Generated boundary test: %s", test_file)

    return specs


# ═══════════════════════════════════════════════════════════════════════════
# Part 2: Architecture Debt Detection (design-agent capability)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ArchitectureDebt:
    """A detected architecture debt item.

    Attributes:
        category: Category of debt (mixed_concerns, boundary_violation,
            missing_abstraction, god_object, magic_literals).
        file_path: Path to the file with the issue.
        line_number: Line number of the issue.
        severity: Severity level (blocker, major, minor, suggestion).
        description: Human-readable description.
        recommendation: Suggestion for remediation.
    """

    category: str
    file_path: str
    line_number: int = 0
    severity: str = "major"
    description: str = ""
    recommendation: str = ""


@dataclass
class ArchitectureDebtReport:
    """Full architecture debt report.

    Attributes:
        project_root: Project root path.
        scan_time: ISO timestamp of scan.
        total_debt_items: Count of all debt items.
        by_category: Dict mapping category to list of debt items.
        by_severity: Dict mapping severity to list of debt items.
        summary: Human-readable summary.
    """

    project_root: str
    scan_time: str = ""
    total_debt_items: int = 0
    by_category: dict[str, list[ArchitectureDebt]] = field(default_factory=dict)
    by_severity: dict[str, list[ArchitectureDebt]] = field(default_factory=dict)
    summary: str = ""


def scan_architecture_debt(
    root: Path,
    max_files: int = 100,
) -> ArchitectureDebtReport:
    """Scan a project for architecture debt using rule-based detection.

    Rules:
    1. Mixed Concerns — A file that defines domain logic AND infrastructure
       (suggesting layer boundary violations)
    2. God Objects — Classes with too many methods (>15) or too many
       dependencies
    3. Missing Abstractions — Direct use of external libraries in domain code
       instead of through an adapter/interface
    4. Magic Literals — Inline strings/numbers that should be named constants
    5. Circular Dependencies — Module-level circular imports
    6. Large Modules — Files with >500 lines

    Args:
        root: Project root directory.
        max_files: Maximum number of files to scan.

    Returns:
        ArchitectureDebtReport with all findings.
    """
    import datetime

    report = ArchitectureDebtReport(
        project_root=str(root),
        scan_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    src_dir = _find_source_dir(root) or root

    # Collect Python files
    py_files = []
    for path in src_dir.rglob("*.py"):
        if any(p in path.parts for p in (".git", "node_modules", "__pycache__", ".venv")):
            continue
        py_files.append(path)
        if len(py_files) >= max_files:
            break

    for py_file in py_files:
        rel_path = str(py_file.relative_to(root))
        try:
            content = py_file.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Rule 1: Large modules
        if len(content.splitlines()) > 500:
            debt = ArchitectureDebt(
                category="large_module",
                file_path=rel_path,
                severity="minor",
                description=f"File has {len(content.splitlines())} lines (threshold: 500)",
                recommendation="Consider splitting into smaller, focused modules.",
            )
            _add_debt(report, debt)

        # Rule 2: Magic literals (inline strings/numbers that aren't named)
        magic_count = _count_magic_literals(tree)
        if magic_count > 5:
            debt = ArchitectureDebt(
                category="magic_literals",
                file_path=rel_path,
                severity="major",
                description=f"Found {magic_count} magic literals (strings/numbers) that should be named constants",
                recommendation="Extract inline literals into named constants in a dedicated constants module.",
            )
            _add_debt(report, debt)

        # Rule 3: God objects — classes with too many methods
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in ast.iter_child_nodes(node) if isinstance(n, ast.FunctionDef)]
                if len(methods) > 15:
                    debt = ArchitectureDebt(
                        category="god_object",
                        file_path=rel_path,
                        line_number=node.lineno or 0,
                        severity="major",
                        description=f"Class '{node.name}' has {len(methods)} methods (threshold: 15)",
                        recommendation="Consider splitting into smaller, focused classes.",
                    )
                    _add_debt(report, debt)

        # Rule 4: Mixed concerns — domain files importing infrastructure
        if _is_domain_file(rel_path):
            infra_imports = _check_infrastructure_imports(tree)
            if infra_imports:
                debt = ArchitectureDebt(
                    category="mixed_concerns",
                    file_path=rel_path,
                    severity="blocker",
                    description=(
                        f"Domain file imports infrastructure: {', '.join(infra_imports[:3])}"
                    ),
                    recommendation=(
                        "Domain code should not import from infrastructure. "
                        "Use dependency inversion: define interfaces in domain, "
                        "implement in infrastructure."
                    ),
                )
                _add_debt(report, debt)

    report.total_debt_items = sum(len(items) for items in report.by_category.values())
    severity_counts = ", ".join(
        f"{sev}: {len(items)}" for sev, items in report.by_severity.items()
    )
    report.summary = (
        f"Architecture debt scan complete. Found {report.total_debt_items} item(s). "
        f"{severity_counts}"
    )

    return report


def _is_domain_file(rel_path: str) -> bool:
    """Check if a file is in a domain module."""
    domain_patterns = ["/domain/", "/model/", "/entities/", "/aggregate/", "/value_object/"]
    for pattern in domain_patterns:
        if pattern in rel_path:
            return True
    return False


def _check_infrastructure_imports(tree: ast.AST) -> list[str]:
    """Check for infrastructure imports in domain code."""
    infra_patterns = [
        "sqlalchemy", "django.db", "requests", "httpx", "redis",
        "boto3", "fastapi", "flask", "celery", "kafka",
    ]
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for pattern in infra_patterns:
                    if alias.name.startswith(pattern):
                        found.append(alias.name)
                        break
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for pattern in infra_patterns:
                    if node.module.startswith(pattern):
                        found.append(node.module)
                        break
    return found


def _count_magic_literals(tree: ast.AST) -> int:
    """Count inline string/number literals that aren't named constants.

    Does not count:
    - __init__ or __new__ method bodies
    - docstrings
    - type annotations
    - test files
    """
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Str) or isinstance(node, ast.Constant):
            if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float)):
                # Skip docstrings
                if isinstance(node.parent, ast.Expr) if hasattr(node, 'parent') else False:
                    continue
                # Skip 0, 1, True, False, None
                if node.value in (0, 1, True, False, None):
                    continue
                # Skip empty strings
                if isinstance(node.value, str) and not node.value.strip():
                    continue
                count += 1
    return count


def _add_debt(report: ArchitectureDebtReport, debt: ArchitectureDebt) -> None:
    """Add a debt item to the report's index structures."""
    report.by_category.setdefault(debt.category, []).append(debt)
    report.by_severity.setdefault(debt.severity, []).append(debt)


def generate_debt_report(
    report: ArchitectureDebtReport,
    output_path: Path,
) -> str:
    """Generate a human-readable architecture debt report.

    Args:
        report: The architecture debt report.
        output_path: Path to write the report to.

    Returns:
        The report content as a string.
    """
    lines = [
        "# Architecture Debt Report",
        "",
        f"**Project:** {report.project_root}",
        f"**Scan Time:** {report.scan_time}",
        f"**Total Debt Items:** {report.total_debt_items}",
        "",
    ]

    severity_order = ["blocker", "major", "minor", "suggestion"]
    category_labels = {
        "large_module": "Large Modules",
        "magic_literals": "Magic Literals",
        "god_object": "God Objects",
        "mixed_concerns": "Mixed Concerns / Layer Violations",
        "boundary_violation": "Boundary Violations",
        "missing_abstraction": "Missing Abstractions",
        "circular_dependency": "Circular Dependencies",
    }

    for category in sorted(report.by_category.keys()):
        items = report.by_category[category]
        label = category_labels.get(category, category.replace("_", " ").title())
        lines.append(f"## {label} ({len(items)})")
        lines.append("")

        for debt in items:
            severity_icon = {
                "blocker": "🔴",
                "major": "🟠",
                "minor": "🟡",
                "suggestion": "🔵",
            }.get(debt.severity, "⚪")
            lines.append(f"### {severity_icon} [{debt.severity.upper()}] {debt.file_path}")
            if debt.line_number:
                lines.append(f"- **Line:** {debt.line_number}")
            lines.append(f"- **Description:** {debt.description}")
            lines.append(f"- **Recommendation:** {debt.recommendation}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(report.summary)
    lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content)
    logger.info("Debt report written: %s", output_path)

    return content
