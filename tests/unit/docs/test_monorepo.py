"""Tests for harness.docs.monorepo."""

from pathlib import Path

import pytest

from harness.docs.monorepo import (
    SubProject,
    MonorepoResult,
    _detect_language,
    _find_workspace_markers,
    _has_subproject_directories,
    detect_sub_projects,
    relationship_map,
)


class TestSubProject:
    def test_defaults(self):
        sp = SubProject(name="test", root=Path("packages/test"))
        assert sp.language is None
        assert sp.description == ""


class TestMonorepoResult:
    def test_defaults(self):
        result = MonorepoResult()
        assert result.is_monorepo is False
        assert result.sub_projects == []
        assert result.errors == []


class TestDetectLanguage:
    def test_python_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        assert _detect_language(tmp_path) == "Python"

    def test_python_setup_py(self, tmp_path):
        (tmp_path / "setup.py").write_text("")
        assert _detect_language(tmp_path) == "Python"

    def test_javascript(self, tmp_path):
        (tmp_path / "package.json").write_text("")
        assert _detect_language(tmp_path) == "JavaScript/TypeScript"

    def test_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("")
        assert _detect_language(tmp_path) == "Rust"

    def test_unknown(self, tmp_path):
        assert _detect_language(tmp_path) is None


class TestFindWorkspaceMarkers:
    def test_finds_pnpm(self, tmp_path):
        (tmp_path / "pnpm-workspace.yaml").write_text("")
        found = _find_workspace_markers(tmp_path)
        assert len(found) == 1

    def test_finds_go_work(self, tmp_path):
        (tmp_path / "go.work").write_text("")
        found = _find_workspace_markers(tmp_path)
        assert len(found) == 1

    def test_returns_empty(self, tmp_path):
        assert _find_workspace_markers(tmp_path) == []


class TestHasSubprojectDirectories:
    def test_detects_packages_dir(self, tmp_path):
        pkg_dir = tmp_path / "packages" / "pkg_a"
        pkg_dir.mkdir(parents=True)
        candidates = _has_subproject_directories(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].name == "pkg_a"

    def test_detects_apps_dir(self, tmp_path):
        app_dir = tmp_path / "apps" / "web"
        app_dir.mkdir(parents=True)
        candidates = _has_subproject_directories(tmp_path)
        assert len(candidates) == 1
        assert candidates[0].name == "web"

    def test_skips_dotfiles(self, tmp_path):
        dot_dir = tmp_path / "packages" / ".hidden"
        dot_dir.mkdir(parents=True)
        candidates = _has_subproject_directories(tmp_path)
        assert len(candidates) == 0

    def test_returns_empty_when_no_subdirs(self, tmp_path):
        assert _has_subproject_directories(tmp_path) == []


class TestDetectSubProjects:
    def test_detects_via_workspace_markers(self, tmp_path):
        (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
        (tmp_path / "packages" / "pkg_a").mkdir(parents=True)
        (tmp_path / "packages" / "pkg_a" / "package.json").write_text("{}")
        result = detect_sub_projects(tmp_path)
        assert result.is_monorepo is True
        assert len(result.sub_projects) >= 1
        assert "Workspace detected" in result.relationships

    def test_detects_via_directory_convention(self, tmp_path):
        (tmp_path / "packages" / "cli").mkdir(parents=True)
        (tmp_path / "packages" / "cli" / "package.json").write_text("{}")
        (tmp_path / "packages" / "core").mkdir(parents=True)
        (tmp_path / "packages" / "core" / "setup.py").write_text("")
        result = detect_sub_projects(tmp_path)
        assert result.is_monorepo
        assert len(result.sub_projects) == 2

    def test_single_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        result = detect_sub_projects(tmp_path)
        assert result.is_monorepo is False
        assert len(result.sub_projects) == 1

    def test_empty_project(self, tmp_path):
        result = detect_sub_projects(tmp_path)
        assert result.is_monorepo is False
        assert result.sub_projects == []


class TestRelationshipMap:
    def test_single_project(self):
        result = relationship_map([SubProject(name="test", root=Path("."))])
        assert "Single project" in result

    def test_multiple_projects(self):
        subs = [
            SubProject(name="Core", root=Path("packages/core"), language="Python"),
            SubProject(name="Web", root=Path("apps/web"), language="JavaScript/TypeScript"),
        ]
        result = relationship_map(subs)
        assert "2 sub-projects" in result
        assert "Core" in result
        assert "Web" in result
