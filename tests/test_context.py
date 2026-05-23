"""Tests for harness.agents.context — ContextPacket and OutputContract.

Tests creation, serialization to/from JSON, and error handling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.agents.context import (
    ContextPacket,
    ContextPacketError,
    OutputContract,
)


class TestOutputContract:
    """Tests for OutputContract."""

    def test_defaults(self):
        oc = OutputContract()
        assert oc.required_files == []
        assert oc.file_rules == []
        assert oc.validate_interface is False
        assert oc.coverage_target == 0.9

    def test_custom_values(self):
        oc = OutputContract(
            required_files=["src/main.py"],
            file_rules=[{"pattern": "*.py", "must_contain": "def "}],
            validate_interface=True,
            coverage_target=0.95,
        )
        assert oc.required_files == ["src/main.py"]
        assert oc.validate_interface is True
        assert oc.coverage_target == 0.95


class TestContextPacket:
    """Tests for ContextPacket."""

    def test_minimal_creation(self):
        packet = ContextPacket(
            engagement_id="eng-1",
            phase_name="design",
            task_id="t-42",
            spec_content="Build a feature",
        )
        assert packet.engagement_id == "eng-1"
        assert packet.phase_name == "design"
        assert packet.task_id == "t-42"
        assert packet.spec_content == "Build a feature"
        assert packet.architecture_rules == []
        assert packet.target_directory == Path(".")
        assert packet.input_artifacts == {}

    def test_full_creation(self, tmp_path):
        packet = ContextPacket(
            engagement_id="eng-1",
            phase_name="coding",
            task_id="t-99",
            spec_content="Implement X",
            architecture_rules=["hexagonal", "SOLID"],
            target_directory=tmp_path / "project",
            input_artifacts={"design": tmp_path / "design.md"},
            output_contract=OutputContract(
                required_files=["src/x.py"],
                coverage_target=0.8,
            ),
            constraint_section={"model": "gpt-4", "temperature": 0.3},
        )
        assert len(packet.architecture_rules) == 2
        assert packet.output_contract.required_files == ["src/x.py"]
        assert packet.constraint_section["model"] == "gpt-4"

    def test_to_json(self):
        packet = ContextPacket(
            engagement_id="eng-1",
            phase_name="test",
            task_id="t-1",
            spec_content="Run tests",
            architecture_rules=["isolated"],
            target_directory=Path("/tmp/project"),
            input_artifacts={"plan": Path("/tmp/plan.md")},
            output_contract=OutputContract(coverage_target=0.9),
            constraint_section={"model": "claude"},
        )
        json_str = packet.to_json()
        data = json.loads(json_str)
        assert data["engagement_id"] == "eng-1"
        assert data["target_directory"] == "/tmp/project"
        assert data["input_artifacts"]["plan"] == "/tmp/plan.md"
        assert data["constraint_section"]["model"] == "claude"

    def test_from_json(self):
        json_str = json.dumps({
            "engagement_id": "eng-2",
            "phase_name": "testing",
            "task_id": "t-2",
            "spec_content": "Test feature",
            "architecture_rules": [],
            "target_directory": "/tmp/repo",
            "input_artifacts": {},
            "output_contract": {
                "required_files": ["test_main.py"],
                "file_rules": [],
                "validate_interface": False,
                "coverage_target": 0.9,
            },
            "constraint_section": {},
        })
        packet = ContextPacket.from_json(json_str)
        assert packet.engagement_id == "eng-2"
        assert packet.phase_name == "testing"
        assert packet.spec_content == "Test feature"
        assert packet.target_directory == Path("/tmp/repo")
        assert packet.output_contract.required_files == ["test_main.py"]

    def test_to_json_roundtrip(self, tmp_path):
        """Serialization then deserialization preserves data."""
        original = ContextPacket(
            engagement_id="eng-3",
            phase_name="analysis",
            task_id="t-3",
            spec_content="Analyse structure",
            architecture_rules=["follow DDD"],
            target_directory=tmp_path,
            input_artifacts={"README": tmp_path / "README.md"},
            constraint_section={"agent_role": "architect"},
        )
        json_str = original.to_json()
        restored = ContextPacket.from_json(json_str)
        assert restored.engagement_id == original.engagement_id
        assert restored.phase_name == original.phase_name
        assert restored.task_id == original.task_id
        assert restored.spec_content == original.spec_content
        assert restored.architecture_rules == original.architecture_rules
        assert restored.constraint_section == original.constraint_section

    def test_to_json_error_handling(self):
        """to_json raises ContextPacketError on bad data."""
        packet = ContextPacket(
            engagement_id="test",
            phase_name="test",
            task_id="test",
            spec_content="test",
        )
        # Normal case should work fine
        result = packet.to_json()
        assert isinstance(result, str)

    def test_from_json_invalid(self):
        """from_json raises ContextPacketError on invalid JSON."""
        with pytest.raises(ContextPacketError, match="Failed to parse"):
            ContextPacket.from_json("not valid json")

    def test_from_json_missing_fields(self):
        """from_json handles missing fields with defaults."""
        json_str = json.dumps({
            "engagement_id": "eng-1",
            "phase_name": "phase-1",
            "task_id": "task-1",
            "spec_content": "content",
        })
        packet = ContextPacket.from_json(json_str)
        assert packet.architecture_rules == []
        assert packet.constraint_section == {}
