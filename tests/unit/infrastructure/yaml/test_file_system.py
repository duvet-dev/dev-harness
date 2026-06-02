"""Tests for infrastructure/yaml/file_system.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.infrastructure.yaml.file_system import RealFileSystem


# ── FileSystem protocol ─────────────────────────────────────────────────────


class TestFileSystemProtocol:
    def test_protocol_methods_exist(self):
        """Verify all expected methods on the protocol."""
        import inspect
        from harness.infrastructure.yaml.file_system import FileSystem

        expected = [
            "exists", "is_dir", "is_file", "mkdir",
            "read_text", "write_text", "read_bytes", "write_bytes",
            "unlink", "rename", "iterdir", "glob", "open",
        ]
        for m in expected:
            assert hasattr(FileSystem, m), f"Missing protocol method: {m}"
            assert callable(getattr(FileSystem, m)), f"{m} not callable"


# ── RealFileSystem ──────────────────────────────────────────────────────────


class TestRealFileSystem:
    @pytest.fixture
    def fs(self) -> RealFileSystem:
        return RealFileSystem()

    def test_exists(self, fs, tmp_path):
        f = tmp_path / "test.txt"
        assert not fs.exists(f)
        f.write_text("hello")
        assert fs.exists(f)

    def test_is_dir(self, fs, tmp_path):
        assert fs.is_dir(tmp_path)
        assert not fs.is_dir(tmp_path / "nope")

    def test_is_file(self, fs, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("")
        assert fs.is_file(f)
        assert not fs.is_file(tmp_path)

    def test_mkdir(self, fs, tmp_path):
        d = tmp_path / "newdir"
        fs.mkdir(d)
        assert d.exists()

    def test_mkdir_parents(self, fs, tmp_path):
        d = tmp_path / "a" / "b" / "c"
        fs.mkdir(d, parents=True)
        assert d.exists()

    def test_read_write_text(self, fs, tmp_path):
        f = tmp_path / "data.txt"
        fs.write_text(f, "hello world")
        assert fs.read_text(f) == "hello world"

    def test_read_write_bytes(self, fs, tmp_path):
        f = tmp_path / "data.bin"
        data = b"\x00\x01\x02"
        fs.write_bytes(f, data)
        assert fs.read_bytes(f) == data

    def test_unlink(self, fs, tmp_path):
        f = tmp_path / "delete_me.txt"
        f.write_text("bye")
        fs.unlink(f)
        assert not f.exists()

    def test_unlink_missing_ok(self, fs, tmp_path):
        fs.unlink(tmp_path / "ghost.txt", missing_ok=True)  # no error

    def test_unlink_missing_raises_by_default(self, fs, tmp_path):
        with pytest.raises(FileNotFoundError):
            fs.unlink(tmp_path / "ghost.txt", missing_ok=False)

    def test_rename(self, fs, tmp_path):
        src = tmp_path / "old.txt"
        dst = tmp_path / "new.txt"
        src.write_text("rename me")
        fs.rename(src, dst)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "rename me"

    def test_iterdir(self, fs, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = fs.iterdir(tmp_path)
        assert len(entries) == 2

    def test_glob(self, fs, tmp_path):
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "data.yaml").write_text("")
        results = fs.glob(tmp_path, "*.json")
        assert len(results) == 1
        assert results[0].name == "data.json"

    def test_open(self, fs, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("file content")
        with fs.open(f) as fh:
            content = fh.read()
        assert content == "file content"

    def test_open_write_mode(self, fs, tmp_path):
        f = tmp_path / "write_test.txt"
        with fs.open(f, "w") as fh:
            fh.write("written")
        assert f.read_text() == "written"
