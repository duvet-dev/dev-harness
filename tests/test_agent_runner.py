"""Tests for the agent runner.

Verifies backend resolution, execution flow, fallback behavior,
and the simple convenience method.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from harness.agents.backends.base import (
    AbstractBackend,
    BackendResult,
    Invocation,
)
from harness.agents.context import ContextPacket, OutputContract
from harness.agents.plugin_registry import PluginRegistry
from harness.agents.runner import AgentRunner


# ── Helpers ──────────────────────────────────────────────────────────────────

class MockBackend(AbstractBackend):
    """A mock backend for testing runner orchestration."""

    def __init__(self, name: str = "mock", status: str = "success"):
        super().__init__()
        self._name = name
        self._status = status

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Mock backend for testing"

    async def prepare(self, packet: ContextPacket) -> Invocation:
        return Invocation(
            command="mock",
            model="test-model",
            available_tools=[],
            input_packet=packet,
        )

    def validate_config(self) -> list[str]:
        return []

    async def run(self, packet: ContextPacket) -> BackendResult:
        return BackendResult(
            status=self._status,
            artifacts={"output": f"mock-output-{self._name}"},
            metrics={"duration_ms": 1},
        )


@pytest.fixture(autouse=True)
def clean_registry():
    PluginRegistry.initialize()
    yield


@pytest.fixture
def runner():
    return AgentRunner({"cleanup_temp_dirs": False})


@pytest.fixture
def packet():
    return ContextPacket(
        engagement_id="test",
        phase_name="test",
        task_id="test",
        spec_content="test spec",
        target_directory=Path(tempfile.mkdtemp(prefix="harness_test_")),
    )


# ── Backend Resolution ───────────────────────────────────────────────────────

class TestBackendResolution:
    """Tests for backend resolution logic."""

    @pytest.mark.asyncio
    async def test_resolve_backend_explicit(self, runner, packet):
        """_resolve_backend prefers explicit name."""
        mock = MockBackend(name="special")
        PluginRegistry.register(mock)

        backend = runner._resolve_backend(packet, backend_name="special")
        assert backend.name == "special"

    @pytest.mark.asyncio
    async def test_resolve_backend_from_packet(self, runner, packet):
        """_resolve_backend reads from packet constraints."""
        mock = MockBackend(name="from-packet")
        PluginRegistry.register(mock)

        packet.constraint_section = {"backend": "from-packet"}
        backend = runner._resolve_backend(packet, backend_name=None)
        assert backend.name == "from-packet"

    @pytest.mark.asyncio
    async def test_resolve_backend_default_api(self, runner, packet):
        """_resolve_backend falls back to 'api' when nothing specified."""
        backend = runner._resolve_backend(packet, backend_name=None)
        # 'api' should be registered by default
        assert backend.name == "api"


# ── run_simple ──────────────────────────────────────────────────────────────

class TestRunSimple:
    """Tests for AgentRunner.run_simple()."""

    @pytest.mark.asyncio
    async def test_run_simple_with_model(self):
        """run_simple() accepts model parameter and includes it in packet."""
        # Patch the runner.run method to inspect the packet
        runner = AgentRunner({"cleanup_temp_dirs": False})

        created_packets = []

        original_run = runner.run

        async def capture_run(packet, **kwargs):
            created_packets.append(packet)
            return BackendResult(
                status="success",
                artifacts={"output": "captured"},
                metrics={"duration_ms": 1},
            )

        with patch.object(runner, "run", capture_run):
            result = await runner.run_simple(
                spec_content="test spec",
                backend_name="api",
                model="deepseek-v4-pro",
            )

        assert result == "captured"
        assert len(created_packets) == 1
        packet = created_packets[0]
        assert packet.constraint_section.get("model") == "deepseek-v4-pro"

    @pytest.mark.asyncio
    async def test_run_simple_with_agent_role(self):
        """run_simple() accepts agent_role parameter and includes it in packet."""
        runner = AgentRunner({"cleanup_temp_dirs": False})

        created_packets = []

        async def capture_run(packet, **kwargs):
            created_packets.append(packet)
            return BackendResult(
                status="success",
                artifacts={"output": "captured"},
                metrics={"duration_ms": 1},
            )

        with patch.object(runner, "run", capture_run):
            result = await runner.run_simple(
                spec_content="test spec",
                backend_name="api",
                agent_role="critical-analyser",
            )

        assert result == "captured"
        assert len(created_packets) == 1
        packet = created_packets[0]
        assert packet.constraint_section.get("agent_role") == "critical-analyser"

    @pytest.mark.asyncio
    async def test_run_simple_with_project_dir(self):
        """run_simple() uses project_dir as target when provided."""
        runner = AgentRunner({"cleanup_temp_dirs": False})

        created_packets = []

        async def capture_run(packet, **kwargs):
            created_packets.append(packet)
            return BackendResult(
                status="success",
                artifacts={"output": "captured"},
                metrics={"duration_ms": 1},
            )

        with patch.object(runner, "run", capture_run):
            result = await runner.run_simple(
                spec_content="test spec",
                backend_name="api",
                project_dir="/tmp/test-project-dir",
            )

        assert result == "captured"
        assert len(created_packets) == 1
        packet = created_packets[0]
        assert str(packet.target_directory) == "/tmp/test-project-dir"

    @pytest.mark.asyncio
    async def test_run_simple_creates_temp_dir_by_default(self):
        """run_simple() creates a temp dir when project_dir not provided."""
        runner = AgentRunner({"cleanup_temp_dirs": False})

        created_packets = []

        async def capture_run(packet, **kwargs):
            created_packets.append(packet)
            return BackendResult(
                status="success",
                artifacts={"output": "captured"},
                metrics={"duration_ms": 1},
            )

        with patch.object(runner, "run", capture_run):
            result = await runner.run_simple(
                spec_content="test spec",
                backend_name="api",
            )

        assert result == "captured"
        assert len(created_packets) == 1
        packet = created_packets[0]
        # Should be a temp dir starting with "harness_simple_"
        assert "harness_simple_" in str(packet.target_directory)

    @pytest.mark.asyncio
    async def test_run_simple_error(self):
        """run_simple() returns error string on failure."""
        runner = AgentRunner({"cleanup_temp_dirs": False})

        async def fail_run(packet, **kwargs):
            return BackendResult(
                status="failure",
                artifacts={},
                metrics={"duration_ms": 0},
                errors=["Something went wrong"],
            )

        with patch.object(runner, "run", fail_run):
            result = await runner.run_simple(
                spec_content="test spec",
                backend_name="api",
            )

        assert result.startswith("Error:")
        assert "Something went wrong" in result


class TestRunCleanup:
    """Tests for run_simple cleanup behaviour."""

    @pytest.mark.asyncio
    async def test_cleanup_skipped_for_real_dirs(self):
        """run_simple() does NOT clean up when project_dir is provided."""
        import tempfile
        import os

        real_dir = tempfile.mkdtemp(prefix="real_test_dir_")
        marker_file = os.path.join(real_dir, "should-survive.txt")
        with open(marker_file, "w") as f:
            f.write("important data")

        runner = AgentRunner({"cleanup_temp_dirs": True})  # cleanup is ON

        async def capture_run(packet, **kwargs):
            return BackendResult(
                status="success",
                artifacts={"output": "done"},
                metrics={"duration_ms": 1},
            )

        with patch.object(runner, "run", capture_run):
            result = await runner.run_simple(
                spec_content="test",
                backend_name="api",
                project_dir=real_dir,
            )

        # The real dir should still exist
        assert os.path.exists(real_dir), "Cleanup deleted real project dir!"
        assert os.path.exists(marker_file), "Cleanup deleted files in real dir!"
        assert result == "done"

        # Cleanup our test dir
        import shutil
        shutil.rmtree(real_dir, ignore_errors=True)


class TestSafetyRmtree:
    """Tests for the _safety_rmtree guard."""

    def test_allows_temp_dir_with_prefix(self, tmp_path):
        """_safety_rmtree allows deleting temp dirs with known prefixes."""
        from harness.agents.runner import _safety_rmtree
        d = tmp_path / "harness_simple_abc"
        d.mkdir()
        (d / "test.txt").write_text("data")
        # This should work without error
        _safety_rmtree(str(d))
        assert not d.exists()

    def test_refuses_real_project_dir(self, tmp_path):
        """_safety_rmtree raises on paths with .git."""
        from harness.agents.runner import _safety_rmtree
        d = tmp_path / "myproject"
        d.mkdir()
        (d / ".git").mkdir()
        (d / "src").mkdir()
        with pytest.raises(RuntimeError, match="REFUSED"):
            _safety_rmtree(str(d))
        # Dir should still exist
        assert d.exists()

    def test_refuses_non_temp_name(self, tmp_path):
        """_safety_rmtree raises on paths without safe prefix."""
        from harness.agents.runner import _safety_rmtree
        d = tmp_path / "important_stuff"
        d.mkdir()
        with pytest.raises(RuntimeError, match="REFUSED"):
            _safety_rmtree(str(d))
        assert d.exists()

    def test_refuses_relative_path(self, tmp_path):
        """_safety_rmtree raises on relative paths."""
        from harness.agents.runner import _safety_rmtree
        with pytest.raises(RuntimeError, match="REFUSED"):
            _safety_rmtree("relative/path")

    def test_allows_agent_temp_prefix(self, tmp_path):
        """_safety_rmtree allows harness_agent_ prefixed dirs."""
        from harness.agents.runner import _safety_rmtree
        d = tmp_path / "harness_agent_xyz123"
        d.mkdir()
        _safety_rmtree(str(d))
        assert not d.exists()

    def test_allows_tmp_prefix(self, tmp_path):
        """_safety_rmtree allows tmp- prefixed dirs."""
        from harness.agents.runner import _safety_rmtree
        d = tmp_path / "tmp_test_dir"
        d.mkdir()
        _safety_rmtree(str(d))
        assert not d.exists()

    def test_detects_git_dir_in_parent(self, tmp_path):
        """_safety_rmtree detects .git in ancestor paths."""
        from harness.agents.runner import _safety_rmtree
        # Create a structure: tmp/gitrepo/sub/harness_simple_xxx/
        git_repo = tmp_path / "gitrepo"
        git_repo.mkdir()
        (git_repo / ".git").mkdir()
        sub = git_repo / "sub"
        sub.mkdir()
        temp_in_repo = sub / "harness_simple_abc"
        temp_in_repo.mkdir()
        with pytest.raises(RuntimeError, match="REFUSED"):
            _safety_rmtree(str(temp_in_repo))
        assert temp_in_repo.exists()


class TestRunnerConfig:
    """Tests for RunnerConfig dataclass."""

    def test_defaults(self):
        from harness.agents.runner import RunnerConfig
        c = RunnerConfig()
        assert c.timeout_seconds == 600
        # project_dir defaults to empty string, not None
        assert c.project_dir == ""

    def test_from_dict(self):
        from harness.agents.runner import RunnerConfig
        c = RunnerConfig.from_dict({
            "timeout_seconds": 120,
            "project_dir": "/tmp/proj",
        })
        assert c.timeout_seconds == 120
        assert c.project_dir == "/tmp/proj"

    def test_from_dict_empty(self):
        from harness.agents.runner import RunnerConfig
        c = RunnerConfig.from_dict({})
        assert c.timeout_seconds == 600


class TestCriticLoopResult:
    """Tests for CriticLoopResult dataclass."""

    def test_defaults(self):
        from harness.agents.runner import CriticLoopResult
        r = CriticLoopResult()
        assert r.converged is False
        assert r.iteration_results == []

    def test_converged(self):
        from harness.agents.runner import CriticLoopResult
        from harness.agents.agent_registry import CriticLoopIteration
        r = CriticLoopResult(converged=True, iteration_results=[
            CriticLoopIteration(iteration=0, architect_artifacts={"file.py": "code"}),
            CriticLoopIteration(iteration=1, architect_artifacts={"file.py": "v2"},
                                converged=True),
        ])
        assert r.converged is True
        assert len(r.iteration_results) == 2
        assert r.iteration_results[0].iteration == 0

    def test_critic_loop_error(self):
        from harness.agents.runner import CriticLoopError
        e = CriticLoopError("max iterations reached")
        assert str(e) == "max iterations reached"
        assert isinstance(e, Exception)


class TestSafetyRmtree:
    """Tests for the guarded _safety_rmtree."""

    def test_safe_prefixes(self, tmp_path):
        from harness.agents.runner import _safety_rmtree
        safe_dir = tmp_path / "harness_simple_test"
        safe_dir.mkdir()
        (safe_dir / "file.txt").write_text("data")
        _safety_rmtree(safe_dir)
        assert not safe_dir.exists()

    def test_unsafe_path_raises(self, tmp_path):
        from harness.agents.runner import _safety_rmtree
        unsafe_dir = tmp_path / "etc"
        unsafe_dir.mkdir()
        with pytest.raises(RuntimeError):
            _safety_rmtree(unsafe_dir)
        assert unsafe_dir.exists()
