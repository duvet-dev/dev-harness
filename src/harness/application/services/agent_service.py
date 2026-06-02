"""AgentService — backend resolution, provider config, tool attachment.

Extracted from ``agents/orchestrator.py`` into a focused application
service. Handles the 'backend resolution → prepare → run' lifecycle
for agent execution.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from harness.agents.backends.base import (
    AbstractBackend,
    BackendError,
    BackendResult,
    Invocation,
)
from harness.agents.context import ContextPacket
from harness.agents.repo_tool import RepoTool
from harness.config.provider_registry import load_providers
from harness.infrastructure.plugins.registry import PluginRegistry
from harness.infrastructure.pydantic import ConstraintSection
from harness.paths import get_providers_path


def _cs(obj: Any) -> ConstraintSection:
    """Normalise a constraint_section value to a ConstraintSection."""
    if isinstance(obj, ConstraintSection):
        return obj
    if isinstance(obj, dict):
        return ConstraintSection(**obj)
    return ConstraintSection()

logger = logging.getLogger(__name__)


class AgentService:
    """Application service for agent backend execution.

    Extracted from the old ``AgentOrchestrator`` to provide a focused
    service for running agents through backends with resolved provider
    configuration, tool attachment, and fallback handling.

    Usage::

        service = AgentService(plugin_registry, config)
        result = await service.run(packet, backend_name="api")
    """

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        default_backend: str = "api",
        temp_dir_prefix: str = "harness_agent_",
        cleanup_temp_dirs: bool = True,
        project_dir: str = "",
        max_fallbacks: int = 3,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._default_backend = default_backend
        self._temp_dir_prefix = temp_dir_prefix
        self._cleanup_temp_dirs = cleanup_temp_dirs
        self._project_dir = project_dir
        self._max_fallbacks = max_fallbacks

    async def run(
        self,
        packet: ContextPacket,
        backend_name: str | None = None,
        use_temp_dir: bool = False,
    ) -> BackendResult:
        """Run a context packet through the selected backend.

        Resolves the provider config and model, passes them to the
        backend, and handles the fallback chain if the primary fails.

        Args:
            packet: The context packet describing the agent task.
            backend_name: Backend to use. If None, resolved from config.
            use_temp_dir: If True, create a temp workspace directory.

        Returns:
            BackendResult with artifacts, metrics, and status.
        """
        start_time = time.monotonic()
        cs = _cs(packet.constraint_section)

        resolved_name = (
            backend_name
            or cs.backend
            or self._default_backend
        )

        project_dir = self._resolve_project_dir(packet)
        model_key = cs.model

        providers = load_providers(project_dir) if project_dir else None
        resolved_config = providers.get_resolved(resolved_name) if providers else None

        if resolved_config and model_key and providers:
            try:
                model_str = providers.resolve_model(resolved_name, model_key)
            except Exception:
                model_str = model_key
        elif model_key:
            model_str = model_key
        else:
            model_str = ""

        fallback_chain = self._build_fallback_chain(
            resolved_name, model_key, packet
        )

        backend = self._resolve_backend(packet, resolved_name)
        result = await self._run_with_resolved_config(
            packet, backend, resolved_config, model_str, use_temp_dir
        )

        if result.status != "success" and fallback_chain:
            for i, fallback in enumerate(fallback_chain):
                if i >= self._max_fallbacks:
                    break

                fb_name = fallback.get("backend", "")
                fb_model = fallback.get("model", "")
                if not fb_name:
                    continue

                fb_config = providers.get_resolved(fb_name) if providers else None
                fb_model_str = fb_model
                if fb_config and fb_model and providers:
                    try:
                        fb_model_str = providers.resolve_model(fb_name, fb_model)
                    except Exception:
                        fb_model_str = fb_model

                try:
                    fb_backend = self._resolve_backend(packet, fb_name)
                except (KeyError, BackendError):
                    continue

                fb_result = await self._run_with_resolved_config(
                    packet, fb_backend, fb_config, fb_model_str, use_temp_dir
                )

                if fb_result.status == "success":
                    fb_result.metrics["runner_duration_ms"] = int(
                        (time.monotonic() - start_time) * 1000
                    )
                    fb_result.metrics["fallback_used"] = True
                    fb_result.metrics["fallback_index"] = i + 1
                    return fb_result

            result.metrics["fallback_attempted"] = len(fallback_chain)

        result.metrics["runner_duration_ms"] = int(
            (time.monotonic() - start_time) * 1000
        )
        result.metrics["backend"] = resolved_name
        return result

    async def _run_with_resolved_config(
        self,
        packet: ContextPacket,
        backend: AbstractBackend,
        resolved_config: dict[str, Any] | None,
        model: str,
        use_temp_dir: bool,
    ) -> BackendResult:
        temp_dir: str | None = None
        original_target = (
            str(packet.target_directory) if packet.target_directory else ""
        )

        if use_temp_dir:
            temp_dir = tempfile.mkdtemp(prefix=self._temp_dir_prefix)
            packet.target_directory = Path(temp_dir)

        try:
            invocation = await backend.prepare(
                packet,
                resolved_config=resolved_config,
                model=model,
            )
            result = await backend.run(invocation)
            return result
        except BackendError as exc:
            return BackendResult(
                status="failure",
                errors=[str(exc)],
                metrics={"backend": backend.name},
            )
        finally:
            if temp_dir and self._cleanup_temp_dirs:
                _safety_rmtree(temp_dir)
                if original_target:
                    packet.target_directory = Path(original_target)

    def _resolve_project_dir(self, packet: ContextPacket) -> Path | None:
        if self._project_dir:
            return Path(self._project_dir)
        if packet.target_directory:
            target = Path(packet.target_directory).resolve()
            for parent in [target] + list(target.parents):
                if get_providers_path(parent).exists():
                    return parent
            return target
        return None

    def _build_fallback_chain(
        self, backend_name: str, model_key: str, packet: ContextPacket
    ) -> list[dict[str, str]]:
        fallbacks: list[dict[str, str]] = []
        packet_fallbacks = _cs(packet.constraint_section).fallbacks
        if isinstance(packet_fallbacks, list):
            for fb in packet_fallbacks:
                if isinstance(fb, dict) and fb.get("backend"):
                    fallbacks.append({
                        "backend": str(fb["backend"]),
                        "model": str(fb.get("model", "default")),
                    })
        return fallbacks

    def _resolve_backend(
        self, packet: ContextPacket, backend_name: str | None
    ) -> AbstractBackend:
        name = (
            backend_name
            or _cs(packet.constraint_section).backend
            or self._default_backend
        )
        try:
            return self._plugin_registry.get(name)
        except KeyError:
            for fallback in ("api", "cli", "editor"):
                if self._plugin_registry.has_backend(fallback):
                    return self._plugin_registry.get(fallback)
            raise BackendError(f"No backends available (requested: {name})")

    def attach_repo_tool(
        self,
        packet: ContextPacket,
        invocation: Invocation,
    ) -> None:
        """Attach the RepoTool to the invocation if configured."""
        if invocation.available_tools:
            return

        target = packet.target_directory
        if not target or str(target) == ".":
            return

        repo_root = target.resolve()
        for parent in [repo_root] + list(repo_root.parents):
            if (parent / ".git").exists():
                repo_root = parent
                break

        agent_role_str = _cs(packet.constraint_section).agent_role
        if not agent_role_str:
            return

        from harness.agents.agent_registry import get_agent
        agent_spec = get_agent(agent_role_str)
        if agent_spec is None:
            return

        perms = agent_spec.tool_permissions
        if perms is None:
            return

        tools = []
        repo_tool = RepoTool(
            repo_root=repo_root,
            write_allowed=perms.write,
            write_prefixes=perms.write_prefixes,
        )
        invocation.tool_registry["repo_tool"] = repo_tool
        tools.append(repo_tool.tool_spec())

        if perms.web_search:
            self.attach_web_tool(packet, invocation)

        invocation.available_tools = tools

    def attach_web_tool(
        self,
        packet: ContextPacket,
        invocation: Invocation,
    ) -> None:
        """Attach the WebSearchTool to the invocation."""
        from harness.tools.web_search import WebSearchTool

        web_tool = WebSearchTool()
        invocation.tool_registry["web_search"] = web_tool
        if invocation.available_tools is None:
            invocation.available_tools = []

        existing_names = {
            t.get("function", {}).get("name", "")
            for t in invocation.available_tools
        }
        spec = web_tool.tool_spec()
        spec_name = spec.get("function", {}).get("name", "")
        if spec_name not in existing_names:
            invocation.available_tools.append(spec)


def _safety_rmtree(path: str) -> None:
    """Remove a temp directory safely.

    Only removes paths matching safety criteria to prevent
    accidental deletion of project directories.
    """
    import os
    import shutil

    p = Path(path).resolve()
    safe_prefixes = ("harness_simple_", "harness_agent_", "tmp", "tmp_")

    for parent in [p] + list(p.parents):
        if (parent / ".git").is_dir():
            raise RuntimeError(
                f"REFUSED: cannot rmtree '{p}' — contains a .git repo"
            )

    if not p.name.startswith(safe_prefixes):
        raise RuntimeError(
            f"REFUSED: cannot rmtree '{p}' — name '{p.name}' "
            f"does not start with a safe prefix"
        )

    if not p.is_absolute():
        raise RuntimeError(f"REFUSED: cannot rmtree '{p}' — not absolute")

    shutil.rmtree(str(p), ignore_errors=True)
