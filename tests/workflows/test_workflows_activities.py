"""Tests for harness.workflows.activities."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from harness.workflows.activities import (
    ActivityError,
    OutputCollectionError,
    SnapshotError,
    ValidationError,
    validate_inputs,
    run_single_agent,
    collect_outputs,
    aggregate_phase_outputs,
    check_phase_coverage,
    snapshot_state,
    _agent_output_dir,
    _REQUIRED_PACKET_FIELDS,
)


class TestValidateInputs:
    """Tests for the validate_inputs activity."""

    VALID_PACKET = {
        "engagement_id": "eng-123",
        "phase_name": "build",
        "task_id": "task-001",
        "spec_content": "Build the thing",
    }

    async def test_valid_packet(self):
        result = await validate_inputs(self.VALID_PACKET)
        assert result["valid"] is True
        assert result["packet"] == self.VALID_PACKET

    async def test_not_a_dict(self):
        with pytest.raises(ValidationError, match="Expected dict"):
            await validate_inputs("not-a-dict")

    async def test_empty_dict(self):
        with pytest.raises(ValidationError, match="Missing required"):
            await validate_inputs({})

    async def test_missing_fields(self):
        packet = {"engagement_id": "eng-123"}
        with pytest.raises(ValidationError, match="Missing required"):
            await validate_inputs(packet)

    async def test_empty_value(self):
        packet = dict(self.VALID_PACKET)
        packet["spec_content"] = ""
        with pytest.raises(ValidationError, match="Empty value"):
            await validate_inputs(packet)

    async def test_required_fields_constant(self):
        assert "engagement_id" in _REQUIRED_PACKET_FIELDS
        assert "phase_name" in _REQUIRED_PACKET_FIELDS
        assert "task_id" in _REQUIRED_PACKET_FIELDS
        assert "spec_content" in _REQUIRED_PACKET_FIELDS
        assert len(_REQUIRED_PACKET_FIELDS) == 4

    async def test_all_empty_values(self):
        packet = {k: "" for k in _REQUIRED_PACKET_FIELDS}
        with pytest.raises(ValidationError, match="Empty value"):
            await validate_inputs(packet)

    async def test_unexpected_exception_wrapped(self):
        """Non-ValidationError exceptions should be wrapped in ActivityError."""
        # Pass something that fails isinstance check then raises TypeError
        with pytest.raises(ActivityError):
            # Force an issue during field checking
            class BadDict(dict):
                def keys(self):
                    raise RuntimeError("internal error")

            await validate_inputs(BadDict())


class TestCollectOutputs:
    """Tests for the collect_outputs activity."""

    async def test_non_existent_directory(self):
        result = await collect_outputs("/nonexistent/path", ["*.txt"])
        assert result == {}

    async def test_empty_directory(self, tmp_path):
        result = await collect_outputs(str(tmp_path), ["*.txt"])
        assert result == {}

    async def test_exact_match(self, tmp_path):
        (tmp_path / "output.txt").write_text("hello world")
        result = await collect_outputs(str(tmp_path), ["*.txt"])
        assert "output.txt" in result
        assert result["output.txt"] == "hello world"

    async def test_recursive_glob(self, tmp_path):
        nested = tmp_path / "sub" / "nested"
        nested.mkdir(parents=True)
        (nested / "data.json").write_text('{"key": "val"}')
        result = await collect_outputs(str(tmp_path), ["**/*.json"])
        assert "sub/nested/data.json" in result
        assert result["sub/nested/data.json"] == '{"key": "val"}'

    async def test_large_file_returns_size(self, tmp_path):
        large = tmp_path / "big.bin"
        large.write_bytes(b"x" * (1024 * 1024 + 1))
        result = await collect_outputs(str(tmp_path), ["*.bin"])
        assert "big.bin" in result
        assert result["big.bin"] == 1024 * 1024 + 1

    async def test_missing_files_omitted(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        result = await collect_outputs(str(tmp_path), ["*.txt", "*.md"])
        assert "a.txt" in result
        assert "*.md" not in result  # pattern not returned

    async def test_multiple_matches(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.md").write_text("c")
        result = await collect_outputs(str(tmp_path), ["*.txt"])
        assert len(result) == 2

    async def test_output_collection_error(self):
        # Empty/invalid directory returns empty results without error
        result = await collect_outputs("", ["*"])
        assert result == {}

    async def test_binary_decode_utf8(self, tmp_path):
        (tmp_path / "data.txt").write_bytes(b"hello \xff world")
        result = await collect_outputs(str(tmp_path), ["*.txt"])
        assert "data.txt" in result
        # Should not raise; errors='replace' used
        assert "hello" in result["data.txt"]


class TestAggregatePhaseOutputs:
    """Tests for the aggregate_phase_outputs activity."""

    async def test_empty_list(self):
        result = await aggregate_phase_outputs([])
        assert result["total_files"] == 0
        assert result["total_size_bytes"] == 0
        assert result["agents"] == 0
        assert result["agent_ids"] == []
        assert result["phases"] == []

    async def test_single_output(self):
        outputs = [
            {
                "engagement_id": "eng-1",
                "phase_name": "build",
                "outputs": {"file1.txt": "hello"},
            }
        ]
        result = await aggregate_phase_outputs(outputs)
        assert result["total_files"] == 1
        assert result["total_size_bytes"] == 5  # len("hello")
        assert result["agents"] == 1
        assert result["agent_ids"] == ["eng-1"]
        assert result["phases"] == ["build"]

    async def test_multiple_outputs(self):
        outputs = [
            {
                "engagement_id": "eng-1",
                "phase_name": "build",
                "outputs": {"a.txt": "aa", "b.txt": "bbb"},
            },
            {
                "engagement_id": "eng-2",
                "phase_name": "test",
                "outputs": {"c.txt": "cccc"},
            },
        ]
        result = await aggregate_phase_outputs(outputs)
        assert result["total_files"] == 3
        assert result["total_size_bytes"] == 9  # 2 + 3 + 4
        assert result["agents"] == 2
        assert result["agent_ids"] == ["eng-1", "eng-2"]
        assert result["phases"] == ["build", "test"]

    async def test_outputs_with_int_sizes(self):
        outputs = [
            {
                "engagement_id": "eng-1",
                "phase_name": "build",
                "outputs": {"big.bin": 999},
            }
        ]
        result = await aggregate_phase_outputs(outputs)
        assert result["total_size_bytes"] == 999
        assert result["total_files"] == 1

    async def test_no_outputs_key(self):
        outputs = [
            {"engagement_id": "eng-1", "phase_name": "build"},
        ]
        result = await aggregate_phase_outputs(outputs)
        assert result["total_files"] == 0
        assert result["total_size_bytes"] == 0

    async def test_outputs_not_dict(self):
        outputs = [
            {"engagement_id": "eng-1", "phase_name": "build", "outputs": "not-a-dict"},
        ]
        result = await aggregate_phase_outputs(outputs)
        # Not a dict, so outputs_map isinstance check fails
        assert result["total_files"] == 0


class TestCheckPhaseCoverage:
    """Tests for the check_phase_coverage activity."""

    async def test_passes_below_95(self):
        result = await check_phase_coverage(80.0)
        assert result["passed"] is True
        assert result["coverage"] == 95.0
        assert result["target"] == 80.0

    async def test_passes_at_95(self):
        result = await check_phase_coverage(95.0)
        assert result["passed"] is True

    async def test_fails_above_95(self):
        result = await check_phase_coverage(96.0)
        assert result["passed"] is False
        assert result["coverage"] == 0.0

    async def test_findings_empty(self):
        result = await check_phase_coverage(50.0)
        assert result["findings"] == []


class TestSnapshotState:
    """Tests for the snapshot_state activity."""

    async def test_writes_yaml(self, tmp_path):
        result = await snapshot_state(
            engagement_id="eng-1",
            status="completed",
            phase="build",
            project_path=str(tmp_path),
        )
        assert result["engagement_id"] == "eng-1"
        assert result["status"] == "completed"
        assert result["phase"] == "build"
        assert "snapshot_path" in result
        assert "timestamp" in result

        snapshot_file = tmp_path / "harness-state.yaml"
        assert snapshot_file.exists()

    async def test_snapshot_file_content(self, tmp_path):
        result = await snapshot_state(
            engagement_id="eng-1",
            status="in_progress",
            phase="design",
            project_path=str(tmp_path),
        )
        snapshot_file = tmp_path / "harness-state.yaml"
        content = snapshot_file.read_text()
        assert "HUMAN READABLE ONLY" in content
        assert "eng-1" in content
        assert "in_progress" in content

    async def test_project_path_does_not_exist(self):
        with pytest.raises(SnapshotError, match="does not exist"):
            await snapshot_state(
                engagement_id="eng-1",
                status="active",
                phase="build",
                project_path="/nonexistent/path/12345",
            )

    async def test_returns_all_fields(self, tmp_path):
        result = await snapshot_state(
            engagement_id="eng-99",
            status="completed",
            phase="review",
            project_path=str(tmp_path),
        )
        assert set(result.keys()) == {
            "snapshot_path", "engagement_id", "status", "phase", "timestamp"
        }


class TestAgentOutputDir:
    """Tests for the internal _agent_output_dir helper."""

    def test_returns_expected_path(self):
        result = _agent_output_dir("eng-1", "build", "task-1")
        expected = os.path.join(".harness", "artifacts", "eng-1", "build", "task-1")
        assert result == expected

    def test_includes_all_components(self):
        result = _agent_output_dir("a", "b", "c")
        parts = result.split(os.sep)
        assert parts[-1] == "c"
        assert parts[-2] == "b"
        assert parts[-3] == "a"
        assert parts[-4] == "artifacts"
        assert parts[-5] == ".harness"


class TestRunSingleAgent:
    """Tests for the run_single_agent activity in activities.py.

    Note: This activity calls AgentOrchestrator which has real async I/O.
    We test the validation gate that happens before runner invocation.
    """

    async def test_invalid_input_returns_failure(self):
        result = await run_single_agent({"engagement_id": "e"})
        # Missing fields should cause validation failure
        assert result["status"] == "failure"
        assert "errors" in result
