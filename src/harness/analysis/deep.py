"""Deep analysis — architecture conformance, coverage, dead code detection.

These checks are more expensive than the fast scan and are triggered
on-demand (e.g. via `harness summary --deep`). They assess project
health against architectural conventions and quality metrics.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness.analysis.base import Finding, ScanResult

# Architecture convention: expected top-level package structure
EXPECTED_PACKAGE_STRUCTURE: dict[str, list[str]] = {
    "python": [
        "src/",
        "tests/",
    ],
    "backend-service": [
        "src/*/domain/",
        "src/*/application/",
        "src/*/infrastructure/",
        "src/*/interfaces/",
        "tests/",
    ],
}


def check_architecture_conformance(
    path: str | Path,
    project_type: str = "python",
    rules: list[str] | None = None,
) -> ScanResult:
    """Check that the project structure follows expected conventions.

    Args:
        path: Project root.
        project_type: 'python' or 'backend-service'.
        rules: Additional convention rules (e.g. 'every module must have __init__.py').

    Returns:
        ScanResult with conformance findings.
    """
    root = Path(path)
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    if not root.exists():
        return ScanResult(
            scan_name="arch-conformance",
            findings=[Finding(
                severity="error",
                category="arch_conformance",
                message=f"Path does not exist: {path}",
                file=str(path),
            )],
            summary="Path not found",
        )

    expected = EXPECTED_PACKAGE_STRUCTURE.get(project_type, [])
    found_dirs = set()
    metrics["expected_dirs"] = expected
    metrics["checked_dirs"] = 0
    metrics["missing_dirs"] = 0

    for pattern in expected:
        # Handle glob patterns like src/*/domain/
        if "*" in pattern:
            # Check if any subdirectories match
            parent_part = pattern.split("*")[0]
            parent_dir = root / parent_part
            if parent_dir.exists():
                items = [d for d in parent_dir.iterdir() if d.is_dir()]
                for item in items:
                    expected_child = pattern.replace("*", item.name)
                    expected_path = root / expected_child
                    if expected_path.exists():
                        found_dirs.add(expected_child)
                    else:
                        findings.append(Finding(
                            severity="warning",
                            category="arch_conformance",
                            message=f"Expected directory missing: {expected_child}",
                            file=expected_child,
                        ))
                        metrics["missing_dirs"] = metrics.get("missing_dirs", 0) + 1
                    metrics["checked_dirs"] = metrics.get("checked_dirs", 0) + 1
            else:
                findings.append(Finding(
                    severity="warning",
                    category="arch_conformance",
                    message=f"Expected parent directory missing: {parent_part}",
                    file=parent_part,
                ))
        else:
            expected_dir = root / pattern
            metrics["checked_dirs"] = metrics.get("checked_dirs", 0) + 1
            if expected_dir.exists():
                found_dirs.add(pattern)
            else:
                findings.append(Finding(
                    severity="warning",
                    category="arch_conformance",
                    message=f"Expected directory missing: {pattern}",
                    file=pattern,
                ))
                metrics["missing_dirs"] = metrics.get("missing_dirs", 0) + 1

    # Check custom rules
    if rules:
        for rule in rules:
            # Simple rule format: "must_contain <glob in path>, <text>"
            match = re.match(r"must_contain\s+(.+?),\s+(.+)", rule)
            if match:
                glob_pattern, required_text = match.group(1), match.group(2)
                rule_path = root / glob_pattern
                if rule_path.exists() and rule_path.is_file():
                    content = rule_path.read_text(errors="replace")
                    if required_text not in content:
                        findings.append(Finding(
                            severity="warning",
                            category="convention",
                            message=f"Rule '{rule}' not satisfied",
                            file=glob_pattern,
                        ))

    # Check Python-specific: __init__.py in all src subdirs
    if project_type == "python":
        src_root = root / "src"
        if src_root.exists():
            for pkg_dir in src_root.rglob("*"):
                if pkg_dir.is_dir() and not any(
                    part.startswith(".") or part == "__pycache__"
                    for part in pkg_dir.relative_to(src_root).parts
                ):
                    init_file = pkg_dir / "__init__.py"
                    if not init_file.exists():
                        findings.append(Finding(
                            severity="warning",
                            category="convention",
                            message=f"Missing __init__.py in {pkg_dir.relative_to(root)}",
                            file=str(pkg_dir.relative_to(root)),
                        ))

    # Generate summary
    total_expected = len(expected)
    found_count = len(found_dirs)
    summary = (
        f"Architecture conformance: {found_count}/{total_expected} "
        f"expected directories found, {len(findings)} issues"
    )

    return ScanResult(
        scan_name="arch-conformance",
        findings=findings,
        metrics=metrics,
        summary=summary,
    )


def assess_coverage(path: str | Path) -> ScanResult:
    """Assess test coverage by checking for test files matching source files.

    For each source file under src/, looks for a corresponding test file
    under tests/. Reports files without matching tests.
    """
    root = Path(path)
    findings: list[Finding] = []

    if not root.exists():
        return ScanResult(
            scan_name="coverage",
            findings=[Finding(
                severity="error",
                category="coverage",
                message=f"Path does not exist: {path}",
                file=str(path),
            )],
            summary="Path not found",
        )

    src_root = root / "src"
    test_root = root / "tests"

    if not src_root.exists():
        return ScanResult(
            scan_name="coverage",
            summary="No src/ directory — coverage not applicable",
        )

    # Collect all test file names
    test_files = set()
    if test_root.exists():
        for tf in test_root.rglob("test_*.py"):
            test_files.add(tf.stem)  # e.g. "test_foo"

    total_src = 0
    covered = 0
    uncovered_src: list[tuple[str, str]] = []  # (rel_path, module_name)

    for sf in src_root.rglob("*.py"):
        if "__pycache__" in sf.parts:
            continue
        rel = sf.relative_to(src_root)
        total_src += 1

        # Derive expected test name
        module_name = sf.stem
        expected_test = f"test_{module_name}"

        if expected_test in test_files:
            covered += 1
        elif sf.stem != "__init__":
            uncovered_src.append((str(rel), expected_test))

    coverage_pct = (covered / total_src * 100) if total_src > 0 else 0.0

    for rel_path, test_name in uncovered_src:
        findings.append(Finding(
            severity="info" if coverage_pct >= 80 else "warning",
            category="coverage",
            message=f"No test file for {rel_path} (expected {test_name}.py)",
            file=str(rel_path),
            details={"expected_test": f"{test_name}.py"},
        ))

    # Generate finding if below threshold
    if uncovered_src and coverage_pct < 80:
        findings.insert(0, Finding(
            severity="warning",
            category="coverage",
            message=f"Coverage {coverage_pct:.0f}% ({covered}/{total_src} modules) — below 80% threshold",
            details={"coverage_pct": coverage_pct, "covered": covered, "total": total_src},
        ))

    summary = (
        f"Coverage: {covered}/{total_src} source modules have tests "
        f"({coverage_pct:.0f}%), {len(uncovered_src)} uncovered"
    )

    return ScanResult(
        scan_name="coverage",
        findings=findings,
        metrics={
            "total_src_modules": total_src,
            "covered": covered,
            "uncovered": len(uncovered_src),
            "coverage_pct": round(coverage_pct, 1),
        },
        summary=summary,
    )


def find_dead_code(path: str | Path) -> ScanResult:
    """Find potentially dead code — files with no imports or usages.

    Uses a simple heuristic: files that are never imported by any other
    file in the project. Reports __init__.py and entry points as expected.
    """
    root = Path(path)
    findings: list[Finding] = []

    if not root.exists():
        return ScanResult(
            scan_name="dead-code",
            findings=[Finding(
                severity="error",
                category="dead_code",
                message=f"Path does not exist: {path}",
                file=str(path),
            )],
            summary="Path not found",
        )

    src_root = root / "src"
    if not src_root.exists():
        return ScanResult(scan_name="dead-code", summary="No src/ directory")

    # Build map of imports: for each module, what does it import?
    import_map: dict[str, set[str]] = {}
    all_modules: set[str] = set()

    for sf in src_root.rglob("*.py"):
        if "__pycache__" in sf.parts:
            continue
        rel = str(sf.relative_to(src_root).with_suffix(""))
        module_path = rel.replace("/", ".")
        all_modules.add(module_path)

        # Parse imports
        content = sf.read_text(errors="replace")
        imported = set()
        for match in re.finditer(
            r"^(?:from|import)\s+([\w.]+)",
            content,
            re.MULTILINE,
        ):
            imported.add(match.group(1))
        import_map[module_path] = imported

    # Find modules that are never imported by any other module
    # Skip __init__ files and entry points (cli module)
    unused_modules: list[str] = []
    for module in sorted(all_modules):
        if module.endswith(".__init__"):
            continue
        if module.endswith(".cli") or module == "cli":
            continue

        is_imported = False
        for importer_path, imports in import_map.items():
            if importer_path == module:
                continue
            if module in imports or module.split(".")[-1] in imports:
                is_imported = True
                break

        if not is_imported:
            unused_modules.append(module)

    for module in unused_modules:
        findings.append(Finding(
            severity="info",
            category="dead_code",
            message=f"Module '{module}' is never imported by other modules",
            file=module.replace(".", "/") + ".py",
            details={"module": module},
        ))

    summary = (
        f"Dead code check: {len(unused_modules)} potentially unused "
        f"modules of {len(all_modules)} total"
    )

    return ScanResult(
        scan_name="dead-code",
        findings=findings,
        metrics={
            "total_modules": len(all_modules),
            "unused_modules": len(unused_modules),
        },
        summary=summary,
    )
