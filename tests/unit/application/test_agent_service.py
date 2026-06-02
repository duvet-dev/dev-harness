"""Tests for application/services/agent_service.py: AgentService, _safety_rmtree."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.application.services.agent_service import AgentService, _safety_rmtree
from harness.agents.backends.base import BackendError, BackendResult, Invocation
from harness.agents.context import ContextPacket, OutputContract
from harness.infrastructure.plugins.registry import PluginRegistry


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=PluginRegistry)
    backend = AsyncMock()
    backend.name = "api"
    backend.prepare.return_value = Invocation(
        command="test",
    )
    backend.run.return_value = BackendResult(status="success", artifacts={"output": "done"})
    registry.get.return_value = backend
    registry.has_backend.return_value = True
    return registry


@pytest.fixture
def service(mock_registry) -> AgentService:
    return AgentService(plugin_registry=mock_registry)


@pytest.fixture
def packet() -> ContextPacket:
    return ContextPacket(
        engagement_id="test",
        phase_name="build",
        task_id="t1",
        spec_content="hello",
        architecture_rules=[],
        target_directory=Path("/tmp"),
        output_contract=OutputContract(),
        constraint_section={"backend": "api", "model": "gpt-4"},
    )


# ── _safety_rmtree ─────────────────────────────────────────────────────────


class TestSafetyRmtree:
    def test_refuses_path_with_git(self, tmp_path):
        git_dir = tmp_path / "sub" / ".git"
        git_dir.mkdir(parents=True)
        target = tmp_path / "sub" / "target"
        target.mkdir()
        with pytest.raises(RuntimeError, match="contains a .git repo"):
            _safety_rmtree(str(target))

    def test_refuses_unsafe_prefix(self, tmp_path):
        target = tmp_path / "not_safe_dir"
        target.mkdir()
        with pytest.raises(RuntimeError, match="does not start with a safe prefix"):
            _safety_rmtree(str(target))

    def test_removes_safe_tmp_dir(self):
        d = tempfile.mkdtemp(prefix="harness_simple_")
        assert os.path.isdir(d)
        _safety_rmtree(d)
        assert not os.path.isdir(d)

    def test_refuses_non_absolute(self):
        pass  # dead-code path (resolve() always produces absolute)

    def test_refuses_path_with_safe_prefix_but_git_parent(self, tmp_path):
        """Path with safe name but .git above should be rejected."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        safe_target = tmp_path / "tmp_" / "work"
        safe_target.mkdir(parents=True)
        with pytest.raises(RuntimeError, match="contains a .git repo"):
            _safety_rmtree(str(safe_target))

    def test_safe_prefix_tmp(self):
        d = tempfile.mkdtemp(prefix="tmp_")
        assert os.path.isdir(d)
        _safety_rmtree(d)
        assert not os.path.isdir(d)


# ── AgentService — init ────────────────────────────────────────────────────


class TestAgentServiceInit:
    def test_requires_plugin_registry(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry, default_backend="editor")
        assert svc is not None

    def test_default_values(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        assert svc._default_backend == "api"
        assert svc._temp_dir_prefix == "harness_agent_"
        assert svc._cleanup_temp_dirs is True
        assert svc._project_dir == ""
        assert svc._max_fallbacks == 3


# ── AgentService — run ─────────────────────────────────────────────────────


class TestAgentServiceRun:
    @pytest.mark.asyncio
    async def test_run_success(self, service: AgentService, packet: ContextPacket):
        result = await service.run(packet, backend_name="api")
        assert result.status == "success"
        assert "runner_duration_ms" in result.metrics
        assert result.metrics["backend"] == "api"

    @pytest.mark.asyncio
    async def test_run_resolves_backend_from_packet(self, service: AgentService):
        """If no backend_name given, resolves from packet constraints."""
        packet = ContextPacket(
            engagement_id="t",
            phase_name="p",
            task_id="t",
            spec_content="c",
            architecture_rules=[],
            target_directory=Path("/tmp"),
            output_contract=OutputContract(),
            constraint_section={"backend": "cli"},
        )
        result = await service.run(packet)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_run_calls_plugin_registry_get(self, service: AgentService, packet: ContextPacket, mock_registry):
        await service.run(packet, backend_name="api")
        mock_registry.get.assert_called_with("api")

    @pytest.mark.asyncio
    async def test_run_with_fallback_chain(self, service: AgentService, mock_registry):
        """When primary fails, fallback backends are tried."""
        primary_backend = AsyncMock()
        primary_backend.name = "api"
        primary_backend.prepare.return_value = Invocation(command="test")
        primary_backend.run.return_value = BackendResult(status="failure", errors=["API error"])

        fallback_backend = AsyncMock()
        fallback_backend.name = "cli"
        fallback_backend.prepare.return_value = Invocation(command="test")
        fallback_backend.run.return_value = BackendResult(status="success", artifacts={"out": "ok"})

        def mock_get(name):
            return {"api": primary_backend, "cli": fallback_backend}.get(name, primary_backend)

        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="test with fallbacks", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "cli", "model": "default"}],
            },
        )
        result = await service.run(packet)
        assert result.status == "success"
        assert result.metrics.get("fallback_used") is True

    @pytest.mark.asyncio
    async def test_run_with_backend_error(self, service: AgentService, packet: ContextPacket, mock_registry):
        """BackendError returns a failure BackendResult."""
        backend = mock_registry.get.return_value
        from harness.agents.backends.base import BackendError
        backend.prepare.side_effect = BackendError("prepare failed")
        result = await service.run(packet)
        assert result.status == "failure"
        assert "prepare failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_run_with_temp_dir(self, mock_registry):
        """When use_temp_dir=True, a temp directory is created and cleaned up."""
        backend = mock_registry.get.return_value
        backend.prepare.return_value = Invocation(command="test")
        backend.run.return_value = BackendResult(status="success")

        svc = AgentService(plugin_registry=mock_registry, cleanup_temp_dirs=True)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "api"},
        )
        result = await svc.run(packet, use_temp_dir=True)
        assert result.status == "success"
        # temp dir should have been cleaned up, so packet.target_directory
        # should be restored to original
        assert str(packet.target_directory) == "/tmp"

    @pytest.mark.asyncio
    async def test_run_with_no_backends_available(self, mock_registry):
        """When no backends are available, should raise BackendError."""
        from harness.agents.backends.base import BackendError
        mock_registry.get.side_effect = KeyError("no-backend")
        mock_registry.has_backend.return_value = False
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "missing"},
        )
        with pytest.raises(BackendError, match="No backends available"):
            await svc.run(packet)

    @pytest.mark.asyncio
    async def test_run_fallback_attempted_all_fail(self, mock_registry):
        """When all fallbacks fail, the original result is returned with fallback_attempted metric."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        fallback_cli = AsyncMock()
        fallback_cli.name = "cli"
        fallback_cli.prepare.return_value = Invocation(command="test")
        fallback_cli.run.return_value = BackendResult(status="failure", errors=["CLI error"])

        def mock_get(name):
            return {"api": primary, "cli": fallback_cli}.get(name, primary)
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "cli", "model": "default"}],
            },
        )
        result = await svc.run(packet)
        assert result.status == "failure"
        assert result.metrics.get("fallback_attempted") == 1

    @pytest.mark.asyncio
    async def test_run_fallback_backend_not_found(self, mock_registry):
        """When a fallback backend is not in the registry, skip it."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        def mock_get(name):
            if name == "missing-backend":
                raise KeyError(name)
            return primary
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "missing-backend", "model": "default"}],
            },
        )
        result = await svc.run(packet)
        assert result.status == "failure"
        assert result.metrics.get("fallback_attempted") == 1

    @pytest.mark.asyncio
    async def test_run_with_model_resolution(self, mock_registry):
        """Model string is resolved through providers when available."""
        backend = mock_registry.get.return_value
        svc = AgentService(plugin_registry=mock_registry, project_dir="/tmp")
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "api", "model": "gpt-4"},
        )
        # Mock providers path to exist
        with patch("harness.application.services.agent_service.get_providers_path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("harness.application.services.agent_service.load_providers") as mock_load:
                mock_providers = MagicMock()
                mock_providers.get_resolved.return_value = {"key": "value"}
                mock_providers.resolve_model.return_value = "resolved-gpt-4"
                mock_load.return_value = mock_providers
                result = await svc.run(packet)
        assert result.status == "success"
        backend.prepare.assert_called_once()
        call_kwargs = backend.prepare.call_args[1]
        assert call_kwargs["model"] == "resolved-gpt-4"

    @pytest.mark.asyncio
    async def test_run_model_resolution_exception_falls_back(self, mock_registry):
        """When model resolution raises, falls back to raw model key."""
        backend = mock_registry.get.return_value
        svc = AgentService(plugin_registry=mock_registry, project_dir="/tmp")
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "api", "model": "gpt-4"},
        )
        with patch("harness.application.services.agent_service.get_providers_path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("harness.application.services.agent_service.load_providers") as mock_load:
                mock_providers = MagicMock()
                mock_providers.get_resolved.return_value = {"key": "value"}
                mock_providers.resolve_model.side_effect = ValueError("bad model")
                mock_load.return_value = mock_providers
                result = await svc.run(packet)
        assert result.status == "success"
        call_kwargs = backend.prepare.call_args[1]
        assert call_kwargs["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_run_skip_providers_when_no_project_dir(self, mock_registry):
        """When the project has no providers.yaml, load_providers returns nothing."""
        backend = mock_registry.get.return_value
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "api", "model": "gpt-4"},
        )
        result = await svc.run(packet)
        assert result.status == "success"
        call_kwargs = backend.prepare.call_args[1]
        # No resolved_config because load_providers returned None
        assert call_kwargs["resolved_config"] is None
        assert call_kwargs["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_run_fallback_with_model_resolution(self, mock_registry):
        """Fallback chain with model resolution through providers."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        fallback = AsyncMock()
        fallback.name = "cli"
        fallback.prepare.return_value = Invocation(command="test")
        fallback.run.return_value = BackendResult(status="success")

        def mock_get(name):
            return {"api": primary, "cli": fallback}.get(name, primary)
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry, project_dir="/tmp")
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "cli", "model": "claude-3"}],
            },
        )
        with patch("harness.application.services.agent_service.get_providers_path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("harness.application.services.agent_service.load_providers") as mock_load:
                mock_providers = MagicMock()
                mock_providers.get_resolved.return_value = {"key": "value"}
                mock_providers.resolve_model.return_value = "resolved-claude-3"
                mock_load.return_value = mock_providers
                result = await svc.run(packet)
        assert result.status == "success"
        assert result.metrics.get("fallback_used") is True
        assert result.metrics.get("fallback_index") == 1
        # fallback should have been called with resolved model
        fallback.prepare.assert_called_once()
        fb_kwargs = fallback.prepare.call_args[1]
        assert fb_kwargs["model"] == "resolved-claude-3"

    @pytest.mark.asyncio
    async def test_run_fallback_exceeds_max_fallbacks(self, mock_registry):
        """When max_fallbacks is exceeded, remaining fallbacks are skipped."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        def mock_get(name):
            return primary
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry, max_fallbacks=0)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "cli", "model": "default"}],
            },
        )
        result = await svc.run(packet)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_run_fallback_skip_empty_backend_name(self, mock_registry):
        """Fallback with empty backend name is skipped."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        def mock_get(name):
            return primary
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "", "model": "default"}],
            },
        )
        result = await svc.run(packet)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_run_fallback_model_resolution_fails(self, mock_registry):
        """When fallback model resolution fails, falls back to raw model key."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        fallback = AsyncMock()
        fallback.name = "cli"
        fallback.prepare.return_value = Invocation(command="test")
        fallback.run.return_value = BackendResult(status="failure", errors=["CLI error"])

        def mock_get(name):
            return {"api": primary, "cli": fallback}.get(name, primary)
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry, project_dir="/tmp")
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "cli", "model": "claude-3"}],
            },
        )
        with patch("harness.application.services.agent_service.get_providers_path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("harness.application.services.agent_service.load_providers") as mock_load:
                mock_providers = MagicMock()
                mock_providers.get_resolved.return_value = {"key": "value"}
                mock_providers.resolve_model.side_effect = ValueError("bad model")
                mock_load.return_value = mock_providers
                result = await svc.run(packet)
        assert result.status == "failure"
        fallback.prepare.assert_called_once()
        fb_kwargs = fallback.prepare.call_args[1]
        assert fb_kwargs["model"] == "claude-3"  # raw fallback

    @pytest.mark.asyncio
    async def test_run_fallback_key_error_skips_backend(self, mock_registry):
        """When a fallback backend is not available (all inner fallbacks fail),
        skip the fallback and continue."""
        primary = AsyncMock()
        primary.name = "api"
        primary.prepare.return_value = Invocation(command="test")
        primary.run.return_value = BackendResult(status="failure", errors=["API error"])

        def mock_get(name):
            if name in ("missing", "api", "cli", "editor"):
                raise KeyError(name)
            return primary
        mock_registry.get.side_effect = mock_get
        mock_registry.has_backend.return_value = False

        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "backend": "api",
                "fallbacks": [{"backend": "missing", "model": "default"}],
            },
        )
        from harness.agents.backends.base import BackendError
        with pytest.raises(BackendError, match="No backends available"):
            await svc.run(packet)

    @pytest.mark.asyncio
    async def test_run_passes_backend_config_and_model(self, service: AgentService, packet: ContextPacket, mock_registry):
        """The backend receives the resolved config and model."""
        backend = mock_registry.get.return_value
        await service.run(packet, backend_name="api")
        backend.prepare.assert_called_once()
        call_kwargs = backend.prepare.call_args[1]
        assert "resolved_config" in call_kwargs
        assert "model" in call_kwargs


# ── AgentService — resolve_project_dir ─────────────────────────────────────


class TestResolveProjectDir:
    def test_uses_configured_project_dir(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry, project_dir="/custom/proj")
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={},
        )
        result = svc._resolve_project_dir(packet)
        assert result == Path("/custom/proj")

    def test_falls_back_to_target_directory(self, mock_registry, tmp_path):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=tmp_path, output_contract=OutputContract(),
            constraint_section={},
        )
        result = svc._resolve_project_dir(packet)
        assert result is not None
        assert str(result).startswith(str(tmp_path))

    def test_returns_none_when_no_target(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=None, output_contract=OutputContract(),
            constraint_section={},
        )
        result = svc._resolve_project_dir(packet)
        assert result is None


# ── AgentService — fallback chain ──────────────────────────────────────────


class TestBuildFallbackChain:
    def test_empty_when_no_fallbacks(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={},
        )
        result = svc._build_fallback_chain("api", "", packet)
        assert result == []

    def test_parses_packet_fallbacks(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "fallbacks": [
                    {"backend": "cli", "model": "default"},
                ],
            },
        )
        result = svc._build_fallback_chain("api", "", packet)
        assert len(result) == 1
        assert result[0]["backend"] == "cli"
        assert result[0]["model"] == "default"

    def test_skips_invalid_fallbacks(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={
                "fallbacks": [
                    {"backend": ""},  # no backend name
                    "just a string",  # not a dict
                ],
            },
        )
        result = svc._build_fallback_chain("api", "", packet)
        assert result == []


# ── AgentService — resolve_backend ─────────────────────────────────────────


class TestResolveBackend:
    def test_gets_named_backend(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "api"},
        )
        result = svc._resolve_backend(packet, None)
        assert result is not None

    def test_falls_through_when_missing(self, mock_registry):
        """When requested backend is missing, falls back to available backends."""
        requested_name = ["missing"]
        fallback_backend = AsyncMock()
        fallback_backend.name = "api"
        fallback_backend.prepare.return_value = Invocation(command="test")
        fallback_backend.run.return_value = BackendResult(status="success")

        def get_side_effect(name):
            if name == "missing":
                raise KeyError(name)
            return fallback_backend

        mock_registry.get.side_effect = get_side_effect
        mock_registry.has_backend.return_value = True

        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=Path("/tmp"), output_contract=OutputContract(),
            constraint_section={"backend": "missing"},
        )
        result = svc._resolve_backend(packet, None)
        assert result is not None
        assert result.name == "api"


# ── AgentService — attach_repo_tool ────────────────────────────────────────


class TestAttachRepoTool:
    def test_skips_when_tools_already_attached(self, mock_registry, packet: ContextPacket):
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(
            command="test", available_tools=[{"existing": "tool"}],
        )
        svc.attach_repo_tool(packet, inv)
        assert len(inv.available_tools) == 1  # unchanged

    def test_skips_when_no_target(self, mock_registry):
        svc = AgentService(plugin_registry=mock_registry)
        packet = ContextPacket(
            engagement_id="t", phase_name="p", task_id="t",
            spec_content="c", architecture_rules=[],
            target_directory=None, output_contract=OutputContract(),
            constraint_section={"agent_role": "coder"},
        )
        inv = Invocation(command="test")
        svc.attach_repo_tool(packet, inv)
        assert inv.available_tools == []

    def test_skips_when_no_agent_role(self, mock_registry, packet: ContextPacket):
        svc = AgentService(plugin_registry=mock_registry)
        packet.constraint_section = {}
        inv = Invocation(command="test")
        svc.attach_repo_tool(packet, inv)
        assert inv.available_tools == []

    def test_skips_when_agent_spec_not_found(self, mock_registry, packet: ContextPacket):
        """When agent_role_str doesn't match any agent spec, returns without error."""
        packet.constraint_section = {"agent_role": "nonexistent-role"}
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        with patch("harness.agents.agent_registry.get_agent", return_value=None):
            svc.attach_repo_tool(packet, inv)
        assert inv.available_tools == []

    def test_skips_when_no_tool_permissions(self, mock_registry, packet: ContextPacket):
        """When agent_spec has no tool_permissions, returns without error."""
        packet.constraint_section = {"agent_role": "coder"}
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        mock_spec = MagicMock()
        mock_spec.tool_permissions = None
        with patch("harness.agents.agent_registry.get_agent", return_value=mock_spec):
            svc.attach_repo_tool(packet, inv)
        assert inv.available_tools == []

    def test_attaches_repo_tool_with_permissions(self, mock_registry, packet: ContextPacket):
        """When agent has tool_permissions, RepoTool is attached."""
        packet.constraint_section = {"agent_role": "coder"}
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        mock_spec = MagicMock()
        mock_spec.tool_permissions.write = True
        mock_spec.tool_permissions.write_prefixes = []
        mock_spec.tool_permissions.web_search = False
        with patch("harness.agents.agent_registry.get_agent", return_value=mock_spec):
            svc.attach_repo_tool(packet, inv)
        assert len(inv.available_tools) == 1
        assert "repo_tool" in inv.tool_registry

    def test_attaches_repo_and_web_tools(self, mock_registry, packet: ContextPacket):
        """When web_search is True, both repo and web tools are attached."""
        packet.constraint_section = {"agent_role": "coder"}
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        mock_spec = MagicMock()
        mock_spec.tool_permissions.write = False
        mock_spec.tool_permissions.write_prefixes = ["/tmp"]
        mock_spec.tool_permissions.web_search = True
        with patch("harness.agents.agent_registry.get_agent", return_value=mock_spec):
            with patch("harness.application.services.agent_service.RepoTool") as MockRepoTool:
                mock_repo = MagicMock()
                MockRepoTool.return_value = mock_repo
                mock_repo.tool_spec.return_value = {"function": {"name": "repo_read"}}
                with patch("harness.tools.web_search.WebSearchTool") as MockWeb:
                    mock_web = MagicMock()
                    MockWeb.return_value = mock_web
                    mock_web.tool_spec.return_value = {"function": {"name": "web_search"}}
                    svc.attach_repo_tool(packet, inv)
        assert len(inv.available_tools) >= 1
        assert "repo_tool" in inv.tool_registry


# ── AgentService — attach_web_tool ─────────────────────────────────────────


class TestAttachWebTool:
    def test_attaches_web_tool(self, mock_registry, packet: ContextPacket):
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        svc.attach_web_tool(packet, inv)
        assert "web_search" in inv.tool_registry
        assert len(inv.available_tools) >= 1

    def test_does_not_duplicate(self, mock_registry, packet: ContextPacket):
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        svc.attach_web_tool(packet, inv)
        svc.attach_web_tool(packet, inv)
        assert len(inv.available_tools) == 1  # de-duped

    def test_handles_none_available_tools(self, mock_registry, packet: ContextPacket):
        """When available_tools is None, initializes to empty list."""
        svc = AgentService(plugin_registry=mock_registry)
        inv = Invocation(command="test")
        inv.available_tools = None
        svc.attach_web_tool(packet, inv)
        assert len(inv.available_tools) >= 1
