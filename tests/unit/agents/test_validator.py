"""Tests for harness.agents.validator — SpecValidator and ValidationResult."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.agents.context import OutputContract
from harness.agents.validator import SpecValidator, ValidationResult


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_defaults(self):
        r = ValidationResult(passed=True)
        assert r.passed is True
        assert r.findings == []

    def test_findings_list(self):
        r = ValidationResult(passed=False, findings=["missing file"])
        assert r.passed is False
        assert "missing file" in r.findings

    def test_bool_truthy_when_passed(self):
        assert bool(ValidationResult(passed=True)) is True
        assert bool(ValidationResult(passed=False)) is False


class TestSpecValidatorValidate:
    """Tests for SpecValidator.validate()."""

    def test_required_file_exists(self, tmp_path):
        (tmp_path / "output.txt").write_text("data")
        contract = OutputContract(required_files=["output.txt"])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True
        assert any("output.txt" in f for f in result.findings)

    def test_required_file_missing(self, tmp_path):
        contract = OutputContract(required_files=["missing.txt"])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False
        assert any("missing.txt" in f for f in result.findings)

    def test_required_file_glob_pattern(self, tmp_path):
        (tmp_path / "src" / "main.py").parent.mkdir()
        (tmp_path / "src" / "main.py").write_text("x=1")
        (tmp_path / "src" / "utils.py").write_text("x=2")
        contract = OutputContract(required_files=["src/*.py"])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True
        assert any("main.py" in f and "utils.py" in f for f in result.findings)

    def test_empty_required_files(self, tmp_path):
        contract = OutputContract(required_files=[])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_interface_stubs_found(self, tmp_path):
        py_file = tmp_path / "module.py"
        py_file.write_text("def hello():\n    pass\n")
        contract = OutputContract(validate_interface=True)
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True
        assert any("def(s)" in f for f in result.findings)

    def test_interface_stubs_found_class(self, tmp_path):
        py_file = tmp_path / "model.py"
        py_file.write_text("class User:\n    pass\n")
        contract = OutputContract(validate_interface=True)
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True
        assert any("class(es)" in f for f in result.findings)

    def test_interface_stubs_missing(self, tmp_path):
        py_file = tmp_path / "empty.py"
        py_file.write_text("# just a comment\n")
        contract = OutputContract(validate_interface=True)
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False
        assert any("no function" in f for f in result.findings)

    def test_interface_no_py_files(self, tmp_path):
        contract = OutputContract(validate_interface=True)
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False

    def test_interface_skip_when_false(self, tmp_path):
        contract = OutputContract(validate_interface=False)
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True


class TestSpecValidatorFileRules:
    """Tests for file size rule checking."""

    def test_min_lines_pass(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        contract = OutputContract(file_rules=[
            {"pattern": "test.txt", "min_lines": 2},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_min_lines_fail(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\n")
        contract = OutputContract(file_rules=[
            {"pattern": "test.txt", "min_lines": 3},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False
        assert any("min_lines" in finding for finding in result.findings)

    def test_max_lines_pass(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\n")
        contract = OutputContract(file_rules=[
            {"pattern": "test.txt", "max_lines": 5},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_max_lines_fail(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("\n".join(f"line{i}" for i in range(10)))
        contract = OutputContract(file_rules=[
            {"pattern": "test.txt", "max_lines": 5},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False
        assert any("max_lines" in finding for finding in result.findings)

    def test_min_bytes_pass(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("hello")
        contract = OutputContract(file_rules=[
            {"pattern": "data.bin", "min_bytes": 3},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_min_bytes_fail(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("ab")
        contract = OutputContract(file_rules=[
            {"pattern": "data.bin", "min_bytes": 10},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False
        assert any("min_bytes" in finding for finding in result.findings)

    def test_max_bytes_pass(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("hello world")
        contract = OutputContract(file_rules=[
            {"pattern": "data.bin", "max_bytes": 100},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_max_bytes_fail(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("x" * 200)
        contract = OutputContract(file_rules=[
            {"pattern": "data.bin", "max_bytes": 50},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False

    def test_multiple_rules_all_pass(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\nline4\n")
        contract = OutputContract(file_rules=[
            {"pattern": "test.py", "min_lines": 2, "max_lines": 10},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_multiple_rules_one_fails(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\n")
        contract = OutputContract(file_rules=[
            {"pattern": "test.py", "min_lines": 2, "max_lines": 10},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is False

    def test_pattern_no_match(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        contract = OutputContract(file_rules=[
            {"pattern": "nonexistent/*.py"},
        ])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True

    def test_rule_missing_pattern(self, tmp_path):
        contract = OutputContract(file_rules=[{"min_lines": 5}])
        result = SpecValidator.validate(tmp_path, contract)
        assert result.passed is True  # skipped gracefully
