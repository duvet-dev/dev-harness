"""Tests for harness.agents.repo_tool — sandboxed filesystem tool.

Tests RepoTool read, write, list, exists operations with path security.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from harness.agents.repo_tool import (
    RepoTool,
    SecurityError,
    ToolPermissionError,
    ToolFileSizeError,
    ToolError,
)


class TestRepoTool:
    """Tests for RepoTool."""

    @pytest.fixture
    def repo(self, tmp_path):
        return RepoTool(repo_root=tmp_path)

    def test_read_file(self, repo, tmp_path):
        file = tmp_path / "hello.txt"
        file.write_text("Hello, World!")
        assert repo.read("hello.txt") == "Hello, World!"

    def test_read_nonexistent(self, repo):
        with pytest.raises(FileNotFoundError):
            repo.read("nonexistent.txt")

    def test_read_escapes_repo(self, repo):
        with pytest.raises(SecurityError):
            repo.read("../etc/passwd")

    def test_read_absolute_path(self, repo):
        with pytest.raises(SecurityError):
            repo.read("/etc/passwd")

    def test_write_file(self, repo, tmp_path):
        result = repo.write("output.txt", "New content")
        assert result == tmp_path / "output.txt"
        assert (tmp_path / "output.txt").read_text() == "New content"

    def test_write_creates_parent_dirs(self, repo, tmp_path):
        result = repo.write("subdir/nested/file.txt", "content")
        assert result.exists()
        assert result.read_text() == "content"

    def test_write_no_permission(self, tmp_path):
        repo = RepoTool(repo_root=tmp_path, write_allowed=False)
        with pytest.raises(ToolPermissionError, match="write permission"):
            repo.write("test.txt", "content")

    def test_write_exceeds_max_bytes(self, repo):
        content = "x" * 600_000  # > max_write_bytes (512000)
        with pytest.raises(ToolFileSizeError, match="too large"):
            repo.write("big.txt", content)

    def test_write_restricted_prefix(self, tmp_path):
        repo = RepoTool(
            repo_root=tmp_path,
            write_prefixes=["docs/"],
        )
        (tmp_path / "docs").mkdir()

        # Allowed
        result = repo.write("docs/readme.md", "# Docs")
        assert result.exists()

        # Not allowed
        with pytest.raises(ToolPermissionError, match="Write not allowed"):
            repo.write("src/main.py", "code")

    def test_write_unrestricted_prefix(self, tmp_path):
        repo = RepoTool(
            repo_root=tmp_path,
            write_prefixes=None,  # unrestricted
        )
        result = repo.write("anywhere.txt", "content")
        assert result.exists()

    def test_list_directory(self, repo, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "sub").mkdir()
        entries = repo.list("")
        assert "a.txt" in entries
        assert "b.txt" in entries
        assert "sub" in entries

    def test_list_subdirectory(self, repo, tmp_path):
        (tmp_path / "sub" / "nested.txt").parent.mkdir()
        (tmp_path / "sub" / "nested.txt").write_text("nested")
        entries = repo.list("sub")
        assert entries == ["nested.txt"]

    def test_list_nonexistent_directory(self, repo):
        with pytest.raises(NotADirectoryError):
            repo.list("nonexistent")

    def test_list_escapes_repo(self, repo):
        with pytest.raises(SecurityError):
            repo.list("../")

    def test_exists_true(self, repo, tmp_path):
        (tmp_path / "exists.txt").write_text("")
        assert repo.exists("exists.txt") is True

    def test_exists_false(self, repo):
        assert repo.exists("nonexistent.txt") is False

    def test_exists_escaped_path(self, repo):
        assert repo.exists("../etc/passwd") is False

    def test_concurrent_write_locking(self, repo, tmp_path):
        """Concurrent writes to same file are serialised via lock."""
        import concurrent.futures

        def writer(n):
            repo.write("shared.txt", f"Writer {n}\n")
            return n

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
            futures = [exe.submit(writer, i) for i in range(5)]
            concurrent.futures.wait(futures)

        # File should exist and have content from one of the writers
        assert (tmp_path / "shared.txt").exists()

    def test_tool_spec_structure(self, repo):
        spec = repo.tool_spec()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "repo_tool"
        assert "operation" in spec["function"]["parameters"]["properties"]

    def test_to_openai_tools(self):
        tool_spec = {"function": {"name": "repo_tool"}}
        spec = RepoTool.to_openai_tools(tool_spec)
        assert len(spec) == 1
        assert spec[0]["function"]["name"] == "repo_tool"

    def test_system_prompt_preamble(self):
        prompt = RepoTool.system_prompt_preamble(tool_name="repo_tool")
        assert "repo_tool" in prompt
        assert "Filesystem Tool" in prompt
        assert "```tool" in prompt
        assert "operation" in prompt

    def test_parse_tool_blocks(self):
        text = (
            "Some text\n"
            "```tool\n"
            '{"operation": "read", "path": "file.py"}\n'
            "```\n"
            "More text\n"
            "```tool\n"
            '{"operation": "write", "path": "out.py", "content": "code"}\n'
            "```\n"
        )
        calls = RepoTool.parse_tool_blocks(text)
        assert len(calls) == 2
        assert calls[0]["operation"] == "read"
        assert calls[0]["path"] == "file.py"
        assert calls[1]["operation"] == "write"

    def test_parse_tool_blocks_ignores_invalid(self):
        text = (
            "```tool\n"
            "not valid json\n"
            "```\n"
            "```tool\n"
            '{"operation": "read", "path": "f.py"}\n'
            "```\n"
        )
        calls = RepoTool.parse_tool_blocks(text)
        assert len(calls) == 1

    def test_parse_tool_blocks_empty(self):
        assert RepoTool.parse_tool_blocks("No tool calls here") == []

    def test_properties(self, repo, tmp_path):
        assert repo.repo_root == tmp_path.resolve()
        assert repo.write_allowed is True
        assert repo.write_prefixes is None


class TestRepoToolSymlinkSecurity:
    """Tests that symlink traversal is blocked."""

    @pytest.fixture
    def repo(self, tmp_path):
        return RepoTool(repo_root=tmp_path)

    def test_symlink_escape_blocked(self, repo, tmp_path):
        """Symlink pointing outside repo should be blocked."""
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")

        link = tmp_path / "link.txt"
        link.symlink_to(outside)

        with pytest.raises(SecurityError):
            repo.read("link.txt")
