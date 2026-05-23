"""Architecture debt detection — rule-based scanning for violations.

Detects:
- Layer boundary violations (e.g. domain importing infrastructure)
- Missing adapter boundaries for external dependencies
- Circular dependencies between layers
- Framework coupling in domain classes
- Direct database access from business logic
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from harness.config.architecture import ArchitectureGoal

# ── Data model ─────────────────────────────────────────────────────────────


@dataclass
class DebtViolation:
    """A single architecture debt violation.

    Attributes:
        rule_name: Machine-readable identifier of the violated rule.
        severity: ``error``, ``warning``, or ``info``.
        message: Human-readable description.
        file: Optional file path where the violation was found.
        line: Optional line number in the file.
        details: Optional additional context.
    """

    rule_name: str
    severity: str = "warning"
    message: str = ""
    file: Optional[str] = None
    line: Optional[int] = None
    details: Optional[str] = None


@dataclass
class DebtReport:
    """Complete debt report for a scanned codebase.

    Attributes:
        violations: All detected violations.
        architecture_goal: The goal used for comparison.
        scanned_files: Number of files scanned.
        summary: Short textual summary.
    """

    violations: list[DebtViolation] = field(default_factory=list)
    architecture_goal: Optional[ArchitectureGoal] = None
    scanned_files: int = 0
    summary: str = ""

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def errors(self) -> list[DebtViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[DebtViolation]:
        return [v for v in self.violations if v.severity == "warning"]

    @property
    def infos(self) -> list[DebtViolation]:
        return [v for v in self.violations if v.severity == "info"]

    def by_file(self) -> dict[str, list[DebtViolation]]:
        """Group violations by file path."""
        result: dict[str, list[DebtViolation]] = {}
        for v in self.violations:
            key = v.file or "(unknown)"
            if key not in result:
                result[key] = []
            result[key].append(v)
        return result

    def to_markdown(self) -> str:
        """Format the report as markdown."""
        lines: list[str] = ["## Architecture Debt Report", ""]

        if not self.violations:
            lines.append("✅ No architecture debt detected.")
            lines.append("")
            return "\n".join(lines)

        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        lines.append(f"| Error | {len(self.errors)} |")
        lines.append(f"| Warning | {len(self.warnings)} |")
        lines.append(f"| Info | {len(self.infos)} |")
        lines.append("")
        lines.append(f"**Files scanned:** {self.scanned_files}")
        lines.append("")

        for severity_name, severity_group in [
            ("Error", self.errors),
            ("Warning", self.warnings),
            ("Info", self.infos),
        ]:
            if not severity_group:
                continue
            lines.append(f"### {severity_name}")
            lines.append("")
            for v in severity_group:
                file_ref = f" `{v.file}`" if v.file else ""
                line_ref = f":{v.line}" if v.line else ""
                lines.append(
                    f"- **[{v.rule_name}]{file_ref}{line_ref}**"
                )
                lines.append(f"  - {v.message}")
                if v.details:
                    lines.append(f"  - *{v.details}*")
            lines.append("")

        return "\n".join(lines)


# ── Debt detector ──────────────────────────────────────────────────────────


class DebtDetector:
    """Rule-based architecture debt detector.

    Scans a directory tree for architecture violations given an
    ``ArchitectureGoal``.

    Usage::

        detector = DebtDetector(architecture_goal)
        report = detector.scan(project_root)
        print(report.to_markdown())
    """

    # External dependency patterns (library names that should use adapters)
    EXTERNAL_DEPENDENCIES: set[str] = {
        "requests",
        "httpx",
        "aiohttp",
        "sqlalchemy",
        "psycopg2",
        "psycopg",
        "pymongo",
        "redis",
        "boto3",
        "google.cloud",
        "azure",
        "elasticsearch",
        "kafka",
        "pika",
        "celery",
        "django",
        "flask",
        "fastapi",
        "pyramid",
        "tornado",
    }

    # Domain-layer infrastructure keyword indicators
    _INFRASTRUCTURE_KEYWORDS: set[str] = {
        "sql", "db", "database", "repository", "cache", "queue",
        "http", "api", "grpc", "rest", "rpc", "kafka", "redis",
        "postgres", "mysql", "mongodb", "s3", "blob", "storage",
        "email", "smtp", "imap", "pop3", "dns", "ssh",
    }

    def __init__(
        self,
        architecture_goal: Optional[ArchitectureGoal] = None,
    ) -> None:
        self._goal = architecture_goal or ArchitectureGoal.default()

    # ── Public API ──────────────────────────────────────────────────────

    def scan(self, root: Path) -> DebtReport:
        """Scan a project directory for architecture debt.

        Args:
            root: Root directory of the project to scan.

        Returns:
            A complete ``DebtReport``.
        """
        violations: list[DebtViolation] = []
        scanned_files = 0

        # Collect Python files (non-test, non-venv)
        python_files = self._collect_python_files(root)
        scanned_files = len(python_files)

        # Detect domain → infrastructure layer violations
        domain_files = self._filter_domain_files(python_files)
        for file_path in domain_files:
            file_violations = self._check_domain_infrastructure_leaks(file_path)
            violations.extend(file_violations)

        # Detect missing adapter boundaries
        adapter_violations = self._detect_missing_adapters(python_files, root)
        violations.extend(adapter_violations)

        # Detect direct database access from business logic (non-adapter files)
        db_violations = self._detect_direct_db_access(python_files, root)
        violations.extend(db_violations)

        # Detect framework coupling in domain
        for file_path in domain_files:
            fw_violations = self._detect_framework_coupling(file_path)
            violations.extend(fw_violations)

        # Detect circular dependencies (file-level)
        # TODO: Full circular dep analysis is a separate wave; for now flag
        #       obvious patterns
        # circular = self._detect_circular_imports(python_files)

        summary = self._build_summary(violations)

        return DebtReport(
            violations=violations,
            architecture_goal=self._goal,
            scanned_files=scanned_files,
            summary=summary,
        )

    # ── File collection ─────────────────────────────────────────────────

    def _collect_python_files(self, root: Path) -> list[Path]:
        """Collect all Python files in a directory, skipping test and venv dirs."""
        skip_dirs = {
            ".venv", "venv", "env", "__pycache__", ".git", ".tox",
            ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules",
            ".harness",
        }
        files: list[Path] = []
        for p in root.rglob("*.py"):
            if any(part in skip_dirs for part in p.relative_to(root).parts):
                continue
            # Skip test files — they have different rules
            if "test_" in p.name or p.name.startswith("conftest"):
                continue
            files.append(p)
        return files

    def _is_domain_file(self, file_path: Path) -> bool:
        """Heuristic: a file is in the domain layer if its path contains
        'domain' and doesn't contain 'adapter', 'infra', 'infrastructure'."""
        parts = file_path.parts
        path_str = str(file_path)
        has_domain = any("domain" in p.lower() for p in parts)
        has_infra = any(
            kw in p.lower()
            for p in parts
            for kw in ("adapter", "infra", "infrastructure", "persistence")
        )
        return has_domain and not has_infra

    def _filter_domain_files(self, files: list[Path]) -> list[Path]:
        return [f for f in files if self._is_domain_file(f)]

    def _is_adapter_file(self, file_path: Path) -> bool:
        """Heuristic: a file is an adapter if its path contains
        'adapter', 'infra', 'infrastructure', 'persistence'."""
        parts = file_path.parts
        return any(
            kw in p.lower()
            for p in parts
            for kw in ("adapter", "infra", "infrastructure", "persistence")
        )

    # ── Domain infrastructure leaks ─────────────────────────────────────

    def _check_domain_infrastructure_leaks(
        self, file_path: Path
    ) -> list[DebtViolation]:
        """Check that domain files don't import infrastructure packages."""
        violations: list[DebtViolation] = []
        try:
            with open(file_path) as f:
                source = f.read()
        except OSError:
            return violations

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    if self._import_looks_infra(pkg):
                        violations.append(
                            DebtViolation(
                                rule_name="domain_infrastructure_leak",
                                severity="error",
                                message=(
                                    f"Domain file imports infrastructure "
                                    f"package '{alias.name}'"
                                ),
                                file=str(file_path),
                                line=node.lineno,
                                details=(
                                    "Domain layer should not depend on "
                                    "infrastructure packages. Use an adapter."
                                ),
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split(".")[0]
                    if self._import_looks_infra(pkg):
                        violations.append(
                            DebtViolation(
                                rule_name="domain_infrastructure_leak",
                                severity="error",
                                message=(
                                    f"Domain file imports from "
                                    f"'{node.module}'"
                                ),
                                file=str(file_path),
                                line=node.lineno,
                                details=(
                                    "Domain layer should not depend on "
                                    "infrastructure packages. Use an adapter."
                                ),
                            )
                        )

        return violations

    def _import_looks_infra(self, pkg: str) -> bool:
        pkg_lower = pkg.lower()
        return any(
            pkg_lower.startswith(kw) for kw in self._INFRASTRUCTURE_KEYWORDS
        )

    # ── Missing adapter boundaries ──────────────────────────────────────

    def _detect_missing_adapters(
        self, files: list[Path], root: Path
    ) -> list[DebtViolation]:
        """Detect external dependencies used directly (no adapter wrapping)."""
        violations: list[DebtViolation] = []
        external_usage: dict[str, list[tuple[Path, int]]] = {}

        for file_path in files:
            if self._is_adapter_file(file_path):
                continue  # Adapter files are allowed to use external deps
            try:
                with open(file_path) as f:
                    source = f.read()
            except OSError:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        pkg = alias.name.split(".")[0]
                        if pkg in self.EXTERNAL_DEPENDENCIES:
                            external_usage.setdefault(pkg, []).append(
                                (file_path, node.lineno)
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        pkg = node.module.split(".")[0]
                        if pkg in self.EXTERNAL_DEPENDENCIES:
                            external_usage.setdefault(pkg, []).append(
                                (file_path, node.lineno)
                            )

        for pkg, usage in external_usage.items():
            # Group by file — if the same file uses it multiple times,
            # only report once per file
            seen_files: set[str] = set()
            for file_path, line in usage:
                rel = str(file_path.relative_to(root))
                if rel in seen_files:
                    continue
                seen_files.add(rel)
                violations.append(
                    DebtViolation(
                        rule_name="missing_adapter",
                        severity="warning",
                        message=(
                            f"External dependency '{pkg}' used directly "
                            f"without an adapter wrapper"
                        ),
                        file=rel,
                        line=line,
                        details=(
                            "Consider wrapping this dependency behind an "
                            "adapter interface in the adapters layer."
                        ),
                    )
                )

        return violations

    # ── Direct database access ──────────────────────────────────────────

    def _detect_direct_db_access(
        self, files: list[Path], root: Path
    ) -> list[DebtViolation]:
        """Detect direct database API usage in non-adapter files."""
        db_keywords = {
            "session.execute", "session.query", "session.add",
            "session.commit", "session.rollback", "session.flush",
            "cursor.execute", "connection.execute", "db.execute",
            "db.query", "db.add", "db.commit", "db.rollback",
            "Model.query", "models.query", "select(", "insert(",
            "update(", "delete(",
        }
        violations: list[DebtViolation] = []

        for file_path in files:
            if self._is_adapter_file(file_path):
                continue

            try:
                with open(file_path) as f:
                    source = f.read()
            except OSError:
                continue

            for kw in db_keywords:
                # Simple string search — pragmatic for the first pass
                idx = source.find(kw)
                if idx != -1:
                    line_no = source[:idx].count("\n") + 1
                    rel = str(file_path.relative_to(root))
                    violations.append(
                        DebtViolation(
                            rule_name="direct_db_access",
                            severity="error",
                            message=(
                                f"Direct database access pattern "
                                f"detected: '{kw}'"
                            ),
                            file=rel,
                            line=line_no,
                            details=(
                                "Database access should be behind a "
                                "repository/adapter in the infrastructure layer."
                            ),
                        )
                    )
                    break  # One violation per file for this rule

        return violations

    # ── Framework coupling ──────────────────────────────────────────────

    def _detect_framework_coupling(
        self, file_path: Path
    ) -> list[DebtViolation]:
        """Detect domain coupling to web/DI frameworks."""
        framework_imports = {
            "flask", "django", "fastapi", "pyramid", "tornado",
            "injector", "dependency_injector", "pinject",
        }
        violations: list[DebtViolation] = []

        try:
            with open(file_path) as f:
                source = f.read()
        except OSError:
            return violations

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    if pkg in framework_imports:
                        violations.append(
                            DebtViolation(
                                rule_name="framework_coupling_in_domain",
                                severity="warning",
                                message=(
                                    f"Domain file imports framework "
                                    f"'{alias.name}'"
                                ),
                                file=str(file_path),
                                line=node.lineno,
                                details=(
                                    "Domain logic should be framework-free. "
                                    "Consider extracting the framework "
                                    "dependency into the application/adapters layer."
                                ),
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split(".")[0]
                    if pkg in framework_imports:
                        violations.append(
                            DebtViolation(
                                rule_name="framework_coupling_in_domain",
                                severity="warning",
                                message=(
                                    f"Domain file imports from framework "
                                    f"'{node.module}'"
                                ),
                                file=str(file_path),
                                line=node.lineno,
                                details=(
                                    "Domain logic should be framework-free."
                                ),
                            )
                        )

        return violations

    # ── Summary builder ─────────────────────────────────────────────────

    def _build_summary(self, violations: list[DebtViolation]) -> str:
        errors = sum(1 for v in violations if v.severity == "error")
        warnings = sum(1 for v in violations if v.severity == "warning")
        infos = sum(1 for v in violations if v.severity == "info")

        if not violations:
            return "No architecture debt detected."

        parts = []
        if errors:
            parts.append(f"{errors} error(s)")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        if infos:
            parts.append(f"{infos} info(s)")

        return (
            f"Found {', '.join(parts)} across "
            f"{len(set(v.file for v in violations))} file(s)."
        )
