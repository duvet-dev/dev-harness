"""Repo-scoped filesystem tool for harness agents.

Provides sandboxed read/write/list/exists operations on the repository
root. Enforces path-escape protection, file size limits, per-file write
locking, and per-agent permission boundaries.

Wave 13 — Agent Read/Write Tool.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any


class SecurityError(Exception):
    """Raised when a path would escape the repository root."""


class ToolPermissionError(Exception):
    """Raised when an agent tries to write without permission."""


class ToolFileSizeError(Exception):
    """Raised when a file exceeds the size limit."""


class ToolError(Exception):
    """Generic tool error."""


class RepoTool:
    """Sandboxed filesystem tool for agent access to the repository.

    All paths are relative to the repository root. The tool enforces:

    - **Path escaping prevention:** resolves every path and verifies it
      stays within the repo root. Symlink traversal is also checked.
    - **File size limits:** :attr:`max_read_bytes` and
      :attr:`max_write_bytes` guard against token-bombing and oversized
      output.
    - **Per-file write locking:** concurrent writes to the same path are
      serialised via :class:`threading.Lock`.
    - **Permission boundaries:** optional ``write_prefixes`` restrict
      which directories the agent may write to.
    """

    def __init__(
        self,
        repo_root: Path,
        write_allowed: bool = True,
        write_prefixes: list[str] | None = None,
        max_read_bytes: int = 1_048_576,
        max_write_bytes: int = 512_000,
        max_list_entries: int = 10_000,
    ):
        self._repo_root = repo_root.resolve()
        self._write_allowed = write_allowed
        self._write_prefixes = write_prefixes  # None = unrestricted
        self._max_read_bytes = max_read_bytes
        self._max_write_bytes = max_write_bytes
        self._max_list_entries = max_list_entries
        self._locks: dict[str, threading.Lock] = {}
        self._lock_cleanup_lock = threading.Lock()
        self._last_cleanup = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, path: str) -> str:
        """Read a file relative to the repo root.

        Raises:
            SecurityError: Path escapes the repo root.
            ToolFileSizeError: File exceeds ``max_read_bytes``.
            FileNotFoundError: File does not exist.
        """
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        content = resolved.read_text(encoding="utf-8", errors="replace")
        if len(content.encode("utf-8")) > self._max_read_bytes:
            raise ToolFileSizeError(
                f"File too large to read: {path} "
                f"({len(content)} bytes > {self._max_read_bytes} limit)"
            )
        return content

    def write(self, path: str, content: str) -> Path:
        """Write content to a file relative to the repo root.

        Creates parent directories automatically.

        Raises:
            ToolPermissionError: Agent does not have write permission.
            SecurityError: Path escapes the repo root.
            ToolFileSizeError: Content exceeds ``max_write_bytes``.
        """
        if not self._write_allowed:
            raise ToolPermissionError(
                "Agent does not have write permission for this tool."
            )

        resolved = self._resolve(path)
        self._check_write_prefix(resolved)

        if len(content.encode("utf-8")) > self._max_write_bytes:
            raise ToolFileSizeError(
                f"Content too large to write: {path} "
                f"({len(content)} bytes > {self._max_write_bytes} limit)"
            )

        resolved.parent.mkdir(parents=True, exist_ok=True)

        # Per-file write lock
        lock = self._get_or_create_lock(str(resolved))
        with lock:
            resolved.write_text(content, encoding="utf-8")

        return resolved

    def list(self, path: str = "") -> list[str]:
        """List the contents of a directory.

        Returns paths relative to the given directory.

        Raises:
            SecurityError: Path escapes the repo root.
            NotADirectoryError: Path is not a directory.
        """
        resolved = self._resolve(path or ".")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        entries = list(resolved.iterdir())
        if len(entries) > self._max_list_entries:
            raise ToolError(
                f"Directory too large to list: {path} "
                f"({len(entries)} entries > {self._max_list_entries} limit)"
            )

        return sorted(
            str(e.relative_to(resolved)) for e in entries
        )

    def exists(self, path: str) -> bool:
        """Check whether a path exists (file or directory)."""
        try:
            resolved = self._resolve(path)
            return resolved.exists()
        except SecurityError:
            return False

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    @property
    def repo_root(self) -> Path:
        """The repository root to which access is sandboxed."""
        return self._repo_root

    @property
    def write_allowed(self) -> bool:
        """Whether the agent can write files via this tool."""
        return self._write_allowed

    @property
    def write_prefixes(self) -> list[str] | None:
        """Directories the agent may write to (None = unrestricted)."""
        return self._write_prefixes

    def tool_spec(self) -> dict[str, Any]:
        """Return a provider-agnostic tool specification for LLM APIs.

        This spec can be transformed into OpenAI tools format,
        Anthropic tool format, etc. See :meth:`to_openai_tools`.
        """
        return {
            "type": "function",
            "function": {
                "name": "repo_tool",
                "description": (
                    "Read, write, list, or check existence of files "
                    "in the project repository. All paths are relative "
                    "to the repository root."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write", "list", "exists"],
                            "description": "The operation to perform.",
                        },
                        "path": {
                            "type": "string",
                            "description": (
                                "File or directory path relative to "
                                "the repository root."
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": (
                                "Content to write (required only for "
                                "the 'write' operation)."
                            ),
                        },
                    },
                    "required": ["operation", "path"],
                },
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        """Resolve a user-supplied path relative to the repo root.

        Raises:
            SecurityError: If the resolved path escapes the repo root,
                whether via ``..``, absolute paths, or symlink traversal.
        """
        raw = (self._repo_root / path).resolve(strict=False)
        if not str(raw).startswith(str(self._repo_root) + "/") and raw != self._repo_root:
            raise SecurityError(
                f"Path escapes repository root: {path!r} "
                f"(resolved to {raw})"
            )
        return raw

    def _check_write_prefix(self, path: Path) -> None:
        """Verify the path is under an allowed write prefix."""
        if self._write_prefixes is None:
            return  # unrestricted

        for prefix in self._write_prefixes:
            prefix_resolved = (self._repo_root / prefix).resolve()
            if str(path).startswith(str(prefix_resolved) + "/") or path == prefix_resolved:
                return

        raise ToolPermissionError(
            f"Write not allowed at {path.relative_to(self._repo_root)}. "
            f"Allowed prefixes: {self._write_prefixes}"
        )

    def _get_or_create_lock(self, resolved_path: str) -> threading.Lock:
        """Get or create a per-file write lock."""
        now = time.monotonic()
        if now - self._last_cleanup > 30.0:
            self._cleanup_stale_locks()

        with self._lock_cleanup_lock:
            if resolved_path not in self._locks:
                self._locks[resolved_path] = threading.Lock()
            return self._locks[resolved_path]

    def _cleanup_stale_locks(self) -> None:
        """Remove locks for files that no longer exist on disk."""
        with self._lock_cleanup_lock:
            stale = [
                path
                for path in self._locks
                if not Path(path).exists()
            ]
            for path in stale:
                del self._locks[path]
            self._last_cleanup = time.monotonic()

    # ------------------------------------------------------------------
    # OpenAI / Anthropic tool format converters
    # ------------------------------------------------------------------

    @staticmethod
    def to_openai_tools(tool_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert an internal tool spec to OpenAI tools format.

        The internal ``tool_spec()`` is already close to OpenAI's format,
        so this is a passthrough in practice.
        """
        return [tool_spec]

    @staticmethod
    def system_prompt_preamble(tool_name: str = "repo_tool") -> str:
        """Return a system-prompt preamble describing the tool.

        This is the text version of the tool description, injected into
        the system prompt when function-calling APIs are not available.
        The model is instructed to call the tool by producing structured
        invocations in its response.
        """
        return (
            "\n\n--- Filesystem Tool ---\n"
            f"You have access to a filesystem tool called `{tool_name}`. "
            "You can use it to read and write files in the repository. "
            "To invoke it, produce a JSON block with this format:\n"
            "\n"
            "```tool\n"
            '{"operation": "read", "path": "src/main.py"}\n'
            "```\n"
            "\n"
            "```tool\n"
            '{"operation": "write", "path": "src/main.py", '
            '"content": "print(\'hello\')"}\n'
            "```\n"
            "\n"
            "```tool\n"
            '{"operation": "list", "path": ".harness/engagements/"}\n'
            "```\n"
            "\n"
            "```tool\n"
            '{"operation": "exists", "path": "src/main.py"}\n'
            "```\n"
            "\n"
            "All paths are relative to the repository root. "
            "You cannot escape the repository. "
            "Use this tool to persist plans, designs, code, tests, "
            "and documentation as you produce them. "
            "Do not rely on chat memory — write it down.\n"
            "--- End Filesystem Tool ---\n\n"
        )

    @staticmethod
    def parse_tool_blocks(text: str) -> list[dict[str, Any]]:
        """Parse ````tool``` JSON blocks from an LLM response.

        This is the non-function-calling fallback: when the LLM cannot
        use native function calling, it embeds tool invocations as
        fenced JSON blocks labeled ``tool``.
        """
        import re

        calls: list[dict[str, Any]] = []
        pattern = re.compile(
            r"```tool\s*\n(.*?)```", re.DOTALL
        )
        for match in pattern.finditer(text):
            block = match.group(1).strip()
            try:
                import json
                call = json.loads(block)
                if isinstance(call, dict) and "operation" in call:
                    calls.append(call)
            except json.JSONDecodeError:
                continue
        return calls
