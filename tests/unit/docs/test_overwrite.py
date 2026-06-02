"""Tests for harness.docs.overwrite."""

from pathlib import Path

import pytest

from harness.docs.overwrite import (
    OverwriteMode,
    _backup_file,
    _backup_path,
    _diff_preview,
    _prompt_user,
    _prompt_with_diff,
    handle_overwrite,
    resolve_overwrite,
)


class TestOverwriteMode:
    def test_enum_values(self):
        assert OverwriteMode.NEVER.value == "never"
        assert OverwriteMode.ASK.value == "ask"
        assert OverwriteMode.ALL.value == "all"


class TestBackupPath:
    def test_creates_timestamped_dir(self, tmp_path):
        file_path = tmp_path / "docs" / "README.md"
        bp = _backup_path(tmp_path, file_path)
        assert bp.parent.parent.name.startswith("20")  # timestamp dir name
        assert bp.name == "README.md"

    def test_preserves_relative_path(self, tmp_path):
        nested = tmp_path / "subdir" / "file.md"
        bp = _backup_path(tmp_path, nested)
        assert "subdir" in str(bp)


class TestBackupFile:
    def test_copies_file(self, tmp_path):
        src = tmp_path / "test.md"
        src.write_text("content")
        bp = _backup_file(src, tmp_path)
        assert bp.is_file()
        assert bp.read_text() == "content"

    def test_creates_parent_dir(self, tmp_path):
        src = tmp_path / "docs" / "readme.md"
        src.parent.mkdir()
        src.write_text("data")
        bp = _backup_file(src, tmp_path)
        assert bp.is_file()


class TestDiffPreview:
    def test_shows_diff_for_different_content(self):
        existing = "line1\nline2\n"
        proposed = "line1\nmodified\n"
        diff = _diff_preview(existing, proposed, "test.md")
        assert "test.md" in diff
        assert "-line2" in diff
        assert "+modified" in diff

    def test_empty_diff_for_identical(self):
        content = "same\n"
        diff = _diff_preview(content, content, "f.md")
        assert diff.strip() == "" or "f.md" in diff


class TestHandleOverwrite:
    def test_never_mode_skips_existing(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_text("existing")
        result = handle_overwrite(path, "new content", tmp_path, OverwriteMode.NEVER)
        assert result is None
        assert path.read_text() == "existing"

    def test_never_mode_writes_new(self, tmp_path):
        path = tmp_path / "new.md"
        result = handle_overwrite(path, "new content", tmp_path, OverwriteMode.NEVER)
        assert result == path
        assert path.read_text() == "new content"

    def test_all_mode_backs_up_and_overwrites(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_text("old")
        result = handle_overwrite(path, "new", tmp_path, OverwriteMode.ALL)
        assert result == path
        assert path.read_text() == "new"
        # Verify backup exists
        backup_root = tmp_path / ".harness" / "docs-backups"
        backup_files = list(backup_root.rglob("doc.md"))
        assert len(backup_files) > 0

    def test_all_mode_writes_new_file(self, tmp_path):
        path = tmp_path / "new_file.md"
        result = handle_overwrite(path, "content", tmp_path, OverwriteMode.ALL)
        assert result == path
        assert path.read_text() == "content"

    def test_ask_mode_writes_new_file(self, tmp_path):
        path = tmp_path / "ask_new.md"
        result = handle_overwrite(path, "content", tmp_path, OverwriteMode.ASK, interactive=False)
        assert result == path
        assert path.read_text() == "content"

    def test_ask_mode_skips_existing_when_non_interactive(self, tmp_path):
        path = tmp_path / "existing.md"
        path.write_text("old")
        result = handle_overwrite(path, "new", tmp_path, OverwriteMode.ASK, interactive=False)
        assert result is None
        assert path.read_text() == "old"

    def test_ask_mode_returns_path_when_identical(self, tmp_path):
        path = tmp_path / "same.md"
        path.write_text("content")
        result = handle_overwrite(path, "content", tmp_path, OverwriteMode.ASK, interactive=False)
        # Content identical — returns path without overwriting
        assert result == path

    def test_backup_root_uses_docs_backups(self, tmp_path):
        path = tmp_path / "test.md"
        path.write_text("data")
        handle_overwrite(path, "new", tmp_path, OverwriteMode.ALL)
        backup_dir = tmp_path / ".harness" / "docs-backups"
        assert backup_dir.is_dir()


class TestResolveOverwrite:
    def test_never_returns_false(self, tmp_path):
        path = tmp_path / "file.md"
        path.write_text("old")
        result = resolve_overwrite(path, tmp_path, OverwriteMode.NEVER)
        assert result is False

    def test_all_mode_returns_true(self, tmp_path):
        path = tmp_path / "file.md"
        path.write_text("old")
        result = resolve_overwrite(path, tmp_path, OverwriteMode.ALL)
        assert result is True
        # Should have created a backup
        backup_dir = tmp_path / ".harness" / "docs-backups"
        assert backup_dir.is_dir()

    def test_returns_true_for_new_file(self, tmp_path):
        path = tmp_path / "new.md"
        result = resolve_overwrite(path, tmp_path, OverwriteMode.NEVER)
        assert result is True

    def test_ask_mode_prompts(self, tmp_path):
        path = tmp_path / "ask.md"
        path.write_text("old")
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("builtins.input", lambda _: "y")
            result = resolve_overwrite(path, tmp_path, OverwriteMode.ASK)
            assert result is True
