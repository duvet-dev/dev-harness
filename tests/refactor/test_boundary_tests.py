"""Tests for harness.refactor.boundary_tests."""

from pathlib import Path

import pytest

from harness.refactor.boundaries import BoundaryCandidate
from harness.refactor.boundary_tests import (
    IMMUTABLE_HEADER,
    BoundaryTest,
    _boundary_test_relpath,
    _compute_hash,
    _infer_boundary_api,
    _module_import_path,
    _to_pascal_case,
    generate_boundary_test,
    generate_boundary_test_module,
    verify_boundary_test_integrity,
)


class TestImmutableHeader:
    def test_header_present(self):
        assert "IMMUTABLE" in IMMUTABLE_HEADER
        assert "DO NOT MODIFY" in IMMUTABLE_HEADER


class TestComputeHash:
    def test_hash_is_sha256(self):
        h = _compute_hash("test content")
        assert len(h) == 64

    def test_hash_different_for_different_content(self):
        h1 = _compute_hash("content a")
        h2 = _compute_hash("content b")
        assert h1 != h2


class TestModuleImportPath:
    def test_strips_src_prefix(self):
        result = _module_import_path("src/harness/foo.py")
        assert result == "harness.foo"

    def test_converts_slashes_to_dots(self):
        result = _module_import_path("lib/utils/helpers.py")
        assert result == "lib.utils.helpers"

    def test_handles_no_path_separator(self):
        result = _module_import_path("module.py")
        assert result == "module"


class TestInferBoundaryApi:
    def test_package_type(self):
        bc = BoundaryCandidate(name="pkg:core", path="src/core/__init__.py", boundary_type="package")
        import_path, public_names, example = _infer_boundary_api(bc)
        assert "core" in import_path

    def test_api_type(self):
        bc = BoundaryCandidate(name="api:rest", path="src/api/routes.py", boundary_type="api")
        import_path, public_names, example = _infer_boundary_api(bc)
        assert "api.routes" in import_path

    def test_interface_type(self):
        bc = BoundaryCandidate(name="iface:ports", path="src/ports.py", boundary_type="interface")
        import_path, public_names, example = _infer_boundary_api(bc)
        assert "ports" in import_path

    def test_default_module(self):
        bc = BoundaryCandidate(name="mod:util", path="src/util.py", boundary_type="module")
        import_path, public_names, example = _infer_boundary_api(bc)
        assert "util" in import_path


class TestToPascalCase:
    def test_snake_case(self):
        assert _to_pascal_case("my_test_class") == "MyTestClass"

    def test_kebab_case(self):
        assert _to_pascal_case("my-test-class") == "MyTestClass"

    def test_colon_delimited(self):
        assert _to_pascal_case("package:core") == "PackageCore"

    def test_single_word(self):
        assert _to_pascal_case("test") == "Test"

    def test_empty_string(self):
        assert _to_pascal_case("") == ""


class TestBoundaryTestRelpath:
    def test_regular_module(self):
        bc = BoundaryCandidate(name="test", path="src/harness/foo.py", boundary_type="module")
        rel = _boundary_test_relpath(bc, Path("."))
        assert rel == "tests/boundaries/test_foo.py"

    def test_init_module(self):
        bc = BoundaryCandidate(name="pkg:core", path="src/core/__init__.py", boundary_type="package")
        rel = _boundary_test_relpath(bc, Path("."))
        assert rel == "tests/boundaries/test_core.py"


class TestGenerateBoundaryTest:
    def test_generates_test_file(self, tmp_path):
        bc = BoundaryCandidate(name="module:util", path="src/harness/util.py", boundary_type="module")
        test = generate_boundary_test(bc, tmp_path, tmp_path)
        assert test.test_path.exists()
        assert IMMUTABLE_HEADER in test.content
        assert "IMMUTABLE" in test.content
        assert test.content_hash == _compute_hash(test.content)

    def test_generated_test_has_pytest_markers(self, tmp_path):
        bc = BoundaryCandidate(name="api:rest", path="src/harness/routes.py", boundary_type="api")
        test = generate_boundary_test(bc, tmp_path, tmp_path)
        assert "@pytest.mark.boundary" in test.content
        assert "@pytest.mark.immutable" in test.content

    def test_includes_import_statement(self, tmp_path):
        bc = BoundaryCandidate(name="mod:foo", path="src/harness/foo.py", boundary_type="module")
        test = generate_boundary_test(bc, tmp_path, tmp_path)
        assert "import harness.foo" in test.content


class TestGenerateBoundaryTestModule:
    def test_generates_multiple_tests(self, tmp_path):
        boundaries = [
            BoundaryCandidate(name="a", path="src/a.py", boundary_type="module"),
            BoundaryCandidate(name="b", path="src/b.py", boundary_type="module"),
        ]
        tests = generate_boundary_test_module(boundaries, tmp_path, tmp_path)
        assert len(tests) == 2
        assert all(t.test_path.exists() for t in tests)


class TestVerifyBoundaryTestIntegrity:
    def test_returns_true_when_no_tests(self, tmp_path):
        assert verify_boundary_test_integrity(tmp_path) is True

    def test_returns_true_for_valid_tests(self, tmp_path):
        boundaries_dir = tmp_path / "tests" / "boundaries"
        boundaries_dir.mkdir(parents=True)
        test_file = boundaries_dir / "test_foo.py"
        test_file.write_text(
            "# ── IMMUTABLE BOUNDARY TEST ──\n"
            "@pytest.mark.boundary\n"
            "@pytest.mark.immutable\n"
            "def test_bar(): pass\n"
        )
        assert verify_boundary_test_integrity(tmp_path) is True

    def test_returns_false_for_missing_markers(self, tmp_path):
        boundaries_dir = tmp_path / "tests" / "boundaries"
        boundaries_dir.mkdir(parents=True)
        test_file = boundaries_dir / "test_foo.py"
        test_file.write_text("def test_bar(): pass\n")
        assert verify_boundary_test_integrity(tmp_path) is False

    def test_handles_corrupt_files(self, tmp_path):
        boundaries_dir = tmp_path / "tests" / "boundaries"
        boundaries_dir.mkdir(parents=True)
        test_file = boundaries_dir / "test_bad.py"
        test_file.write_text("\xff\xfe")  # non-UTF-8
        # Should not crash
        result = verify_boundary_test_integrity(tmp_path)
        assert result is False
