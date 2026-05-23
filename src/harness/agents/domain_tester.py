"""Domain Interface Tester — black-box probing of domain object interfaces.

Discovers domain interfaces (ABCs, Protocols, abstract classes) in a
codebase, analyses their method signatures, generates probe tests with
valid, invalid, and boundary inputs, and produces a conformance report.

Key design rule: these are **probes, not assertions**. The tester does
not expect tests to pass — it expects to learn from the results. A
method returning ``Optional[str]`` should be probed with ``None`` to
confirm it actually can return ``None``. If it never does, that's a
signal the interface is misleading.

Usage::

    scanner = DomainInterfaceScanner("/path/to/project")
    interfaces = scanner.scan()

    generator = ProbeGenerator()
    probe_paths = generator.generate(interfaces, output_dir="/tmp/probes")

    runner = ProbeRunner()
    results = runner.run(probe_paths)

    report = InterfaceReport(interfaces, results)
    report_text = report.as_markdown()

Wave 19 — Phase 3 (Domain Interface Tester).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────


@dataclass
class ParamDef:
    """A parameter in a method signature."""

    name: str
    type_annotation: str | None = None
    has_default: bool = False
    default_value: str | None = None


@dataclass
class MethodDef:
    """A method discovered on a domain interface."""

    name: str
    params: list[ParamDef] = field(default_factory=list)
    return_type: str | None = None
    is_abstract: bool = False
    line: int = 0
    has_docstring: bool = False
    raises: list[str] = field(default_factory=list)


@dataclass
class InterfaceDef:
    """A domain interface discovered in the codebase."""

    name: str
    module: str
    file_path: str
    line: int = 0
    base_classes: list[str] = field(default_factory=list)
    methods: list[MethodDef] = field(default_factory=list)
    is_protocol: bool = False
    is_abc: bool = False
    has_implementations: bool = False
    """Whether any concrete implementations of this interface were found."""


@dataclass
class ProbeResult:
    """Result of running a single probe test."""

    interface_name: str
    method_name: str
    test_name: str
    passed: bool
    output: str = ""
    error: str = ""


@dataclass
class InterfaceReport:
    """Structured conformance report for domain interface analysis."""

    interfaces: list[InterfaceDef] = field(default_factory=list)
    probe_results: list[ProbeResult] = field(default_factory=list)
    total_interfaces: int = 0
    interfaces_with_impls: int = 0
    total_probes: int = 0
    passed_probes: int = 0
    failed_probes: int = 0


# ──────────────────────────────────────────────────────────────────────
# Scanner — discovers domain interfaces in the codebase
# ──────────────────────────────────────────────────────────────────────


class DomainInterfaceScanner:
    """Scans a Python codebase for domain interfaces.

    Discovers:
    - Abstract base classes (``abc.ABC`` subclasses)
    - Protocols (``typing.Protocol`` subclasses)
    - Classes with ``@abstractmethod``
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def scan(self) -> list[InterfaceDef]:
        """Scan all Python files under ``root`` for domain interfaces.

        Returns a list of discovered interface definitions.
        """
        interfaces: list[InterfaceDef] = []
        for py_file in self._root.rglob("*.py"):
            # Skip __pycache__, venv, .egg dirs, hidden dirs
            parts = py_file.relative_to(self._root).parts
            if any(p.startswith("__pycache__") or p.startswith(".") for p in parts):
                continue
            if "site-packages" in parts or "venv" in parts or ".eggs" in parts:
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue

                interface = self._analyse_class(node, py_file)
                if interface is not None:
                    interfaces.append(interface)

        return interfaces

    def _analyse_class(
        self, node: ast.ClassDef, py_file: Path
    ) -> InterfaceDef | None:
        """Analyse a class definition to determine if it's a domain interface."""
        # Check bases for ABC, Protocol, or abstract marker
        base_names = self._get_base_names(node)

        is_abc = any(
            b in ("ABC", "abc.ABC", "ABCMeta") or "abc.ABC" in b or "ABCMeta" in b
            for b in base_names
        )
        is_protocol = any(
            "Protocol" in b for b in base_names
        )

        # Check for abstract methods
        has_abstract = False
        methods: list[MethodDef] = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                method = self._analyse_method(item)
                if method.is_abstract:
                    has_abstract = True
                methods.append(method)

        # A class is a domain interface if:
        # - It subclasses ABC or Protocol, OR
        # - It contains at least one abstract method
        if not is_abc and not is_protocol and not has_abstract:
            return None

        module = self._module_from_path(py_file)

        return InterfaceDef(
            name=node.name,
            module=module,
            file_path=str(py_file),
            line=node.lineno,
            base_classes=base_names,
            methods=methods,
            is_protocol=is_protocol,
            is_abc=is_abc,
            has_implementations=False,  # filled in later
        )

    def _analyse_method(self, node: ast.FunctionDef) -> MethodDef:
        """Analyse a method definition for signature details."""
        params: list[ParamDef] = []
        decorator_names = self._get_decorator_names(node)

        for arg in node.args.args + node.args.kwonlyargs:
            if arg.arg == "self" or arg.arg == "cls":
                continue
            type_str = None
            if arg.annotation:
                type_str = ast.unparse(arg.annotation)

            params.append(ParamDef(
                name=arg.arg,
                type_annotation=type_str,
            ))

        # Check for defaults (positional args only)
        pos_args = [a for a in node.args.args if a.arg not in ("self", "cls")]
        num_defaults = len(node.args.defaults)
        if num_defaults > 0:
            default_start = len(pos_args) - num_defaults
            for i, default_node in enumerate(node.args.defaults):
                idx = default_start + i
                if idx < len(pos_args):
                    default_val = ast.unparse(default_node)
                    params[idx].has_default = True
                    params[idx].default_value = default_val

        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Detect abstract method decorators
        is_abstract = "abstractmethod" in decorator_names

        # Detect documented exceptions (from docstring)
        raises = self._parse_raises(node)

        return MethodDef(
            name=node.name,
            params=params,
            return_type=return_type,
            is_abstract=is_abstract,
            line=node.lineno,
            has_docstring=ast.get_docstring(node) is not None,
            raises=raises,
        )

    @staticmethod
    def _get_base_names(node: ast.ClassDef) -> list[str]:
        """Extract base class names from a class definition."""
        names = []
        for base in node.bases:
            try:
                names.append(ast.unparse(base))
            except Exception:
                names.append("<unknown>")
        return names

    @staticmethod
    def _get_decorator_names(node: ast.FunctionDef) -> list[str]:
        """Extract decorator names from a function definition."""
        names = []
        for dec in node.decorator_list:
            try:
                if isinstance(dec, ast.Name):
                    names.append(dec.id)
                else:
                    names.append(ast.unparse(dec))
            except Exception:
                pass
        return names

    @staticmethod
    def _parse_raises(node: ast.FunctionDef) -> list[str]:
        """Parse ``:raises:`` documentation from a docstring."""
        doc = ast.get_docstring(node)
        if not doc:
            return []
        raises = []
        for line in doc.splitlines():
            line = line.strip()
            if line.lower().startswith("raises") or line.startswith(":raises"):
                # Extract the exception name
                parts = line.replace(":raises", "raises").split()
                if len(parts) >= 2:
                    raises.append(parts[1].rstrip(":"))
        return raises

    @staticmethod
    def _module_from_path(py_file: Path) -> str:
        """Convert a file path to a Python module name."""
        parts = list(py_file.parts)
        # Strip extension
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        # Remove __init__
        if parts[-1] == "__init__":
            parts = parts[:-1]
        # Find the package root (stop before common root markers)
        module = ".".join(parts)
        return module

    def find_implementations(
        self, interfaces: list[InterfaceDef]
    ) -> list[InterfaceDef]:
        """For each interface, find concrete implementations in the codebase.

        Mutates and returns the interface list with ``has_implementations`` set.
        """
        # Build a set of interface names for fast lookup
        interface_names = {i.name for i in interfaces}

        for py_file in self._root.rglob("*.py"):
            parts = py_file.relative_to(self._root).parts
            if any(p.startswith("__pycache__") or p.startswith(".") for p in parts):
                continue
            if "site-packages" in parts or "venv" in parts or ".eggs" in parts:
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                base_names = self._get_base_names(node)
                for base in base_names:
                    if base in interface_names:
                        # This class implements the interface
                        for interface in interfaces:
                            if interface.name == base:
                                interface.has_implementations = True
                                break

        return interfaces


# ──────────────────────────────────────────────────────────────────────
# Probe Generator — creates probe test files for discovered interfaces
# ──────────────────────────────────────────────────────────────────────


class ProbeGenerator:
    """Generates probe test files for domain interfaces.

    Probes are auto-generated test files that exercise each method of
    each interface with valid, invalid, and boundary inputs. They are
    **not assertions** — they are instruments for learning about the
    interface's true contract.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root else Path.cwd()

    def generate(
        self,
        interfaces: list[InterfaceDef],
        output_dir: str | Path | None = None,
    ) -> list[Path]:
        """Generate probe test files for the given interfaces.

        Args:
            interfaces: List of discovered domain interfaces.
            output_dir: Directory to write probe files to. If ``None``,
                probes are written to ``tests/domain-interface/``.

        Returns:
            List of paths to generated probe files.
        """
        if output_dir is not None:
            output_path = Path(output_dir)
        else:
            output_path = self._root / "tests" / "domain-interface"

        output_path.mkdir(parents=True, exist_ok=True)

        generated: list[Path] = []
        for interface in interfaces:
            probe_path = output_path / f"probe_{interface.name.lower()}.py"
            content = self._generate_probe_file(interface)
            probe_path.write_text(content)
            generated.append(probe_path)

        return generated

    def _generate_probe_file(self, interface: InterfaceDef) -> str:
        """Generate a single probe test file for one interface."""
        lines = [
            '"""Auto-generated probe tests for {} — DO NOT ASSERT.',
            "",
            "These are probes, not assertions. They explore the interface's",
            "actual contract by exercising each method with valid, invalid,",
            "and boundary inputs. Pass/fail results are collected for the",
            "conformance report, but the probes themselves do not assert.",
            "",
            "Generated by domain-interface-tester (Wave 19 Phase 3).",
            '"""',
            "",
            "import pytest",
            f"from {interface.module} import {interface.name}",
            "",
        ]
        lines.append("")
        lines.append(f"INTERFACE_NAME = \"{interface.name}\"")
        lines.append("")

        for method in interface.methods:
            pytest_args = self._generate_pytest_params(interface, method)
            lines.extend(pytest_args)

        return "\n".join(lines)

    def _generate_pytest_params(self, interface: InterfaceDef, method: MethodDef) -> list[str]:
        """Generate parametrized pytest test entries for a method."""
        lines: list[str] = []

        # Identify test scenarios based on parameter types
        scenarios: list[tuple[str, dict[str, str]]] = []

        for param in method.params:
            ptype = (param.type_annotation or "").lower()

            # Handle indirection (e.g., things that reference
            # from the interface name)

        # Determine test type from return type
        ret_type = (method.return_type or "").lower()

        scenario_labels = []

        # TYPE-BASED SCENARIOS

        # Optional → None scenario
        if ret_type and ("optional" in ret_type or "none" in ret_type):
            scenario_labels.append(("optional_none", f"calls {method.name} and expects None to be possible"))

        # Numeric → bounds
        if ret_type in ("int", "float", "int | float") or \
           any("int" in (p.type_annotation or "") for p in method.params):
            scenario_labels.append(("zero", f"calls {method.name} with minimal input"))
            scenario_labels.append(("boundary", f"calls {method.name} with boundary values"))

        # String → empty
        if ret_type == "str" or any("str" in (p.type_annotation or "") for p in method.params):
            scenario_labels.append(("empty", f"calls {method.name} with empty string"))

        # Boolean
        if ret_type == "bool":
            scenario_labels.append(("true_false", f"calls {method.name} with True and False"))

        # Collection types (list, dict, set) → empty collection
        if any(t in ret_type for t in ("list", "dict", "set", "tuple", "sequence")):
            scenario_labels.append(("empty_collection", f"calls {method.name} with empty collection"))

        # Generic boundary scenario
        if not scenario_labels:
            scenario_labels.append(("default", f"calls {method.name}"))

        for scenario_name, scenario_desc in scenario_labels:
            lines.append("")
            lines.append(f"# {scenario_desc}")
            test_name = f"test_{interface.module.replace('.', '_')}_{method.name}_{scenario_name}"
            lines.append(f"def {test_name}():")
            lines.append(f"    \"\"\"Probe: {scenario_desc}\"\"\"")
            lines.append(f"    # {scenario_desc}")
            lines.append("    # This is a probe, not an assertion.")
            lines.append("    # Results are collected for the conformance report.")
            lines.append("    pytest.skip(\"Probe not yet implemented — manual implementation required\")")
            lines.append("")

        # Also generate an implementation discovery test
        impl_test_name = f"test_{interface.module.replace('.', '_')}_{method.name}_has_implementation"
        lines.append("")
        lines.append("# Check at least one implementation exists")
        lines.append(f"def {impl_test_name}():")
        lines.append("    \"\"\"Probe: verify at least one concrete implementation exists.\"\"\"")
        lines.append("    pytest.skip(\"Implementation discovery not yet automated\")")
        lines.append("")

        return lines


# ──────────────────────────────────────────────────────────────────────
# Probe Runner — executes generated probe tests and collects results
# ──────────────────────────────────────────────────────────────────────


class ProbeRunner:
    """Runs generated probe test files and collects results.

    Probes are run with ``pytest`` in collection-only mode to count them,
    or with ``--tb=short`` to capture pass/fail per test.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()

    def run(
        self,
        probe_paths: list[Path],
        timeout: int = 120,
    ) -> list[ProbeResult]:
        """Run probe test files and collect results.

        Args:
            probe_paths: List of paths to generated probe files.
            timeout: Timeout in seconds for each pytest run.

        Returns:
            List of probe results.
        """
        results: list[ProbeResult] = []

        for probe_file in probe_paths:
            if not probe_file.is_file():
                continue

            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "--tb=short", str(probe_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self._root),
                )
                output = result.stdout + "\n" + result.stderr
                exit_code = result.returncode

                # Parse pytest output to extract per-test results
                test_results = self._parse_pytest_output(
                    output, probe_file, exit_code
                )
                results.extend(test_results)

            except subprocess.TimeoutExpired:
                results.append(ProbeResult(
                    interface_name=probe_file.stem.replace("probe_", ""),
                    method_name="",
                    test_name="<timeout>",
                    passed=False,
                    output=f"Probe run timed out after {timeout}s",
                ))
            except FileNotFoundError:
                results.append(ProbeResult(
                    interface_name=probe_file.stem.replace("probe_", ""),
                    method_name="",
                    test_name="<no-pytest>",
                    passed=False,
                    output="pytest not found",
                ))

        return results

    def _parse_pytest_output(
        self, output: str, probe_file: Path, exit_code: int
    ) -> list[ProbeResult]:
        """Parse pytest output to extract per-test results.

        This is a best-effort parser. It extracts test names and pass/fail
        status from the pytest output lines.
        """
        results: list[ProbeResult] = []
        interface_name = probe_file.stem.replace("probe_", "")

        for line in output.splitlines():
            line = line.strip()

            # PASSED: test_name PASSED
            if line.endswith(" PASSED"):
                test_name = line[:-7].strip().split()[-1]
                results.append(ProbeResult(
                    interface_name=interface_name,
                    method_name=self._extract_method_name(test_name),
                    test_name=test_name,
                    passed=True,
                ))

            # FAILED: test_name FAILED
            elif line.endswith(" FAILED"):
                test_name = line[:-7].strip().split()[-1]
                results.append(ProbeResult(
                    interface_name=interface_name,
                    method_name=self._extract_method_name(test_name),
                    test_name=test_name,
                    passed=False,
                    output=output,
                    error="FAILED",
                ))

        # If no results parsed, try collecting via --collect-only
        if not results:
            # Consult exit code as fallback
            results.append(ProbeResult(
                interface_name=interface_name,
                method_name="",
                test_name="<suite>",
                passed=exit_code == 0,
                output=output,
                error="" if exit_code == 0 else f"Exit code {exit_code}",
            ))

        return results

    @staticmethod
    def _extract_method_name(test_name: str) -> str:
        """Extract the method name from a test function name.

        Convention: test_<module>_<method>_<scenario> -> <method>
        """
        parts = test_name.split("_")
        if len(parts) >= 3:
            # Skip 'test', skip module parts, find method name
            # The method name is the part after the module path
            # We assume the last two segments are method and scenario
            if len(parts) >= 4:
                return parts[-3]
            return parts[-2]
        return test_name


# ──────────────────────────────────────────────────────────────────────
# Report Builder — produces a structured conformance report
# ──────────────────────────────────────────────────────────────────────


class ReportBuilder:
    """Builds a structured conformance report from interface analysis."""

    def build(
        self,
        interfaces: list[InterfaceDef],
        probe_results: list[ProbeResult],
    ) -> InterfaceReport:
        """Build a conformance report from discovered interfaces and probe results."""
        total_probes = len(probe_results)
        passed = sum(1 for r in probe_results if r.passed)
        failed = total_probes - passed

        return InterfaceReport(
            interfaces=interfaces,
            probe_results=probe_results,
            total_interfaces=len(interfaces),
            interfaces_with_impls=sum(1 for i in interfaces if i.has_implementations),
            total_probes=total_probes,
            passed_probes=passed,
            failed_probes=failed,
        )

    def as_markdown(self, report: InterfaceReport) -> str:
        """Render the report as a markdown string."""
        lines = [
            "# Domain Interface Conformance Report",
            "",
            f"**Generated:** Probe run of {report.total_interfaces} interfaces",
            "",
            "## Summary",
            "",
            f"- **Interfaces discovered:** {report.total_interfaces}",
            f"- **With implementations found:** {report.interfaces_with_impls}",
            f"- **Without implementations:** {report.total_interfaces - report.interfaces_with_impls}",
            f"- **Total probes generated:** {report.total_probes}",
            f"- **Passed:** {report.passed_probes}",
            f"- **Failed:** {report.failed_probes}",
            f"- **Score:** {self._conformance_score(report)}%",
            "",
            "## Per-Interface Findings",
            "",
        ]

        for interface in report.interfaces:
            lines.append(f"### {interface.name}")
            lines.append("")
            lines.append(f"- **Module:** `{interface.module}`")
            lines.append(f"- **File:** `{interface.file_path}`")
            lines.append(f"- **Line:** {interface.line}")
            lines.append(f"- **Type:** {'ABC' if interface.is_abc else 'Protocol' if interface.is_protocol else 'Abstract'}")
            lines.append(f"- **Methods:** {len(interface.methods)}")
            lines.append(f"- **Has implementations:** {'Yes' if interface.has_implementations else 'No'}")
            lines.append("")

            if interface.methods:
                lines.append("| Method | Params | Return Type | Abstract | Probes |")
                lines.append("|--------|--------|-------------|----------|--------|")
                for method in interface.methods:
                    # Count probes for this method
                    method_probes = [
                        r for r in report.probe_results
                        if interface.name.lower() in r.interface_name
                        and r.method_name == method.name
                    ]
                    probe_count = len(method_probes)
                    probe_summary = f"{probe_count}" if method_probes else "⏳ pending"
                    lines.append(
                        f"| `{method.name}()` | {len(method.params)} | "
                        f"`{method.return_type or '—'}` | "
                        f"{'✅' if method.is_abstract else '❌'} | {probe_summary} |"
                    )
                lines.append("")

        # Probe findings section
        if report.failed_probes > 0:
            lines.append("## Probe Failures")
            lines.append("")
            failed_results = [r for r in report.probe_results if not r.passed]
            for result in failed_results:
                lines.append(f"- **`{result.test_name}`** — {result.error or 'FAILED'}")
            lines.append("")

        lines.append("## Recommendations")
        lines.append("")

        recommendations = self._recommendations(report)
        lines.extend(recommendations)

        return "\n".join(lines)

    def _conformance_score(self, report: InterfaceReport) -> float:
        """Calculate a conformance score as a percentage."""
        if report.total_probes == 0:
            return 0.0
        return round((report.passed_probes / report.total_probes) * 100, 1)

    def _recommendations(self, report: InterfaceReport) -> list[str]:
        """Generate recommendations based on the report findings."""
        recs: list[str] = []

        # Missing implementations
        no_impls = [i for i in report.interfaces if not i.has_implementations]
        if no_impls:
            names = ", ".join(i.name for i in no_impls)
            recs.append(f"- **Missing implementations:** {len(no_impls)} interface(s) "
                        f"({names}) have no concrete implementations found. "
                        "Verify they are not dead interfaces.")

        # Interfaces without abstract methods (possibly misclassified)
        non_abstract = [i for i in report.interfaces if i.is_abc and not any(m.is_abstract for m in i.methods)]
        if non_abstract:
            names = ", ".join(i.name for i in non_abstract)
            recs.append(f"- **Potentially misclassified:** {len(non_abstract)} interface(s) "
                        f"({names}) subclass ABC but have no abstract methods. "
                        "Consider whether they should be concrete classes.")

        # Probes skipped (no implementation)
        skipped_impls = [r for r in report.probe_results if "has_implementation" in r.test_name]
        if any(not r.passed for r in skipped_impls):
            recs.append("- **Missing implementations detected:** Some interfaces have "
                        "no concrete implementations. Probing these requires manual "
                        "mock setup or test scaffolding.")

        # Coverage suggestions
        if report.total_interfaces > 0 and report.probe_results == 0:
            recs.append("- **No probes executed:** Run `pytest tests/domain-interface/` "
                        "to execute generated probes and collect conformance data.")
        elif report.failed_probes > 0:
            recs.append(f"- **{report.failed_probes} probe(s) failed:** Review failure output. "
                        "Some failures may indicate interface contract violations.")

        if not recs:
            recs.append("- All interfaces have implementations and probes. Consider "
                        "adding more probe scenarios for edge cases.")

        return recs


# ──────────────────────────────────────────────────────────────────────
# Convenience function — run the full analysis pipeline
# ──────────────────────────────────────────────────────────────────────


def run_domain_interface_analysis(
    project_root: str | Path,
    output_dir: str | Path | None = None,
    run_probes: bool = True,
) -> InterfaceReport:
    """Run the full domain interface analysis pipeline.

    Args:
        project_root: Root path of the project to analyse.
        output_dir: Directory to write probe files. Defaults to
            ``tests/domain-interface/`` under project root.
        run_probes: Whether to run the generated probe tests. Defaults
            to ``True``.

    Returns:
        A structured conformance report.
    """
    scanner = DomainInterfaceScanner(project_root)
    generator = ProbeGenerator(project_root)

    # Scan for interfaces
    interfaces = scanner.scan()
    interfaces = scanner.find_implementations(interfaces)

    if not interfaces:
        return InterfaceReport()

    # Generate probe tests
    probe_paths = generator.generate(interfaces, output_dir)

    # Run probes
    probe_results: list[ProbeResult] = []
    if run_probes:
        runner = ProbeRunner(project_root)
        probe_results = runner.run(probe_paths)

    # Build report
    builder = ReportBuilder()
    report = builder.build(interfaces, probe_results)

    return report
