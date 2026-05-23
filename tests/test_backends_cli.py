"""Tests for harness.agents.backends.cli_backend — CLI subprocess backend.

Tests ToolDef, CliBackendConfig, prepare, and run with mocked subprocess.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.agents.backends.cli_backend import (
    CliBackend,
    CliBackendConfig,
    ToolDef,
)
from harness.agents.backends.base import (
    AbstractBackend,
    BackendResult,
    Invocation,
)
from harness.agents.context import ContextPacket, OutputContract


class TestToolDef:
    """Tests for ToolDef dataclass."""

    def test_defaults(self):
        tool = ToolDef(name="test", binary="pytest")
        assert tool.name == "test"
        assert tool.binary == "pytest"
        assert tool.template_args == []
        assert tool.timeout_seconds == 1800
        assert tool.env_overrides == {}

    def test_custom_values(self):
        tool = ToolDef(
            name="custom", binary="node",
            template_args=["script.js"],
            timeout_seconds=300,
            env_overrides={"NODE_ENV": "test"},
        )
        assert tool.template_args == ["script.js"]
        assert tool.timeout_seconds == 300
        assert tool.env_overrides == {"NODE_ENV": "test"}


class TestCliBackendConfig:
    """Tests for CliBackendConfig."""

    def test_default_config(self):
        config = CliBackendConfig()
        assert config.tools == {}
        assert config.default_timeout == 1800

    def test_from_dict(self):
        config = CliBackendConfig.from_dict({
            "default_timeout": "600",
            "tools": {
                "claude": {
                    "name": "claude-code",
                    "binary": "claude",
                    "args": ["{spec_file}", "{project_dir}"],
                    "timeout": "300",
                },
            },
        })
        assert config.default_timeout == 600
        assert "claude" in config.tools
        assert config.tools["claude"].binary == "claude"
        assert config.tools["claude"].timeout_seconds == 300


class TestCliBackend:
    """Tests for CliBackend."""

    def test_name(self):
        assert CliBackend.name == "cli"

    @pytest.mark.asyncio
    async def test_prepare(self, tmp_path):
        """prepare() creates an Invocation with spec file."""
        backend = CliBackend({"tools": {
            "claude": {
                "binary": "claude",
                "args": ["{spec_file}"],
            },
        }})

        packet = ContextPacket(
            engagement_id="test",
            phase_name="coding",
            task_id="t1",
            spec_content="# Implement feature X",
            architecture_rules=["follow SOLID"],
            target_directory=tmp_path,
        )

        invocation = await backend.prepare(packet)
        assert invocation.command == "claude"
        assert len(invocation.args) == 1
        # Spec file should exist
        spec_file = Path(invocation.args[0])
        assert spec_file.exists()
        assert "Implement feature X" in spec_file.read_text()

    @pytest.mark.asyncio
    async def test_prepare_with_no_tools(self):
        """prepare() works when no tools are configured."""
        backend = CliBackend()
        packet = ContextPacket(
            engagement_id="test", phase_name="test",
            task_id="t1", spec_content="test",
        )
        invocation = await backend.prepare(packet)
        # Should use a default empty tool
        assert invocation.command == ""
        assert invocation.timeout_seconds == 1800

    @pytest.mark.asyncio
    async def test_run_success(self):
        """run() returns success when subprocess exits 0."""
        backend = CliBackend()

        invocation = Invocation(
            command="echo",
            args=["hello world"],
            timeout_seconds=30,
        )

        result = await backend.run(invocation)
        assert result.status == "success"
        assert "hello world" in result.artifacts.get("stdout.log", "")

    @pytest.mark.asyncio
    async def test_run_failure(self):
        """run() returns failure when subprocess exits non-zero."""
        backend = CliBackend()

        invocation = Invocation(
            command="sh",
            args=["-c", "exit 1"],
            timeout_seconds=30,
        )

        result = await backend.run(invocation)
        assert result.status == "failure"
        assert result.metrics.get("return_code") == 1

    @pytest.mark.asyncio
    async def test_run_file_not_found(self):
        """run() returns failure when binary doesn't exist."""
        backend = CliBackend()

        invocation = Invocation(
            command="/nonexistent/tool",
            args=[],
            timeout_seconds=30,
        )

        result = await backend.run(invocation)
        assert result.status == "failure"
        assert any("not found" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_with_reconfigured_command(self):
        """run() uses resolved_config command override."""
        backend = CliBackend()

        invocation = Invocation(
            command="echo",
            args=[],
            resolved_config={"type": "cli", "command": "echo"},
            timeout_seconds=30,
        )

        result = await backend.run(invocation)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_run_collects_files(self, tmp_path):
        """run() collects produced files from the working directory."""
        backend = CliBackend()

        # Create a file that should be collected
        (tmp_path / "output.txt").write_text("test output")

        invocation = Invocation(
            command="echo",
            args=["done"],
            work_dir=str(tmp_path),
            timeout_seconds=30,
        )

        result = await backend.run(invocation)
        assert result.status == "success"
        assert "output.txt" in result.artifacts

    def test_validate_config(self):
        backend = CliBackend()
        errors = backend.validate_config({"tools": {}})
        assert errors == []

    def test_validate_config_missing_binary(self):
        backend = CliBackend()
        errors = backend.validate_config({
            "tools": {
                "bad": {"binary": ""},
            },
        })
        assert any("binary is required" in e for e in errors)
