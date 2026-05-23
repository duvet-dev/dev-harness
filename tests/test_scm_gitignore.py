"""Tests for harness.scm.gitignore."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.scm.gitignore import (
    DEFAULT_GITIGNORE,
    TEMPLATE_EXTENSIONS,
    get_default_gitignore,
    write_gitignore,
    suggest_dynamic_additions,
)


class TestGetDefaultGitignore:
    def test_returns_string(self):
        content = get_default_gitignore()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_includes_python_patterns(self):
        content = get_default_gitignore()
        assert "__pycache__/" in content
        assert "*.pyc" in content or "*.py[cod]" in content

    def test_includes_ide_patterns(self):
        content = get_default_gitignore()
        assert ".idea/" in content or ".vscode/" in content

    def test_includes_os_patterns(self):
        content = get_default_gitignore()
        assert ".DS_Store" in content
        assert "Thumbs.db" in content

    def test_backend_service_template(self):
        content = get_default_gitignore(template="backend-service")
        assert "*.pem" in content
        assert "*.key" in content

    def test_data_pipeline_template(self):
        content = get_default_gitignore(template="data-pipeline")
        assert "*.parquet" in content or "data/raw/" in content

    def test_library_template(self):
        content = get_default_gitignore(template="library")
        assert "*.so" in content
        assert "*.dll" in content

    def test_unknown_template_returns_default(self):
        content = get_default_gitignore(template="nonexistent")
        # Should not have backend-service specific entries
        assert "*.pem" not in content
        assert "*.key" not in content
        # But should have the default
        assert "__pycache__/" in content

    def test_ends_with_newline(self):
        content = get_default_gitignore()
        assert content.endswith("\n")


class TestWriteGitignore:
    def test_writes_file(self, tmp_path: Path):
        dest = tmp_path / ".gitignore"
        write_gitignore(dest)
        assert dest.is_file()
        content = dest.read_text()
        assert "__pycache__/" in content

    def test_raises_on_missing_parent_dir(self, tmp_path: Path):
        dest = tmp_path / "sub" / ".gitignore"
        with pytest.raises(FileNotFoundError):
            write_gitignore(dest)

    def test_writes_with_template(self, tmp_path: Path):
        dest = tmp_path / ".gitignore"
        write_gitignore(dest, template="library")
        content = dest.read_text()
        assert "*.so" in content


class TestSuggestDynamicAdditions:
    def test_returns_empty_for_empty_project(self, tmp_path: Path):
        suggestions = suggest_dynamic_additions(tmp_path)
        assert isinstance(suggestions, list)

    def test_detects_node_modules_in_subdir(self, tmp_path: Path):
        # The function checks for node_modules/ inside subdirectories
        sub = tmp_path / "frontend"
        sub.mkdir()
        (sub / "node_modules").mkdir()
        suggestions = suggest_dynamic_additions(tmp_path)
        assert "node_modules/" in suggestions

    def test_ignores_dot_directories(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        suggestions = suggest_dynamic_additions(tmp_path)
        assert "node_modules/" not in suggestions
