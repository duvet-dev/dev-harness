"""Filesystem abstraction protocol.

Defines a Filesystem protocol that abstracts all direct
filesystem I/O operations. Production implementations use the
real filesystem; test implementations use in-memory fakes.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Optional, Protocol, TextIO


class FileSystem(Protocol):
    """Abstract filesystem operations.

    Following the I/O abstraction pattern, all direct filesystem
    calls (open, read, write, mkdir, exists) should go through
    this protocol.
    """

    def exists(self, path: Path) -> bool: ...

    def is_dir(self, path: Path) -> bool: ...

    def is_file(self, path: Path) -> bool: ...

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None: ...

    def read_text(self, path: Path, encoding: str = "utf-8") -> str: ...

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None: ...

    def read_bytes(self, path: Path) -> bytes: ...

    def write_bytes(self, path: Path, content: bytes) -> None: ...

    def unlink(self, path: Path, missing_ok: bool = False) -> None: ...

    def rename(self, src: Path, dst: Path) -> None: ...

    def iterdir(self, path: Path) -> list[Path]: ...

    def glob(self, path: Path, pattern: str) -> list[Path]: ...

    def open(self, path: Path, mode: str = "r") -> TextIO | BinaryIO: ...


class RealFileSystem:
    """Production filesystem that delegates to pathlib/stdlib.

    This is the default implementation used in production code.
    """

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        return path.read_text(encoding=encoding)

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        path.write_text(content, encoding=encoding)

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def write_bytes(self, path: Path, content: bytes) -> None:
        path.write_bytes(content)

    def unlink(self, path: Path, missing_ok: bool = False) -> None:
        path.unlink(missing_ok=missing_ok)

    def rename(self, src: Path, dst: Path) -> None:
        src.rename(dst)

    def iterdir(self, path: Path) -> list[Path]:
        return list(path.iterdir())

    def glob(self, path: Path, pattern: str) -> list[Path]:
        return list(path.glob(pattern))

    def open(self, path: Path, mode: str = "r") -> TextIO | BinaryIO:
        return open(path, mode)  # noqa: SIM115
