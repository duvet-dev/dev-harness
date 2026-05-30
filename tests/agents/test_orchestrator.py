"""Tests for AgentOrchestrator (replaces AgentRunner tests).

Target: 100% coverage on harness.agents.orchestrator module.
Covers: AgentOrchestrator, OrchestratorConfig, CriticLoopResult,
        CriticLoopError, _safety_rmtree, _build_iterations_from_cycle.
"""

from __future__ import annotations

import os
import tempfile
import unittest.mock
from pathlib import Path
from typing import Any

import pytest

from harness.agents.backends.base import BackendResult, Invocation
from harness.agents.context import ContextPacket, OutputContract
from harness.agents.orchestrator import (
    AgentOrchestrator,
    CriticLoopConfig,
    CriticLoopError,
    CriticLoopResult,
    CriticLoopState,
    OrchestratorConfig,
    _build_iterations_from_cycle,
    _safety_rmtree,
)


# ── _safety_rmtree ─────────────────────────────────────────────────────────────


class TestSafetyRmtree:
    def test_refuses_path_with_git(self, tmp_path):
        """Path containing a .git directory must be refused."""
        git_dir = tmp_path / "sub" / ".git"
        git_dir.mkdir(parents=True)
        target = tmp_path / "sub" / "target"
        target.mkdir()
        with pytest.raises(RuntimeError, match="contains a .git repo"):
            _safety_rmtree(str(target))

    def test_refuses_unsafe_prefix(self, tmp_path):
        """Paths without a safe prefix must be refused."""
        target = tmp_path / "not_safe_dir"
        target.mkdir()
        with pytest.raises(RuntimeError, match="does not start with a safe prefix"):
            _safety_rmtree(str(target))

    def test_refuses_relative_path_in_repo(self):
        """A relative path that resolves inside a git repo must be refused."""
        with pytest.raises(RuntimeError, match="contains a .git repo"):
            _safety_rmtree("tmp_foo")

    def test_accepts_safe_prefix(self, tmp_path):
        """A safe-prefixed temp directory should be removed."""
        target = tmp_path / "harness_agent_test"
        target.mkdir()
        _safety_rmtree(str(target))
        assert not target.exists()

    def test_accepts_tmp_prefix(self, tmp_path):
        """tmp/ prefix should also be safe."""
        target = tmp_path / "tmp_workdir"
        target.mkdir()
        _safety_rmtree(str(target))
        assert not target.exists()


# ── OrchestratorConfig ──────────────────────────────────────────────────────────


class TestOrchestratorConfig:
    def test_defaults(self):
        c = OrchestratorConfig()
        assert c.default_backend == "api"
        assert c.timeout_seconds == 600
        assert c.temp_dir_prefix == "harness_agent_"
        assert c.cleanup_temp_dirs is True
        assert c.project_dir == ""
        assert c.max_fallbacks == 3

    def test_from_dict_partial(self):
        c = OrchestratorConfig.from_dict({"default_backend": "cli"})
        assert c.default_backend == "cli"
        assert c.timeout_seconds == 600  # unchanged

    def test_from_dict_full(self):
        c = OrchestratorConfig.from_dict({
            "default_backend": "editor",
            "timeout_seconds": "300",
            "temp_dir_prefix": "my_prefix_",
            "cleanup_temp_dirs": False,
            "project_dir": "/tmp/proj",
            "max_fallbacks": 5,
        })
        assert c.default_backend == "editor"
        assert c.timeout_seconds == 300
        assert c.temp_dir_prefix == "my_prefix_"
        assert c.cleanup_temp_dirs is False
        assert c.project_dir == "/tmp/proj"
        assert c.max_fallbacks == 5


# ── CriticLoopResult ────────────────────────────────────────────────────────────


class TestCriticLoopResult:
    def test_defaults(self):
        r = CriticLoopResult()
        assert r.converged is False
        assert r.iterations == 0
        assert r.iteration_results == []
        assert r.final_state == CriticLoopState.RUNNING
        assert r.error_message == ""

    def test_custom_values(self):
        r = CriticLoopResult(
            converged=True,
            iterations=3,
            final_state=CriticLoopState.CONVERGED,
            error_message="nope",
        )
        assert r.converged is True
        assert r.iterations == 3
        assert r.final_state == CriticLoopState.CONVERGED
        assert r.error_message == "nope"


# ── CriticLoopError ─────────────────────────────────────────────────────────────


class TestCriticLoopError:
    def test_is_exception(self):
        err = CriticLoopError("something bad")
        assert isinstance(err, Exception)
        assert "something bad" in str(err)


# ── AgentOrchestrator ───────────────────────────────────────────────────────────


class TestAgentOrchestratorInit:
    def test_no_config(self):
        o = AgentOrchestrator()
        assert o._config.default_backend == "api"

    def test_with_config_dict(self):
        o = AgentOrchestrator({"default_backend": "editor"})
        assert o._config.default_backend == "editor"


class TestAgentOrchestratorResolveProjectDir:
    def test_uses_config_project_dir(self):
        o = AgentOrchestrator({"project_dir": "/tmp/my_proj"})
        packet = ContextPacket(
            engagement_id="test",
            phase_name="build",
            task_id="t1",
            spec_content="do it",
            target_directory=Path("/tmp/some/other"),
        )
        result = o._resolve_project_dir(packet)
        assert result == Path("/tmp/my_proj")

    def test_falls_back_to_target(self, tmp_path):
        o = AgentOrchestrator()
        target = tmp_path / "nested" / "deep"
        target.mkdir(parents=True)
        packet = ContextPacket(
            engagement_id="test",
            phase_name="build",
            task_id="t1",
            spec_content="do it",
            target_directory=target,
        )
        result = o._resolve_project_dir(packet)
        assert result == target.resolve()


class TestAgentOrchestratorBuildFallbackChain:
    def test_no_fallbacks(self):
        o = AgentOrchestrator()
        packet = ContextPacket(
            engagement_id="test",
            phase_name="build",
            task_id="t1",
            spec_content="do it",
        )
        chain = o._build_fallback_chain("api", "", packet)
        assert chain == []

    def test_from_packet_constraints(self):
        o = AgentOrchestrator()
        packet = ContextPacket(
            engagement_id="test",
            phase_name="build",
            task_id="t1",
            spec_content="do it",
            constraint_section={
                "fallbacks": [
                    {"backend": "cli", "model": "gpt-4"},
                    {"backend": "editor"},
                ]
            },
        )
        chain = o._build_fallback_chain("api", "", packet)
        assert len(chain) == 2
        assert chain[0]["backend"] == "cli"
        assert chain[0]["model"] == "gpt-4"
        assert chain[1]["backend"] == "editor"
        assert chain[1]["model"] == "default"


class TestAgentOrchestratorResolveBackend:
    def test_uses_explicit_name(self):
        from harness.agents.plugin_registry import PluginRegistry
        PluginRegistry.initialize()
        o = AgentOrchestrator()
        packet = ContextPacket("t", "b", "t", "x")
        backend = o._resolve_backend(packet, "api")
        assert backend is not None

    def test_uses_backend_from_packet(self):
        from harness.agents.plugin_registry import PluginRegistry
        PluginRegistry.initialize()
        o = AgentOrchestrator()
        packet = ContextPacket(
            "t", "b", "t", "x",
            constraint_section={"backend": "api"},
        )
        backend = o._resolve_backend(packet, None)
        assert backend is not None

    def test_falls_back_to_api_for_unknown(self):
        """Requesting a non-existent backend should fall back to 'api'."""
        from harness.agents.plugin_registry import PluginRegistry
        PluginRegistry.initialize()
        o = AgentOrchestrator()
        packet = ContextPacket("t", "b", "t", "x")
        backend = o._resolve_backend(packet, "non_existent_backend_xyz")
        assert backend is not None


class TestAgentOrchestratorCheckCriticConvergence:
    def test_converges_on_keyword(self):
        o = AgentOrchestrator()
        result = BackendResult(
            status="success",
            artifacts={"review": "The design looks good. APPROVED."},
        )
        config = CriticLoopConfig(convergence_keywords=["approved"])
        assert o._check_critic_convergence(result, config) is True

    def test_no_convergence_on_missing_keyword(self):
        o = AgentOrchestrator()
        result = BackendResult(
            status="success",
            artifacts={"review": "Some issues remain."},
        )
        config = CriticLoopConfig(convergence_keywords=["approved"])
        assert o._check_critic_convergence(result, config) is False


class TestAgentOrchestratorRunCriticLoop:
    @pytest.mark.asyncio
    async def test_raises_critic_loop_error(self):
        o = AgentOrchestrator()
        with pytest.raises(CriticLoopError, match="deprecated"):
            await o.run_critic_loop("test spec")


class TestAgentOrchestratorAttachRepoTool:
    def test_skips_when_tools_already_present(self):
        o = AgentOrchestrator()
        invocation = Invocation(
            command="test",
            available_tools=[{"function": {"name": "existing"}}],
        )
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x"
        )
        o.attach_repo_tool(packet, invocation)
        assert len(invocation.available_tools) == 1
        assert invocation.available_tools[0]["function"]["name"] == "existing"

    def test_skips_when_no_target_directory(self):
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x"
        )
        o.attach_repo_tool(packet, invocation)
        assert not invocation.available_tools
        assert not invocation.tool_registry

    def test_skips_when_no_agent_role(self, tmp_path):
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x",
            target_directory=tmp_path,
        )
        o.attach_repo_tool(packet, invocation)
        assert not invocation.available_tools

    def test_skips_on_unknown_role(self, tmp_path):
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x",
            target_directory=tmp_path,
            constraint_section={"agent_role": "bogus-role-999"},
        )
        o.attach_repo_tool(packet, invocation)
        assert not invocation.available_tools

    def test_attaches_for_valid_role(self, tmp_path):
        """For critical-analyser, attach_repo_tool should attach RepoTool."""
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            "t", "b", "t1", "x",
            target_directory=tmp_path,
            constraint_section={"agent_role": "critical-analyser"},
        )
        o.attach_repo_tool(packet, invocation)
        assert invocation.available_tools
        assert "repo_tool" in invocation.tool_registry


class TestAgentOrchestratorAttachWebTool:
    def test_attaches_web_search_tool(self):
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x"
        )
        o.attach_web_tool(packet, invocation)
        assert "web_search" in invocation.tool_registry
        assert invocation.available_tools is not None
        assert len(invocation.available_tools) >= 1
        names = {t.get("function", {}).get("name", "") for t in invocation.available_tools}
        assert "web_search" in names

    def test_does_not_duplicate(self):
        o = AgentOrchestrator()
        invocation = Invocation(command="test")
        packet = ContextPacket(
            engagement_id="t", phase_name="b", task_id="t1", spec_content="x"
        )
        o.attach_web_tool(packet, invocation)
        o.attach_web_tool(packet, invocation)
        count = sum(
            1 for t in invocation.available_tools
            if t.get("function", {}).get("name") == "web_search"
        )
        assert count == 1


# ── Async integration tests (patched backends) ─────────────────────────────────


@pytest.mark.asyncio
async def test_run_simple_returns_string():
    """run_simple returns a string regardless of success/failure."""
    o = AgentOrchestrator()
    result = await o.run_simple("do something impossible")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_run_simple_with_project_dir(tmp_path):
    """Providing a project_dir should not raise."""
    o = AgentOrchestrator()
    (tmp_path / "hello.py").write_text("x = 1\n")
    result = await o.run_simple(
        "analyse this",
        project_dir=str(tmp_path),
        agent_role="critical-analyser",
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_run_returns_backend_result():
    o = AgentOrchestrator()
    packet = ContextPacket("test", "build", "t1", "do something")
    result = await o.run(packet)
    assert hasattr(result, "status")
    assert hasattr(result, "artifacts")
    assert hasattr(result, "metrics")


@pytest.mark.asyncio
async def test_run_with_use_temp_dir():
    o = AgentOrchestrator()
    packet = ContextPacket(
        "test", "build", "t1", "do something",
        target_directory=Path("/tmp"),
    )
    result = await o.run(packet, use_temp_dir=True)
    assert hasattr(result, "status")
    assert "backend" in result.metrics


# ── _build_iterations_from_cycle ────────────────────────────────────────────────


class TestBuildIterationsFromCycle:
    def test_empty(self):
        class FakeResult:
            step_results = []

        result = _build_iterations_from_cycle(FakeResult(), ["converged"])
        assert result == []

    def test_with_convergence_hit(self):
        class StepResult:
            step_type = "critique"
            iteration = 1
            artifacts = {"review": "The design has converged."}

        class FakeResult:
            step_results = [StepResult()]

        iterations = _build_iterations_from_cycle(FakeResult(), ["converged"])
        assert len(iterations) == 1
        assert iterations[0].converged is True

    def test_without_convergence(self):
        class StepResult:
            step_type = "critique"
            iteration = 1
            artifacts = {"review": "Still needs work."}

        class FakeResult:
            step_results = [StepResult()]

        iterations = _build_iterations_from_cycle(FakeResult(), ["converged"])
        assert len(iterations) == 1
        assert iterations[0].converged is False

    def test_skips_gate_type(self):
        """Gate step type should also count as critic."""
        class StepResult:
            step_type = "gate"
            iteration = 1
            artifacts = {"review": "Approved"}

        class FakeResult:
            step_results = [StepResult()]

        iterations = _build_iterations_from_cycle(FakeResult(), ["approved"])
        assert len(iterations) == 1
        assert iterations[0].converged is True
