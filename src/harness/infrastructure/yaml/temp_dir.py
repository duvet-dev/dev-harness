"""Temp directory manager.

Provides a ContextManager-based temporary directory with
optional cleanup. Wraps tempfile.mkdtemp for integration with
the I/O abstraction pattern.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class TempDirManager:
    """Context manager for temporary directories.

    Usage::

        with TempDirManager() as tmp:
            tmp_path = tmp.path
            # ... work with tmp_path ...
        # Directory is cleaned up on exit.

    Args:
        prefix: Prefix for the temp directory name.
        suffix: Suffix for the temp directory name.
        cleanup: If True (default), delete directory on exit.
        dir: Base directory for the temp directory. If None,
            uses system temp directory.
    """

    def __init__(
        self,
        prefix: str = "harness_",
        suffix: str = "",
        cleanup: bool = True,
        dir: str | None = None,
    ) -> None:
        self._prefix = prefix
        self._suffix = suffix
        self._cleanup = cleanup
        self._dir = dir
        self._path: Path | None = None

    @property
    def path(self) -> Path:
        """The temporary directory path.

        Raises:
            RuntimeError: If the context manager hasn't been entered.
        """
        if self._path is None:
            raise RuntimeError("TempDirManager not yet entered")
        return self._path

    def __enter__(self) -> TempDirManager:
        self._path = Path(
            tempfile.mkdtemp(prefix=self._prefix, suffix=self._suffix, dir=self._dir)
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: object | None = None,
    ) -> None:
        if self._cleanup and self._path is not None and self._path.exists():
            shutil.rmtree(self._path, ignore_errors=True)
        self._path = None
