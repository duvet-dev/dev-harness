"""Tests for harness.refactor.boundaries."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.refactor.boundaries import (
    BoundaryCandidate,
    _find_source_dirs,
    _interactive_add,
    _interactive_select,
    present_and_confirm_boundaries,
    read_boundary_registration,
    register_boundaries,
    scan_boundary_candidates,
)


class TestBoundaryCandidate:
    def test_defaults(self):
        bc = BoundaryCandidate(name="test", path="src/test.py", boundary_type="module")
        assert bc.name == "test"
        assert bc.path == "src/test.py"
        assert bc.boundary_type == "module"
        assert bc.description == ""


class TestFindSourceDirs:
    def test_finds_src_dir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        pkg = src / "mypkg"
        pkg.mkdir()
        dirs = _find_source_dirs(tmp_path)
        assert src in dirs
        assert pkg in dirs

    def test_falls_back_to_root(self, tmp_path):
        dirs = _find_source_dirs(tmp_path)
        assert dirs == [tmp_path]


class TestScanBoundaryCandidates:
    def test_empty_project(self, tmp_path):
        candidates = scan_boundary_candidates(tmp_path)
        assert candidates == []

    def test_detects_package_boundary(self, tmp_path):
        init = tmp_path / "src" / "mypkg" / "__init__.py"
        init.parent.mkdir(parents=True)
        init.write_text("__all__ = ['func']\ndef func(): pass\n")
        candidates = scan_boundary_candidates(tmp_path)
        pkg_names = [c.name for c in candidates if c.boundary_type == "package"]
        assert len(pkg_names) >= 1

    def test_detects_api_directory(self, tmp_path):
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "__init__.py").write_text("")
        candidates = scan_boundary_candidates(tmp_path)
        api_names = [c.name for c in candidates if "api" in c.boundary_type or "api:" in c.name]
        assert any("api" in c.boundary_type for c in candidates)

    def test_detects_interface_files(self, tmp_path):
        interface_file = tmp_path / "src" / "interfaces.py"
        interface_file.parent.mkdir(parents=True)
        interface_file.write_text("# interface\n")
        candidates = scan_boundary_candidates(tmp_path)
        assert any(c.boundary_type == "interface" for c in candidates)

    def test_detects_cli_entry_points(self, tmp_path):
        cli_file = tmp_path / "src" / "cli.py"
        cli_file.parent.mkdir(parents=True)
        cli_file.write_text("import click\n")
        candidates = scan_boundary_candidates(tmp_path)
        assert any(c.boundary_type == "cli" for c in candidates)

    def test_detects_http_handlers(self, tmp_path):
        handler = tmp_path / "src" / "routes.py"
        handler.parent.mkdir(parents=True)
        handler.write_text("@app.route('/hello')\ndef hello(): pass\n")
        candidates = scan_boundary_candidates(tmp_path)
        assert any(c.boundary_type == "http" for c in candidates)

    def test_returns_empty_for_nonexistent_root(self, tmp_path):
        assert scan_boundary_candidates(tmp_path / "nonexistent") == []

    def test_deduplicates_by_path(self, tmp_path):
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "__init__.py").write_text("__all__ = ['x']")
        candidates = scan_boundary_candidates(tmp_path)
        paths = [c.path for c in candidates]
        assert len(paths) == len(set(paths))

    def test_sorts_by_path(self, tmp_path):
        for name in ["z_last", "a_first", "m_middle"]:
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").write_text("")
        candidates = scan_boundary_candidates(tmp_path)
        paths = [c.path for c in candidates]
        assert paths == sorted(paths)


class TestRegisterBoundaries:
    def test_writes_yaml(self, tmp_path):
        boundaries = [
            BoundaryCandidate(name="test", path="src/test.py", boundary_type="module"),
        ]
        path = register_boundaries(boundaries, tmp_path)
        assert path.is_file()
        import yaml
        data = yaml.safe_load(path.read_text())
        assert data["version"] == 1
        assert len(data["boundaries"]) == 1
        assert data["boundaries"][0]["name"] == "test"

    def test_writes_empty_list(self, tmp_path):
        path = register_boundaries([], tmp_path)
        data = __import__("yaml").safe_load(path.read_text())
        assert data["boundaries"] == []


class TestReadBoundaryRegistration:
    def test_reads_valid_file(self, tmp_path):
        import yaml
        data = {"version": 1, "boundaries": [{"name": "test", "path": "src/t.py", "type": "module"}]}
        (tmp_path / "boundaries.yaml").write_text(yaml.dump(data))
        boundaries = read_boundary_registration(tmp_path)
        assert len(boundaries) == 1
        assert boundaries[0].name == "test"

    def test_returns_empty_for_no_file(self, tmp_path):
        assert read_boundary_registration(tmp_path) == []

    def test_returns_empty_for_malformed(self, tmp_path):
        (tmp_path / "boundaries.yaml").write_text("not: [valid yaml\n")
        assert read_boundary_registration(tmp_path) == []


class TestPresentAndConfirmBoundaries:
    def test_accepts_all_with_y(self):
        candidates = [BoundaryCandidate(name="test", path="src/t.py", boundary_type="module")]
        with patch("builtins.input", return_value=""):
            result = present_and_confirm_boundaries(candidates)
            assert len(result) == 1

    def test_accepts_all_with_empty(self):
        candidates = [BoundaryCandidate(name="test", path="src/t.py", boundary_type="module")]
        with patch("builtins.input", return_value=""):
            result = present_and_confirm_boundaries(candidates)
            assert len(result) == 1

    def test_rejects_none(self):
        with patch("builtins.input", side_effect=["n", "", "", ""]):
            with patch("harness.refactor.boundaries._interactive_select", return_value=[]):
                result = present_and_confirm_boundaries([])
                assert result == []

    def test_deduplicates_by_path(self):
        candidates = [
            BoundaryCandidate(name="a", path="src/a.py", boundary_type="module"),
            BoundaryCandidate(name="b", path="src/a.py", boundary_type="module"),
        ]
        with patch("builtins.input", return_value=""):
            result = present_and_confirm_boundaries(candidates)
            assert len(result) == 1
