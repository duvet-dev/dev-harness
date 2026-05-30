"""Tests for harness.agents.backends.editor_backend — editor context files backend.

Tests EditorBackendConfig, prepare, and run for writing editor context files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.backends.editor_backend import (
    EditorBackend,
    EditorBackendConfig,
)
from harness.agents.backends.base import (
    AbstractBackend,
    BackendResult,
    Invocation,
)
from harness.agents.context import ContextPacket, OutputContract


class TestEditorBackendConfig:
    """Tests for EditorBackendConfig."""

    def test_default_config(self):
        config = EditorBackendConfig()
        assert "context.md" in config.output_formats
        assert ".cursorrules" in config.output_formats
        assert config.include_architecture is True
        assert config.include_spec is True
        assert config.include_contract is True

    def test_from_dict(self):
        config = EditorBackendConfig.from_dict({
            "output_formats": ["context.md"],
            "include_architecture": False,
            "include_spec": True,
        })
        assert config.output_formats == ["context.md"]
        assert config.include_architecture is False
        assert config.include_spec is True

    def test_from_dict_defaults(self):
        config = EditorBackendConfig.from_dict({})
        assert ".cursorrules" in config.output_formats


class TestEditorBackend:
    """Tests for EditorBackend."""

    def test_name(self):
        assert EditorBackend.name == "editor"

    @pytest.mark.asyncio
    async def test_prepare(self):
        """prepare() creates an invocation without a separate run plan."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="test",
            phase_name="coding",
            task_id="t1",
            spec_content="# Implement feature",
            target_directory=Path("/tmp/test_editor"),
        )
        invocation = await backend.prepare(packet)
        assert invocation.command == "write_files"
        assert invocation.input_packet == packet

    @pytest.mark.asyncio
    async def test_run_writes_files(self, tmp_path):
        """run() writes context files to the target directory."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="eng-1",
            phase_name="implementation",
            task_id="t1",
            spec_content="# Build the API endpoint",
            architecture_rules=["use hexagonal architecture"],
            target_directory=tmp_path,
            output_contract=OutputContract(
                required_files=["src/api.py"],
                coverage_target=0.8,
            ),
            constraint_section={"language": "python"},
        )
        invocation = Invocation(
            command="write_files",
            work_dir=str(tmp_path),
            input_packet=packet,
            timeout_seconds=30,
        )
        result = await backend.run(invocation)

        assert result.status == "success"
        assert result.metrics["files_written"] >= 2

        # Check files exist
        context_md = tmp_path / "context.md"
        cursorrules = tmp_path / ".cursorrules"
        assert context_md.exists()
        assert cursorrules.exists()

    @pytest.mark.asyncio
    async def test_run_includes_spec(self, tmp_path):
        """Context file includes spec content."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="e1", phase_name="p1", task_id="t1",
            spec_content="## My Spec\nWrite a function.",
            target_directory=tmp_path,
        )
        invocation = await backend.prepare(packet)
        invocation.work_dir = str(tmp_path)
        result = await backend.run(invocation)

        content = (tmp_path / "context.md").read_text()
        assert "My Spec" in content
        assert "Write a function" in content

    @pytest.mark.asyncio
    async def test_run_includes_architecture_rules(self, tmp_path):
        """Context file includes architecture rules."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="e1", phase_name="p1", task_id="t1",
            spec_content="Implement",
            architecture_rules=["hexagonal", "SOLID"],
            target_directory=tmp_path,
        )
        invocation = await backend.prepare(packet)
        invocation.work_dir = str(tmp_path)
        result = await backend.run(invocation)

        content = (tmp_path / "context.md").read_text()
        assert "hexagonal" in content
        assert "SOLID" in content

    @pytest.mark.asyncio
    async def test_run_includes_output_contract(self, tmp_path):
        """Context file includes output contract."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="e1", phase_name="p1", task_id="t1",
            spec_content="Implement",
            target_directory=tmp_path,
            output_contract=OutputContract(
                required_files=["src/main.py", "tests/test_main.py"],
                file_rules=[{"pattern": "*.py", "must_contain": "def "}],
                coverage_target=0.9,
            ),
        )
        invocation = await backend.prepare(packet)
        invocation.work_dir = str(tmp_path)
        result = await backend.run(invocation)

        content = (tmp_path / "context.md").read_text()
        assert "src/main.py" in content
        assert "test_main.py" in content
        assert "90%" in content or "0.9" in content or "90" in content

    @pytest.mark.asyncio
    async def test_run_includes_constraints(self, tmp_path):
        """Context file includes constraints section."""
        backend = EditorBackend()
        packet = ContextPacket(
            engagement_id="e1", phase_name="p1", task_id="t1",
            spec_content="Implement",
            target_directory=tmp_path,
            constraint_section={"language": "python", "framework": "fastapi"},
        )
        invocation = await backend.prepare(packet)
        invocation.work_dir = str(tmp_path)
        result = await backend.run(invocation)

        content = (tmp_path / "context.md").read_text()
        assert "language" in content
        assert "python" in content
        assert "framework" in content
        assert "fastapi" in content

    @pytest.mark.asyncio
    async def test_run_without_packet(self, tmp_path):
        """run() returns failure when no packet is provided."""
        backend = EditorBackend()
        invocation = Invocation(
            command="write_files",
            work_dir=str(tmp_path),
            input_packet=None,
            timeout_seconds=30,
        )
        result = await backend.run(invocation)
        assert result.status == "failure"
        assert any("No context packet" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_custom_formats(self, tmp_path):
        """Only configured formats are written."""
        backend = EditorBackend({"output_formats": ["CLAUDE.md"]})
        packet = ContextPacket(
            engagement_id="e1", phase_name="p1", task_id="t1",
            spec_content="Implement",
            target_directory=tmp_path,
        )
        invocation = await backend.prepare(packet)
        invocation.work_dir = str(tmp_path)
        result = await backend.run(invocation)

        assert result.metrics["files_written"] == 1
        assert (tmp_path / "CLAUDE.md").exists()

    def test_validate_config_empty_formats(self):
        """Empty output_formats validation fails."""
        backend = EditorBackend()
        errors = backend.validate_config({"output_formats": []})
        assert any("not be empty" in e for e in errors)

    def test_validate_config_valid(self):
        """Valid config passes validation."""
        backend = EditorBackend()
        errors = backend.validate_config({"output_formats": ["context.md"]})
        assert errors == []
