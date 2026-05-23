"""Agent runner — orchestrates backend execution.

Ties together ContextPacket, backends, and Temporal activities.
Handles backend resolution, execution, artifact collection, and
result formatting.

Architecture §2.3 — Agent System (Runner).

Wave 12a: Provider resolution and fallback chain. The runner loads
provider configurations from the project and user configs, resolves
the provider + model for each agent invocation, and passes the
resolved config to the backend via ``Invocation.resolved_config``.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.context import ContextPacket, OutputContract
from harness.agents.backends.base import (
    AbstractBackend,
    BackendError,
    BackendResult,
)
from harness.agents.plugin_registry import PluginRegistry
from harness.agents.repo_tool import RepoTool
from harness.agents.agent_registry import (
    CriticLoopConfig,
    CriticLoopIteration,
    CriticLoopState,
    get_agent,
    get_default_critic_loop_config,
    AgentRole,
    ToolPermissions,
)
from harness.agents.cycle import (
    CycleConvergence,
    CycleResult,
    CycleRunner,
    CycleRunnerDefinition,
    CycleStep,
)
from harness.paths import get_providers_path
from harness.config.provider_registry import load_providers

logger = logging.getLogger(__name__)


# ── Safety: guarded rmtree ────────────────────────────────────────────────────

_SAFE_DELETABLE_PREFIXES: tuple[str, ...] = (
    "harness_simple_",
    "harness_agent_",
    "tmp",
    "tmp_",
)
"""Prefixes of temp directories that are safe to rmtree.

Any path that does NOT start with one of these prefixes, or that
contains a ``.git`` directory, will be refused by ``_safety_rmtree()``.
This prevents accidental deletion of project repos.
"""


def _safety_rmtree(path: str | os.PathLike) -> None:
    """Remove *path* only if it is a temporary directory we created.

    Safety rules (all must pass):
      1. Path must not contain a ``.git`` directory.
      2. The final component of the path must start with one of the
         safe prefixes defined in ``_SAFE_DELETABLE_PREFIXES``.
      3. Path must be an absolute path.

    Raises ``RuntimeError`` if the path looks like a real project repo.
    """
    p = Path(path).resolve()

    # Rule 1: must not contain a .git directory anywhere in the tree
    # (check parent chain up to root)
    for parent in [p] + list(p.parents):
        if (parent / ".git").is_dir():
            raise RuntimeError(
                f"REFUSED: cannot rmtree '{p}' — it contains a .git repo at "
                f"'{parent}'. Use Trash or manual deletion instead."
            )

    # Rule 2: final component must start with a safe prefix
    if not p.name.startswith(_SAFE_DELETABLE_PREFIXES):
        raise RuntimeError(
            f"REFUSED: cannot rmtree '{p}' — name '{p.name}' does not "
            f"start with a safe prefix {_SAFE_DELETABLE_PREFIXES}. "
            f"Use Trash or manual deletion instead."
        )

    # Rule 3: must be absolute
    if not p.is_absolute():
        raise RuntimeError(
            f"REFUSED: cannot rmtree '{p}' — not an absolute path."
        )

    shutil.rmtree(str(p), ignore_errors=True)


@dataclass
class RunnerConfig:
    """Configuration for the agent runner."""

    default_backend: str = "api"
    timeout_seconds: int = 600
    temp_dir_prefix: str = "harness_agent_"
    cleanup_temp_dirs: bool = True
    project_dir: str = ""
    """Optional project root directory for provider config lookup.

    If empty, the runner tries to derive it from the packet's
    ``target_directory`` by looking for a ``.harness/providers.yaml`` file.
    """
    max_fallbacks: int = 3
    """Maximum number of fallback backends to try before failing."""

    @classmethod
    def from_dict(cls, config: dict) -> RunnerConfig:
        c = cls()
        if "default_backend" in config:
            c.default_backend = config["default_backend"]
        if "timeout_seconds" in config:
            c.timeout_seconds = int(config["timeout_seconds"])
        if "temp_dir_prefix" in config:
            c.temp_dir_prefix = config["temp_dir_prefix"]
        if "cleanup_temp_dirs" in config:
            c.cleanup_temp_dirs = bool(config["cleanup_temp_dirs"])
        if "project_dir" in config:
            c.project_dir = config["project_dir"]
        if "max_fallbacks" in config:
            c.max_fallbacks = int(config["max_fallbacks"])
        return c


@dataclass
class CriticLoopResult:
    """Result of a design-critic multi-agent loop.

    Contains the final convergence state and the full iteration history
    so callers can inspect what changed in each cycle.
    """

    converged: bool = False
    """Whether the loop converged (critic signalled no new issues)."""

    iterations: int = 0
    """Number of architect→critic cycles that actually ran."""

    iteration_results: list[CriticLoopIteration] = field(default_factory=list)
    """Per-iteration snapshot of architect and critic outputs."""

    final_state: CriticLoopState = CriticLoopState.RUNNING
    """The terminal state of the loop."""

    error_message: str = ""
    """Error message if the loop failed, empty on success."""


class CriticLoopError(Exception):
    """Raised when the critic loop encounters a terminal error."""


class AgentRunner:
    """Orchestrates agent backend execution.

    Usage:

        runner = AgentRunner(config)
        result = await runner.run(packet)

    Or within a Temporal activity:

        runner = AgentRunner()
        result = await runner.run(
            packet,
            backend_name="api",
            use_temp_dir=True,
        )
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = RunnerConfig.from_dict(config or {})
        PluginRegistry.initialize(config)

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

        # 1. Resolve backend name
        resolved_name = (
            backend_name
            or packet.constraint_section.get("backend")
            or self._config.default_backend
        )

        # 2. Resolve provider config
        project_dir = self._resolve_project_dir(packet)
        model_key = packet.constraint_section.get("model", "")

        providers = load_providers(project_dir) if project_dir else None
        resolved_config = providers.get_resolved(resolved_name) if providers else None

        # Determine the actual model string
        if resolved_config and model_key and providers:
            try:
                model_str = providers.resolve_model(resolved_name, model_key)
            except Exception:
                model_str = model_key
        elif model_key:
            model_str = model_key
        else:
            model_str = ""

        # Get fallback chain from config or from packet constraints
        fallback_chain = self._build_fallback_chain(
            resolved_name, model_key, packet
        )

        # 3. Resolve backend and run
        backend = self._resolve_backend(packet, resolved_name)
        result = await self._run_with_resolved_config(
            packet, backend, resolved_config, model_str, use_temp_dir
        )

        # 4. Fallback chain: if primary failed, try each fallback in order
        if result.status != "success" and fallback_chain:
            logger.info(
                "Primary backend '%s' returned '%s', trying %d fallbacks",
                resolved_name,
                result.status,
                len(fallback_chain),
            )
            for i, fallback in enumerate(fallback_chain):
                if i >= self._config.max_fallbacks:
                    break

                fb_name = fallback.get("backend", "")
                fb_model = fallback.get("model", "")
                if not fb_name:
                    continue

                logger.info(
                    "Trying fallback %d: backend='%s', model='%s'",
                    i + 1, fb_name, fb_model,
                )

                fb_config = providers.get_resolved(fb_name) if providers else None
                fb_model_str = fb_model
                if fb_config and fb_model and providers:
                    try:
                        fb_model_str = providers.resolve_model(fb_name, fb_model)
                    except Exception:
                        fb_model_str = fb_model

                try:
                    fb_backend = self._resolve_backend(packet, fb_name)
                except (KeyError, BackendError) as exc:
                    logger.warning(
                        "Fallback backend '%s' unavailable: %s", fb_name, exc
                    )
                    continue

                fb_result = await self._run_with_resolved_config(
                    packet, fb_backend, fb_config, fb_model_str, use_temp_dir
                )

                if fb_result.status == "success":
                    elapsed = int((time.monotonic() - start_time) * 1000)
                    fb_result.metrics["runner_duration_ms"] = elapsed
                    fb_result.metrics["fallback_used"] = True
                    fb_result.metrics["fallback_index"] = i + 1
                    fb_result.errors.append(
                        f"Fallback {i + 1} ('{fb_name}') used after "
                        f"primary '{resolved_name}' failed"
                    )
                    return fb_result

            # All fallbacks failed — return the primary result
            elapsed = int((time.monotonic() - start_time) * 1000)
            result.metrics["runner_duration_ms"] = elapsed
            result.metrics["fallback_attempted"] = len(fallback_chain)
            return result

        # 5. Fill in timing
        elapsed = int((time.monotonic() - start_time) * 1000)
        result.metrics["runner_duration_ms"] = elapsed
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
        """Run a backend with resolved configuration.

        Sets up temp dir, prepares invocation, attaches resolved config,
        and executes.
        """
        # Optionally create temp workspace
        temp_dir: str | None = None
        original_target = str(packet.target_directory) if packet.target_directory else ""

        if use_temp_dir:
            temp_dir = tempfile.mkdtemp(prefix=self._config.temp_dir_prefix)
            packet.target_directory = Path(temp_dir)

        try:
            # Prepare invocation
            invocation = await backend.prepare(packet)

            # Attach resolved config
            if resolved_config:
                invocation.resolved_config = resolved_config
            if model:
                invocation.model = model

            # Inject RepoTool if the agent has tool permissions (Wave 13)
            self._attach_repo_tool(packet, invocation)

            # Execute
            result = await backend.run(invocation)

            return result

        except BackendError as exc:
            return BackendResult(
                status="failure",
                errors=[str(exc)],
                metrics={"backend": backend.name},
            )

        finally:
            # Cleanup temp dir if used
            if temp_dir and self._config.cleanup_temp_dirs:
                _safety_rmtree(temp_dir)
                if original_target:
                    packet.target_directory = Path(original_target)

    def _resolve_project_dir(self, packet: ContextPacket) -> Path | None:
        """Derive the project root directory.

        Resolution order:
        1. ``RunnerConfig.project_dir`` (if set)
        2. ``target_directory`` traversal upwards looking for ``.harness/providers.yaml``
        3. ``target_directory`` itself (for minimal/embedded setups)
        """
        if self._config.project_dir:
            return Path(self._config.project_dir)

        if packet.target_directory:
            target = Path(packet.target_directory).resolve()
            # Walk up looking for .harness/providers.yaml
            for parent in [target] + list(target.parents):
                if get_providers_path(parent).exists():
                # Note: prefer get_providers_path() once root is known
                    return parent
            # Fall back to target directory
            return target

        return None

    def _build_fallback_chain(
        self,
        backend_name: str,
        model_key: str,
        packet: ContextPacket,
    ) -> list[dict[str, str]]:
        """Build the fallback chain from packet constraints.

        Falls back. Looks at the ``fallbacks`` key in
        ``constraint_section`` for a list of ``{backend, model}`` dicts.
        """
        fallbacks: list[dict[str, str]] = []

        # Check packet constraints first
        packet_fallbacks = packet.constraint_section.get("fallbacks")
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
        """Resolve which backend to use.

        Resolution order:
        1. Explicit backend_name parameter
        2. packet.constraint_section['backend']
        3. RunnerConfig.default_backend
        """
        name = (
            backend_name
            or packet.constraint_section.get("backend")
            or self._config.default_backend
        )

        try:
            return PluginRegistry.get(name)
        except KeyError:
            # Fallback chain: try api, then cli, then first available
            for fallback in ("api", "cli", "editor"):
                if PluginRegistry.has_backend(fallback):
                    logger.warning(
                        "Backend '%s' not found, falling back to '%s'",
                        name, fallback,
                    )
                    return PluginRegistry.get(fallback)

            raise BackendError(f"No backends available (requested: {name})")

    async def run_simple(
        self,
        spec_content: str,
        architecture_rules: list[str] | None = None,
        backend_name: str | None = None,
        model: str | None = None,
        project_dir: str | Path | None = None,
        agent_role: str | None = None,
    ) -> str:
        """Convenience method: run with a spec string, get back content.

        Useful for quick agent invocations where you just want the
        produced text, not the full BackendResult.

        When *project_dir* is provided, the RepoTool is attached and
        the agent can browse files during analysis (requires *agent_role*
        with read-only tool permissions).
        """
        from harness.agents.context import ContextPacket, OutputContract

        constraint_section: dict[str, str] = {
            "backend": backend_name or self._config.default_backend,
        }
        if model:
            constraint_section["model"] = model
        if agent_role:
            constraint_section["agent_role"] = agent_role

        target_dir = Path(project_dir) if project_dir else Path(
            tempfile.mkdtemp(prefix="harness_simple_")
        )

        packet = ContextPacket(
            engagement_id="_simple",
            phase_name="direct",
            task_id=spec_content[:40],
            spec_content=spec_content,
            architecture_rules=architecture_rules or [],
            target_directory=target_dir,
            output_contract=OutputContract(),
            constraint_section=constraint_section,
        )

        result = await self.run(packet, backend_name=backend_name)

        # Only clean up temp dirs we created, never real project dirs
        if self._config.cleanup_temp_dirs and not project_dir:
            _safety_rmtree(str(packet.target_directory))

        if result.status == "success":
            return "\n".join(result.artifacts.values())
        return f"Error: {'; '.join(result.errors)}"

    async def run_critic_loop(
        self,
        spec_content: str,
        architecture_rules: list[str] | None = None,
        engagement_dir: Path | None = None,
        config: CriticLoopConfig | None = None,
        backend_name: str | None = None,
    ) -> CriticLoopResult:
        """Run a complete design-critic multi-agent loop.

        Orchestrates:

            architect (writes design) → critic (reviews) →
            architect (revises) → critic (re-reviews) → …

        until convergence or the maximum iteration limit.  The loop
        uses **files as memory** — each agent writes artifacts to
        *engagement_dir*, and subsequent iterations read previous
        outputs via input artifacts and the RepoTool.

        Args:
            spec_content:
                The task description / requirements for the architect.
            architecture_rules:
                Optional architecture constraints or guidelines.
            engagement_dir:
                Directory where engagement artifacts live.  If
                ``None``, a temporary directory is created (and
                cleaned up on success).
            config:
                Critic loop configuration.  Defaults from
                :func:`~harness.agents.agent_registry.get_default_critic_loop_config`
                if not provided.
            backend_name:
                Backend name for all agent invocations.  ``None``
                falls back to the runner's default_backend.

        Returns:
            :class:`CriticLoopResult` with per-iteration snapshots.

        Raises:
            :class:`CriticLoopError` on fatal errors.

        Example::

            runner = AgentRunner()
            result = await runner.run_critic_loop(
                spec_content="Build an OAuth token refresh system",
                config=CriticLoopConfig(max_iterations=3),
            )
            if result.converged:
                print(f"Converged in {result.iterations} iteration(s)")
        """
        cfg = config or get_default_critic_loop_config()
        target_dir = (
            engagement_dir
            or Path(tempfile.mkdtemp(prefix="critic_loop_"))
        )
        auto_cleanup = engagement_dir is None

        # Build a CycleRunnerDefinition from the critic loop config
        keywords = cfg.convergence_keywords

        cycle_def = CycleRunnerDefinition(
            name="critic-loop",
            steps=[
                CycleStep(agent=cfg.architect_role.value, step_type="produce",
                          artifact="design.md", max_retries=0),
                CycleStep(agent=cfg.critic_role.value, step_type="critique",
                          artifact="critique.md", max_retries=0),
            ],
            convergence=CycleConvergence(
                condition="agent_judgment",
                max_iterations=cfg.max_iterations,
                on_timeout="best_effort",
            ),
            initial_phase_artifact="requirements.md",
            final_artifact="design.md",
        )

        # Custom convergence: use CriticLoopConfig.convergence_keywords
        def critic_convergence_check(
            _definition: CycleRunnerDefinition,
            iteration: int,
            step_results: list,
            artifacts: dict[str, str],
        ) -> bool:
            """Check critic output for convergence keywords."""
            for sr in step_results:
                if sr.step_type == "critique" and sr.status == "success":
                    text = " ".join(
                        v.lower() for v in sr.artifacts.values()
                    )
                    for kw in keywords:
                        if kw.lower() in text:
                            return True
            return False

        # Run through the CycleRunner engine (reusing self as the agent runner)
        cycle_runner = CycleRunner(root=target_dir)
        cycle_runner._agent_runner = self

        try:
            cycle_result = await cycle_runner.run(
                definition=cycle_def,
                engagement_slug="_critic_loop",
                spec_content=spec_content,
                architecture_rules=architecture_rules or [],
                backend_name=backend_name,
                on_convergence_check=critic_convergence_check,
            )
        except Exception as exc:
            raise CriticLoopError(f"Critic loop failed: {exc}") from exc

        # Build iteration results directly from step results, using the
        # same convergence keywords for consistency
        iteration_results = _build_iterations_from_cycle(
            cycle_result, cfg.convergence_keywords
        )

        if cycle_result.status == "error":
            return CriticLoopResult(
                converged=False,
                iterations=cycle_result.iterations,
                iteration_results=iteration_results,
                final_state=CriticLoopState.ERROR,
                error_message=cycle_result.error or "Critic loop error",
            )

        if cycle_result.status == "complete":
            return CriticLoopResult(
                converged=True,
                iterations=cycle_result.iterations,
                iteration_results=iteration_results,
                final_state=CriticLoopState.CONVERGED,
            )

        # timeout (best_effort)
        return CriticLoopResult(
            converged=False,
            iterations=cycle_result.iterations,
            iteration_results=iteration_results,
            final_state=CriticLoopState.MAX_ITERATIONS_REACHED,
        )

    def _check_critic_convergence(
        self,
        critic_result: BackendResult,
        config: CriticLoopConfig,
    ) -> bool:
        """Check whether the critic signalled convergence.

        Tests all artifact text (case-insensitive) against the
        :attr:`CriticLoopConfig.convergence_keywords` list.  If any
        keyword is found in any artifact, the loop is considered
        converged.

        Override or extend this method in subclasses for custom
        convergence logic (e.g. parsing structured YAML frontmatter).

        Note:
            This is kept for backward compatibility. New code should
            use the CycleRunner engine directly with a custom
            ``on_convergence_check`` callback.
        """
        artifacts_text = " ".join(
            v.lower() for v in critic_result.artifacts.values()
        )
        for keyword in config.convergence_keywords:
            if keyword.lower() in artifacts_text:
                return True
        return False

    def _attach_repo_tool(
        self,
        packet: ContextPacket,
        invocation: Invocation,
    ) -> None:
        """Attach the RepoTool to the invocation if the agent has permissions.

        Looks up the agent role from ``constraint_section.agent_role``
        in the packet. If the agent has tool permissions configured,
        creates a :class:`~harness.agents.repo_tool.RepoTool` instance
        and populates:

        - ``invocation.available_tools`` — tool specs for the LLM API
        - ``invocation.tool_registry`` — the RepoTool instance itself

        If the requestor has already provided "available_tools" in
        the constraint section, those are used instead (manual override).
        """
        # Skip if tools are already attached
        if invocation.available_tools:
            return

        # Determine the repo root from the target directory
        target = packet.target_directory
        if not target or str(target) == ".":
            return

        repo_root = target.resolve()
        # Walk up looking for .git as the repo root marker
        for parent in [repo_root] + list(repo_root.parents):
            if (parent / ".git").exists():
                repo_root = parent
                break

        # Determine agent role
        agent_role_str = packet.constraint_section.get("agent_role", "")
        if not agent_role_str:
            # Without an agent role, we can't determine permissions
            return

        # Look up the agent spec
        try:
            agent_role = AgentRole(agent_role_str)
        except ValueError:
            logger.warning(
                "Unknown agent role '%s', skipping RepoTool attachment",
                agent_role_str,
            )
            return

        agent_spec = get_agent(agent_role)
        if agent_spec is None:
            logger.warning(
                "Agent spec not found for '%s', skipping RepoTool",
                agent_role_str,
            )
            return

        perms = agent_spec.tool_permissions
        if perms is None:
            logger.debug(
                "Agent '%s' has no tool permissions, skipping RepoTool",
                agent_role_str,
            )
            return

        # Create the tools & populate invocation
        from harness.tools.web_search import WebSearchTool

        tools = []

        # RepoTool
        repo_tool = RepoTool(
            repo_root=repo_root,
            write_allowed=perms.write,
            write_prefixes=perms.write_prefixes,
        )
        invocation.tool_registry["repo_tool"] = repo_tool
        tools.append(repo_tool.tool_spec())

        logger.info(
            "Attached RepoTool for agent '%s' (write=%s, prefixes=%s)",
            agent_role_str,
            perms.write,
            perms.write_prefixes or "any",
        )

        # WebSearchTool
        if perms.web_search:
            web_tool = WebSearchTool()
            invocation.tool_registry["web_search"] = web_tool
            tools.append(web_tool.tool_spec())
            logger.info(
                "Attached WebSearchTool for agent '%s'",
                agent_role_str,
            )

        invocation.available_tools = tools


def _build_iterations_from_cycle(
    cycle_result: CycleResult,
    convergence_keywords: list[str],
) -> list[CriticLoopIteration]:
    """Convert CycleResult step results to CriticLoopIteration list.

    Groups step results by iteration, pairs produce/critique, and uses
    the provided convergence_keywords to determine converged status per
    iteration — matching the same logic as run_critic_loop's callback.
    """
    from collections import defaultdict

    iteration_map: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"arch_arts": {}, "critic_arts": {}}
    )

    for sr in cycle_result.step_results:
        if sr.step_type == "produce":
            iteration_map[sr.iteration]["arch_arts"].update(sr.artifacts)
        elif sr.step_type in ("critique", "gate"):
            iteration_map[sr.iteration]["critic_arts"].update(sr.artifacts)

    iterations: list[CriticLoopIteration] = []
    for iter_num, data in sorted(iteration_map.items()):
        # Use the same convergence keywords as the crit loop callback
        converged = False
        text = " ".join(
            v.lower() for v in data["critic_arts"].values()
        )
        for kw in convergence_keywords:
            if kw.lower() in text:
                converged = True
                break

        iterations.append(CriticLoopIteration(
            iteration=iter_num,
            architect_artifacts=data["arch_arts"],
            critic_artifacts=data["critic_arts"],
            converged=converged,
        ))

    return iterations

