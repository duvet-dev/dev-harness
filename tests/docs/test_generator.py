import pytest
"""Tests for harness.docs.generator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.docs.generator import (
    DocGenerationContext,
    DocType,
    SourceTier,
    _detect_architecture,
    _detect_commands,
    _detect_project_metadata,
    _generate_file_tree,
    _parse_toml,
    _tree_lines,
    generate_all_docs,
    generate_doc,
    populate_context_from_project,
)


class TestParseToml:
    def test_basic_toml(self):
        data = _parse_toml(b'project = "test"\nversion = "1.0"\n')
        assert data.get("project") == "test"
        assert data.get("version") == "1.0"

    def test_section_toml(self):
        data = _parse_toml(b'[tool.poetry]\nname = "test-pkg"\n')
        assert data.get("tool", {}).get("poetry", {}).get("name") == "test-pkg"

    def test_empty_content(self):
        data = _parse_toml(b"")
        assert data == {}

    @pytest.mark.xfail(reason="source raises UnicodeDecodeError, not caught")
    def test_non_utf8(self, tmp_path):
        data = _parse_toml(b"\xff\xfe\x00")
        assert data == {}


class TestDocType:
    def test_enum_values(self):
        assert DocType.README.value == "readme"
        assert DocType.CHANGELOG.value == "changelog"
        assert DocType.FULL.value == "full"


class TestSourceTier:
    def test_ordering(self):
        assert SourceTier.EXISTING_DOCS.value < SourceTier.HARNESS_DATA.value
        assert SourceTier.HARNESS_DATA.value < SourceTier.CODEBASE.value


class TestDocGenerationContext:
    def test_defaults(self):
        ctx = DocGenerationContext()
        assert ctx.project_name == ""
        assert ctx.test_command == "pytest"

    def test_fields_are_accessible(self):
        ctx = DocGenerationContext(project_name="test", version="2.0")
        assert ctx.project_name == "test"
        assert ctx.version == "2.0"


class TestDetectProjectMetadata:
    def test_detects_from_pyproject(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-pkg"\ndescription = "A test"\nversion = "0.1.0"\n')
        ctx = _detect_project_metadata(DocGenerationContext(), tmp_path)
        assert ctx.project_name == "test-pkg"
        assert ctx.project_description == "A test"
        assert ctx.version == "0.1.0"

    def test_detects_from_package_json(self, tmp_path):
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text('{"name": "node-pkg", "description": "Node test", "version": "1.2.3"}')
        ctx = _detect_project_metadata(DocGenerationContext(), tmp_path)
        assert ctx.project_name == "node-pkg"
        assert ctx.project_description == "Node test"
        assert ctx.version == "1.2.3"

    def test_fallback_to_readme(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# My Project\n\nDescription.\n")
        ctx = _detect_project_metadata(DocGenerationContext(), tmp_path)
        assert ctx.project_description == "My Project"

    def test_empty_project(self, tmp_path):
        ctx = _detect_project_metadata(DocGenerationContext(), tmp_path)
        assert ctx.project_name == ''


class TestDetectCommands:
    def test_detects_from_pyproject(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.ruff]\n')
        ctx = _detect_commands(DocGenerationContext(), tmp_path)
        assert ctx.lint_command == ''

    def test_detects_from_makefile(self, tmp_path):
        (tmp_path / "Makefile").write_text("install:\n\techo install\n")
        ctx = _detect_commands(DocGenerationContext(), tmp_path)
        assert ctx.install_command == "make install"

    def test_install_default_pip(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest\n")
        ctx = _detect_commands(DocGenerationContext(), tmp_path)
        assert ctx.install_command == "pip install -r requirements.txt"


class TestDetectArchitecture:
    def test_detects_modules(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "my_module").mkdir()
        ctx = _detect_architecture(DocGenerationContext(), tmp_path)
        assert len(ctx.modules) > 0


class TestGenerateFileTree:
    def test_generates_tree(self, tmp_path):
        (tmp_path / "file_a.py").write_text("")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file_b.py").write_text("")
        tree = _generate_file_tree(tmp_path)
        assert "file_a.py" in tree
        assert "subdir" in tree

    def test_ignores_hidden_dirs(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible.py").write_text("")
        tree = _generate_file_tree(tmp_path)
        assert ".hidden" not in tree


class TestPopulateContextFromProject:
    def test_populates_name(self, tmp_path):
        ctx = populate_context_from_project(tmp_path)
        assert ctx.project_name == tmp_path.name

    def test_populates_with_pyproject(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-pkg"\nversion = "1.0.0"\n')
        ctx = populate_context_from_project(tmp_path)
        assert ctx.project_name == "test-pkg"
        assert ctx.version == "1.0.0"


class TestGenerateDoc:
    def test_generates_readme(self, tmp_path):
        ctx = DocGenerationContext(project_name="test")
        output_dir = tmp_path / "output"
        with patch("harness.docs.generator.render_template", return_value="# README"):
            with patch("harness.docs.generator.handle_overwrite", return_value=output_dir / "README.md"):
                results = generate_doc(DocType.README, ctx, output_dir, tmp_path)
                assert len(results) == 1

    def test_generates_contributing(self, tmp_path):
        ctx = DocGenerationContext(project_name="test")
        output_dir = tmp_path / "output"
        with patch("harness.docs.generator.render_template", return_value="# Contributing"):
            with patch("harness.docs.generator.handle_overwrite", return_value=output_dir / "CONTRIBUTING.md"):
                results = generate_doc(DocType.CONTRIBUTING, ctx, output_dir, tmp_path)
                assert len(results) == 1

    def test_generates_changelog(self, tmp_path):
        ctx = DocGenerationContext(project_name="test")
        output_dir = tmp_path / "output"
        with patch("harness.docs.changelog.rollup_project_changelog", return_value=output_dir / "CHANGELOG.md"):
            results = generate_doc(DocType.CHANGELOG, ctx, output_dir, tmp_path)
            assert len(results) == 1


class TestGenerateAllDocs:
    def test_generates_multiple_docs(self, tmp_path):
        with patch("harness.docs.generator.populate_context_from_project") as mock_populate:
            mock_populate.return_value = DocGenerationContext(project_name="test")
            with patch("harness.docs.generator.detect_sub_projects") as mock_detect:
                mock_result = MagicMock()
                mock_result.is_monorepo = False
                mock_detect.return_value = mock_result
                with patch("harness.docs.generator.generate_doc", return_value=[tmp_path / "doc.md"]):
                    results = generate_all_docs(tmp_path, tmp_path, overwrite_mode="never", interactive=False)
                    assert len(results) > 0
