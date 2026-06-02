"""Tests for harness.agents.domain_tester — interface scanning, probes, reporting."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.agents.domain_tester import (
    ParamDef,
    MethodDef,
    InterfaceDef,
    ProbeResult,
    InterfaceReport,
    DomainInterfaceScanner,
    ProbeGenerator,
    ProbeRunner,
    ReportBuilder,
    run_domain_interface_analysis,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════


class TestParamDef:
    def test_minimal(self):
        p = ParamDef(name="x")
        assert p.name == "x"
        assert p.type_annotation is None
        assert p.has_default is False

    def test_full(self):
        p = ParamDef(name="count", type_annotation="int", has_default=True, default_value="0")
        assert p.name == "count"
        assert p.type_annotation == "int"
        assert p.has_default is True
        assert p.default_value == "0"


class TestMethodDef:
    def test_minimal(self):
        m = MethodDef(name="save")
        assert m.name == "save"
        assert m.params == []
        assert m.return_type is None


class TestInterfaceDef:
    def test_minimal(self):
        i = InterfaceDef(name="Repository", module="app.repo", file_path="/app/repo.py")
        assert i.name == "Repository"
        assert i.module == "app.repo"


class TestProbeResult:
    def test_defaults(self):
        r = ProbeResult(interface_name="IStorage", method_name="save",
                        test_name="test_save", passed=False)
        assert r.passed is False
        assert r.output == ""

    def test_passed(self):
        r = ProbeResult(interface_name="IStorage", method_name="save",
                        test_name="test_save", passed=True)
        assert r.passed is True


class TestInterfaceReport:
    def test_defaults(self):
        r = InterfaceReport()
        assert r.total_interfaces == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DomainInterfaceScanner
# ═══════════════════════════════════════════════════════════════════════════════


class TestDomainInterfaceScanner:
    def make_sample_file(self, path: Path, content: str):
        path.write_text(content)
        return path

    def test_scans_abc_subclass(self, tmp_path):
        self.make_sample_file(tmp_path / "interfaces.py", """
from abc import ABC, abstractmethod

class Repository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool:
        ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) == 1
        assert interfaces[0].name == "Repository"
        assert interfaces[0].is_abc is True
        assert len(interfaces[0].methods) == 1

    def test_scans_protocol(self, tmp_path):
        self.make_sample_file(tmp_path / "protocols.py", """
from typing import Protocol

class Streamable(Protocol):
    def read(self) -> bytes: ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) >= 1
        assert interfaces[0].is_protocol is True

    def test_detects_abstract_method(self, tmp_path):
        self.make_sample_file(tmp_path / "service.py", """
from abc import ABC, abstractmethod

class Service(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    def helper(self) -> None: ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) == 1
        i = interfaces[0]
        methods = {m.name for m in i.methods}
        assert "execute" in methods
        assert "helper" in methods
        abstract_methods = [m for m in i.methods if m.is_abstract]
        assert len(abstract_methods) == 1
        assert abstract_methods[0].name == "execute"

    def test_skips_non_interface_class(self, tmp_path):
        self.make_sample_file(tmp_path / "concrete.py", """
class RegularClass:
    def do_thing(self): pass
""")
        scanner = DomainInterfaceScanner(tmp_path)
        assert scanner.scan() == []

    def test_skips_pycache_and_hidden_dirs(self, tmp_path):
        (tmp_path / "__pycache__").mkdir()
        self.make_sample_file(tmp_path / "__pycache__" / "cached.py", """
from abc import ABC
class Hidden(ABC): pass
""")
        (tmp_path / ".hidden").mkdir()
        self.make_sample_file(tmp_path / ".hidden" / "ignored.py", """
from abc import ABC
class Ignored(ABC): pass
""")
        scanner = DomainInterfaceScanner(tmp_path)
        assert scanner.scan() == []

    def test_skips_site_packages(self, tmp_path):
        (tmp_path / "venv" / "lib" / "python3.9" / "site-packages").mkdir(parents=True)
        self.make_sample_file(
            tmp_path / "venv" / "lib" / "python3.9" / "site-packages" / "pkg.py",
            "from abc import ABC\nclass ExtPkg(ABC): pass\n",
        )
        scanner = DomainInterfaceScanner(tmp_path)
        assert scanner.scan() == []

    def test_handles_syntax_error_gracefully(self, tmp_path):
        self.make_sample_file(tmp_path / "broken.py", "this is not valid python {{{")
        self.make_sample_file(tmp_path / "good.py", """
from abc import ABC
class Valid(ABC):
    @abstractmethod
    def run(self): ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) == 1
        assert interfaces[0].name == "Valid"

    def test_find_implementations(self, tmp_path):
        self.make_sample_file(tmp_path / "interface.py", """
from abc import ABC, abstractmethod
class IRepo(ABC):
    @abstractmethod
    def get(self, id: int) -> str: ...
""")
        self.make_sample_file(tmp_path / "impl.py", """
from interface import IRepo
class SqlRepo(IRepo):
    def get(self, id: int) -> str: return "ok"
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) == 1
        assert interfaces[0].has_implementations is False
        interfaces = scanner.find_implementations(interfaces)
        assert interfaces[0].has_implementations is True

    def test_get_base_names(self, tmp_path):
        self.make_sample_file(tmp_path / "test.py", """
from abc import ABC, ABCMeta
class A(ABC, metaclass=ABCMeta): pass
""")
        scanner = DomainInterfaceScanner(tmp_path)
        tree = ast.parse((tmp_path / "test.py").read_text())
        class_node = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)][0]
        names = scanner._get_base_names(class_node)
        assert "ABC" in names

    def test_get_decorator_names(self, tmp_path):
        self.make_sample_file(tmp_path / "test.py", """
from abc import abstractmethod
class Foo:
    @abstractmethod
    @property
    def x(self): ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        tree = ast.parse((tmp_path / "test.py").read_text())
        func_node = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]
        names = scanner._get_decorator_names(func_node)
        assert "abstractmethod" in names
        assert "property" in names

    def test_method_with_default_value(self, tmp_path):
        self.make_sample_file(tmp_path / "test.py", """
from abc import ABC
class Pager(ABC):
    def page(self, limit: int = 10) -> list: ...
""")
        scanner = DomainInterfaceScanner(tmp_path)
        interfaces = scanner.scan()
        assert len(interfaces) >= 1
        i = interfaces[0]
        for m in i.methods:
            if m.name == "page":
                assert len(m.params) == 1
                assert m.params[0].has_default is True
                assert m.params[0].default_value == "10"


# ═══════════════════════════════════════════════════════════════════════════════
# ProbeGenerator
# ═══════════════════════════════════════════════════════════════════════════════


class TestProbeGenerator:
    def test_generates_probe_files(self, tmp_path):
        interface = InterfaceDef(
            name="IStorage",
            module="app.storage",
            file_path="/app/storage.py",
            methods=[
                MethodDef(name="save", params=[
                    ParamDef(name="data", type_annotation="dict"),
                ], return_type="bool"),
                MethodDef(name="load", params=[
                    ParamDef(name="key", type_annotation="str"),
                ], return_type="Optional[bytes]"),
            ],
        )
        generator = ProbeGenerator(tmp_path)
        paths = generator.generate([interface], output_dir=tmp_path / "probes")
        assert len(paths) == 1
        probe_file = paths[0]
        assert probe_file.exists()
        content = probe_file.read_text()
        assert "IStorage" in content
        assert "save" in content
        assert "load" in content
        assert "from app.storage import IStorage" in content

    def test_custom_output_dir(self, tmp_path):
        interface = InterfaceDef(
            name="IRepo", module="repo", file_path="repo.py",
        )
        generator = ProbeGenerator(tmp_path)
        out = tmp_path / "custom_probes"
        paths = generator.generate([interface], output_dir=out)
        assert len(paths) == 1
        assert (out / "probe_irepo.py").exists()

    def test_empty_interfaces_no_files(self, tmp_path):
        generator = ProbeGenerator(tmp_path)
        paths = generator.generate([], output_dir=tmp_path / "probes")
        assert paths == []


# ═══════════════════════════════════════════════════════════════════════════════
# ProbeRunner
# ═══════════════════════════════════════════════════════════════════════════════


class TestProbeRunner:
    def test_nonexistent_probe_file(self):
        runner = ProbeRunner()
        results = runner.run([Path("/tmp/nonexistent_probe_NONEXISTENT_TEST.py")])
        assert len(results) == 0  # File not found, silently skipped

    def test_parse_pytest_output_passed(self):
        runner = ProbeRunner()
        output = """
============================= test session starts ==============================
collected 1 item

test_save.py .                                                          [100%]

============================== 1 passed in 0.01s ===============================
"""
        results = runner._parse_pytest_output(output, Path("test_save.py"), 0)
        assert len(results) >= 1

    def test_parse_pytest_output_failed(self):
        runner = ProbeRunner()
        output = """
============================= test session starts ==============================

FAILED test_bad.py::test_crash - AssertionError: assert False

============================= 1 failed in 0.01s ===============================
"""
        results = runner._parse_pytest_output(output, Path("test_bad.py"), 1)
        assert len(results) >= 1
        assert any(not r.passed for r in results)

    def test_extract_method_name(self):
        runner = ProbeRunner()
        name = runner._extract_method_name("test_module_save_default")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_timeout_handling(self):
        runner = ProbeRunner()
        # ProbeRunner skips non-existent files, so use a real-ish path mock
        with patch("pathlib.Path.is_file", return_value=True), \
             patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=30)):
            results = runner.run([Path("test_slow.py")])
            assert len(results) >= 1
            assert all(not r.passed for r in results)

    def test_filenotfound_handling(self):
        """FileNotFoundError when pytest is missing is handled."""
        runner = ProbeRunner()
        with patch("pathlib.Path.is_file", return_value=True), \
             patch("subprocess.run",
                   side_effect=FileNotFoundError("pytest not found")):
            results = runner.run([Path("test_missing_pytest.py")])
            assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# ReportBuilder
# ═══════════════════════════════════════════════════════════════════════════════


class TestReportBuilder:
    def make_builder(self) -> ReportBuilder:
        return ReportBuilder()

    def test_empty_report(self):
        report = self.make_builder().build([], [])
        assert report.total_interfaces == 0
        assert report.total_probes == 0

    def test_score_zero_when_no_probes(self):
        report = InterfaceReport()
        assert self.make_builder()._conformance_score(report) == 0.0

    def test_score_calculation(self):
        report = InterfaceReport(
            total_probes=10,
            passed_probes=7,
            failed_probes=3,
        )
        assert self.make_builder()._conformance_score(report) == 70.0

    def test_score_all_passed(self):
        report = InterfaceReport(total_probes=4, passed_probes=4)
        assert self.make_builder()._conformance_score(report) == 100.0

    def test_markdown_empty(self):
        builder = self.make_builder()
        report = builder.build([], [])
        md = builder.as_markdown(report)
        assert "Domain Interface Conformance Report" in md
        assert "Recommendations" in md

    def test_markdown_with_interfaces(self):
        iface = InterfaceDef(
            name="IStorage", module="app.storage", file_path="/app/storage.py", line=10,
            methods=[MethodDef(name="save")],
        )
        report = InterfaceReport(
            interfaces=[iface],
            total_interfaces=1,
            total_probes=0,
        )
        md = self.make_builder().as_markdown(report)
        assert "IStorage" in md
        assert "app.storage" in md

    def test_recommendations_missing_impls(self):
        i = InterfaceDef(name="Repo", module="r", file_path="r.py", has_implementations=False)
        report = InterfaceReport(interfaces=[i], total_interfaces=1)
        recs = self.make_builder()._recommendations(report)
        assert any("Missing implementations" in r for r in recs)

    def test_recommendations_no_probes_executed(self):
        report = InterfaceReport(total_interfaces=2, total_probes=0)
        recs = self.make_builder()._recommendations(report)
        # Should mention no probes or similar
        assert len(recs) > 0

    def test_recommendations_failed_probes(self):
        report = InterfaceReport(
            total_interfaces=1, total_probes=2,
            passed_probes=1, failed_probes=1,
        )
        recs = self.make_builder()._recommendations(report)
        assert any("probe(s) failed" in r for r in recs)

    def test_recommendations_all_good(self):
        report = InterfaceReport(
            interfaces=[InterfaceDef(name="Repo", module="r", file_path="r.py",
                                     has_implementations=True)],
            total_interfaces=1, interfaces_with_impls=1,
        )
        recs = self.make_builder()._recommendations(report)
        assert not recs or any("implementations" in r for r in recs)  # graceful fallback


# ═══════════════════════════════════════════════════════════════════════════════
# run_domain_interface_analysis — integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunDomainInterfaceAnalysis:
    def test_returns_empty_report_when_no_interfaces(self, tmp_path):
        report = run_domain_interface_analysis(tmp_path, run_probes=False)
        assert isinstance(report, InterfaceReport)
        assert report.total_interfaces == 0

    def test_scans_and_generates_probes(self, tmp_path):
        (tmp_path / "interfaces.py").write_text("""
from abc import ABC, abstractmethod
class IRepo(ABC):
    @abstractmethod
    def get(self, id: int) -> str: ...
""")
        report = run_domain_interface_analysis(tmp_path, output_dir=tmp_path / "probes", run_probes=False)
        assert len(report.interfaces) == 1
        assert report.interfaces[0].name == "IRepo"
        assert (tmp_path / "probes" / "probe_irepo.py").exists()
