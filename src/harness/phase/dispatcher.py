"""StepDispatcher — agent/team step dispatch — V7 §5.3.

Resolves agents from team references or explicit lists, injects team
guidelines, and dispatches to individual agents (sequential or
parallel) with timeout and retry handling.

Step output naming convention (V7 §2.2):
  .pending.md → in progress
  .md → completed successfully
  .failed.md → terminal error

See V7 §5.3 for the full specification and §6.3 for the flow.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from harness.artifact.repository import Artifact, ArtifactRepository
from harness.artifact.types import ArtifactType
from harness.errors import (
    AgentTimeoutError,
    ParallelDispatchError,
    StepDispatchError,
    UnknownTeamError,
)
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchProtocol,
)
from harness.phase.model import Step
from harness.team.registry import TeamRegistry
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.dispatcher")


@dataclass
class StepResult:
    """Result of dispatching a single step.

    Attributes:
        success: True if the step completed successfully.
        artifacts: List of artifacts produced by the step.
        error: Error message if the step failed.
        trace_id: Trace ID for structured logging.
        partial: True if some agents completed and some failed
            (parallel dispatch only).
        dissenting_notes: List of dissenting agent outputs attached
            by the LeadAggregator (V7 §5.7).
    """

    success: bool
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    trace_id: str = ""
    partial: bool = False
    dissenting_notes: list[str] = field(default_factory=list)


class StepDispatcher:
    """Dispatches agent/team steps to individual agents.

    Usage::

        dispatcher = StepDispatcher(
            team_registry=TeamRegistry(...),
            dispatch_fn=my_async_dispatch,
            parallel_protocol=ParallelDispatchProtocol(...),
            artifact_repo=ArtifactRepository(...),
        )
        result = await dispatcher.dispatch(step, context)
    """

    def __init__(
        self,
        team_registry: TeamRegistry,
        dispatch_fn: Any = None,
        parallel_protocol: ParallelDispatchProtocol | None = None,
        artifact_repo: ArtifactRepository | None = None,
        lead_aggregator: Any = None,
    ) -> None:
        """Initialise the StepDispatcher.

        Args:
            team_registry: Registry for resolving team references.
            dispatch_fn: Async callable for dispatching individual
                agents. Signature: async (agent, context) -> str.
                If None, dispatcher uses a stub that returns empty.
            parallel_protocol: Parallel dispatch handler. Created
                with defaults if not provided.
            artifact_repo: Repository for saving step output
                artifacts. Created with defaults if not provided.
            lead_aggregator: Optional LeadAggregator for aggregating
                parallel dispatch results.
        """
        self._team_registry = team_registry
        self._dispatch_fn = dispatch_fn or self._stub_dispatch
        self._parallel = parallel_protocol or ParallelDispatchProtocol()
        self._artifact_repo = artifact_repo or ArtifactRepository()
        self._lead_aggregator = lead_aggregator

    def _resolve_agents(self, step: Step) -> list[str]:
        """Resolve agent list from team reference or explicit list.

        If step.team is set, resolves via TeamRegistry. Otherwise
        returns step.agents directly.

        Args:
            step: The step to resolve agents for.

        Returns:
            List of agent string names.

        Raises:
            UnknownTeamError: If step references a team that doesn't
                exist in the TeamRegistry.
            StepDispatchError: If step has no agents and no team.
        """
        if step.team:
            team = self._team_registry.resolve(step.team)
            return team.agents
        if step.agents:
            return step.agents
        raise StepDispatchError(
            "Step has neither agents nor team specified"
        )

    def _get_guidelines(self, step: Step) -> str | None:
        """Get team guidelines if step references a team (D36).

        Guidelines are injected at step dispatch time — step-scoped,
        not agent-scoped. A single agent participating in different
        teams across steps receives different guidelines each time.

        Args:
            step: The step to check for team guidelines.

        Returns:
            Team guidelines string, or None if no team reference
            or the team has no guidelines.
        """
        if step.team:
            try:
                team = self._team_registry.resolve(step.team)
                return team.guidelines
            except UnknownTeamError:
                logger.warning(
                    "StepDispatcher._get_guidelines — unknown team",
                    extra={"team": step.team},
                )
                return None
        return None

    async def dispatch(
        self,
        step: Step,
        context: Any | None = None,
    ) -> StepResult:
        """Dispatch a step to its agents.

        Handles agent resolution, guidelines injection, sequential
        vs parallel dispatch, timeouts, retries, and lead aggregation.

        Args:
            step: The step to dispatch.
            context: Optional context passed to the dispatch function.

        Returns:
            StepResult with artifacts and status.

        Raises:
            StepDispatchError: If agent resolution fails.
        """
        agents = self._resolve_agents(step)
        guidelines = self._get_guidelines(step)

        if not agents:
            return StepResult(
                success=False,
                error="No agents resolved for step (empty team?)",
            )

        logger.info(
            "StepDispatcher.dispatch",
            extra={
                "agents": agents,
                "has_guidelines": guidelines is not None,
                "parallel": step.parallel,
            },
        )

        if step.parallel:
            return await self._dispatch_parallel(
                agents, step, context, guidelines
            )
        else:
            return await self._dispatch_sequential(
                agents, step, context, guidelines
            )

    async def _dispatch_parallel(
        self,
        agents: list[str],
        step: Step,
        context: Any | None,
        guidelines: str | None,
    ) -> StepResult:
        """Dispatch all agents in parallel."""
        async def dispatch_one(agent: str, ctx: Any) -> DispatchResult:
            content = await self._dispatch_fn(
                agent, ctx, step, guidelines
            )
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=content or "",
            )

        parallel_result = await self._parallel.dispatch_all(
            agents=agents,
            dispatch_fn=dispatch_one,
            context=context,
        )

        # Apply lead aggregation if available
        if self._lead_aggregator:
            aggregated = await self._lead_aggregator.aggregate(
                results=parallel_result,
                step=step,
            )
            return StepResult(
                success=aggregated.success,
                artifacts=aggregated.artifacts
                or self._make_artifacts(parallel_result.completed, step),
                error=aggregated.error,
                partial=parallel_result.partial,
                dissenting_notes=aggregated.dissenting_notes or [],
            )

        # Without lead aggregator: flatten completed results
        artifacts = self._make_artifacts(
            parallel_result.completed, step
        )
        partial = parallel_result.partial
        error = None

        if parallel_result.failed or parallel_result.timed_out:
            error = (
                f"{len(parallel_result.failed)} agent(s) failed, "
                f"{len(parallel_result.timed_out)} timed out"
            )

        return StepResult(
            success=not bool(parallel_result.failed or parallel_result.timed_out),
            artifacts=artifacts,
            error=error,
            partial=partial,
        )

    async def _dispatch_sequential(
        self,
        agents: list[str],
        step: Step,
        context: Any | None,
        guidelines: str | None,
    ) -> StepResult:
        """Dispatch agents sequentially (one after another)."""
        artifacts: list[Artifact] = []

        for agent in agents:
            try:
                output = await self._dispatch_fn(
                    agent, context, step, guidelines
                )
                artifact = Artifact(
                    type=ArtifactType.SUMMARY,
                    content=output or "",
                    path=f"step_{agent}.md",
                )
                artifacts.append(artifact)
            except Exception as e:
                logger.warning(
                    "StepDispatcher — sequential dispatch failed",
                    extra={"agent": agent, "error": str(e)},
                )
                return StepResult(
                    success=False,
                    artifacts=artifacts,
                    error=f"Agent '{agent}' dispatch failed: {e}",
                )

        return StepResult(success=True, artifacts=artifacts)

    def _make_artifacts(
        self,
        results: list[Any],
        step: Step,
    ) -> list[Artifact]:
        """Create artifacts from completed dispatch results."""
        artifacts: list[Artifact] = []
        for result in results:
            output = getattr(result, "output", "") or getattr(result, "content", "") or ""
            if output:
                artifact = Artifact(
                    type=step.output[0] if step.output else ArtifactType.SUMMARY,
                    content=output,
                    path=f"step_{getattr(result, 'agent_name', 'unknown')}.md",
                )
                artifacts.append(artifact)
        return artifacts

    async def _stub_dispatch(
        self,
        agent: str,
        context: Any | None,
        step: Step | None = None,
        guidelines: str | None = None,
    ) -> str:
        """Stub dispatch function for testing.

        Real implementations will route to the agent runner.
        """
        return f"{agent} completed"
