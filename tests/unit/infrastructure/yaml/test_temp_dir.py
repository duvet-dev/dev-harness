"""Tests for infrastructure/yaml/temp_dir.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.infrastructure.yaml.temp_dir import TempDirManager


class TestTempDirManager:
    def test_context_manager_creates_temp_dir(self):
        """Temp dir is created when entering the context."""
        with TempDirManager(prefix="test_harness_") as tmp:
            assert tmp.path.exists()
            assert tmp.path.is_dir()

    def test_cleanup_on_exit(self):
        """Temp dir is cleaned up on exit when cleanup=True."""
        path_ref: Path | None = None
        with TempDirManager(prefix="test_cleanup_") as tmp:
            path_ref = tmp.path
            assert path_ref.exists()
        assert not path_ref.exists()

    def test_no_cleanup_disabled(self):
        """Temp dir persists when cleanup=False."""
        path_ref: Path | None = None
        with TempDirManager(prefix="test_nocleanup_", cleanup=False) as tmp:
            path_ref = tmp.path
        assert path_ref and path_ref.exists()
        # Clean up ourselves
        import shutil
        shutil.rmtree(path_ref, ignore_errors=True)

    def test_custom_prefix(self):
        """Temp dir name starts with the given prefix."""
        with TempDirManager(prefix="my_custom_prefix_") as tmp:
            assert tmp.path.name.startswith("my_custom_prefix_")

    def test_custom_suffix(self):
        """Temp dir name ends with the given suffix."""
        with TempDirManager(suffix="_suffix") as tmp:
            assert tmp.path.name.endswith("_suffix")

    def test_custom_base_dir(self, tmp_path):
        """Temp dir is created in the specified base directory."""
        with TempDirManager(dir=str(tmp_path)) as tmp:
            assert str(tmp.path).startswith(str(tmp_path))

    def test_path_accessible_inside_context(self):
        """path property works inside the context manager."""
        with TempDirManager() as tmp:
            p = tmp.path
            assert isinstance(p, Path)

    def test_path_raises_outside_context(self):
        """path property raises RuntimeError outside context."""
        tmp = TempDirManager()
        with pytest.raises(RuntimeError, match="not yet entered"):
            _ = tmp.path

    def test_multiple_uses(self):
        """Can be used multiple times for different temp dirs."""
        paths: list[Path] = []
        for _ in range(3):
            with TempDirManager(prefix="multi_") as tmp:
                paths.append(tmp.path)
                assert tmp.path.exists()
        for p in paths:
            assert not p.exists()

    def test_exception_still_cleans_up(self):
        """Temp dir is cleaned up even if an exception occurs."""
        path_ref: Path | None = None
        with pytest.raises(ValueError, match="test exception"):
            with TempDirManager(prefix="test_exc_") as tmp:
                path_ref = tmp.path
                raise ValueError("test exception")
        assert path_ref and not path_ref.exists()
