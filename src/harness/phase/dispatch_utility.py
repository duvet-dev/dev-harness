"""Parallel dispatch protocol — V7 §6.3.

Provides parallel agent dispatch with configurable timeouts, retries,
and partial completion handling.

Used by StepDispatcher when step.parallel is True.

See V7 §5.3 for StepDispatcher integration and §6.3 for the flow.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from harness.errors import AgentTimeoutError, ParallelDispatchError
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.dispatch_utility")


@dataclass
class DispatchResult:
    """Result of dispatching a single agent.

    Attributes:
        agent_name: Name of the dispatched agent.
        success: Whether the agent completed successfully.
        output: The agent's output content.
        error: Error message if the agent failed.
        elapsed_seconds: Time taken for the dispatch.
    """

    agent_name: str
    success: bool
    output: str = ""
    error: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class ParallelDispatchResult:
    """Result of dispatching multiple agents in parallel.

    Attributes:
        completed: List of successfully completed DispatchResults.
        failed: List of failed DispatchResults.
        timed_out: List of agent names that timed out.
        partial: True if some agents completed and some failed.
    """

    completed: list[DispatchResult] = field(default_factory=list)
    failed: list[DispatchResult] = field(default_factory=list)
    timed_out: list[str] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        """True if some agents completed and others failed."""
        return bool(self.completed) and bool(self.failed or self.timed_out)


class ParallelDispatchProtocol:
    """Async parallel dispatch of multiple agents.

    Dispatches agents concurrently with configurable per-agent timeouts
    and retries. Supports partial completion handling.

    Usage::

        protocol = ParallelDispatchProtocol(timeout=30.0, max_retries=2)
        result = await protocol.dispatch_all(
            agents=["architect", "architecture-critic"],
            dispatch_fn=my_dispatch_func,
        )
        if result.partial:
            # Handle partial completion
            ...
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 1,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialise the parallel dispatch protocol.

        Args:
            timeout: Maximum seconds to wait for each agent dispatch.
            max_retries: Number of retries on failure for each agent.
            retry_delay: Seconds to wait between retries.
        """
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def dispatch_all(
        self,
        agents: list[str],
        dispatch_fn: Any,
        context: Any | None = None,
    ) -> ParallelDispatchResult:
        """Dispatch all agents in parallel.

        Args:
            agents: List of agent names to dispatch.
            dispatch_fn: Async callable accepting (agent_name, context)
                and returning DispatchResult.
            context: Optional context passed to each dispatch call.

        Returns:
            ParallelDispatchResult with completed, failed, and
            timed_out results.
        """
        if not agents:
            logger.warning("ParallelDispatchProtocol.dispatch_all — no agents")
            return ParallelDispatchResult()

        tasks = {
            agent: self._dispatch_with_retry(agent, dispatch_fn, context)
            for agent in agents
        }

        completed: list[DispatchResult] = []
        failed: list[DispatchResult] = []
        timed_out: list[str] = []

        for agent, task in tasks.items():
            try:
                result = await asyncio.wait_for(task, timeout=self._timeout)
                if result.success:
                    completed.append(result)
                else:
                    failed.append(result)
            except asyncio.TimeoutError:
                timed_out.append(agent)
                logger.warning(
                    "ParallelDispatchProtocol — timeout",
                    extra={
                        "agent": agent,
                        "timeout": self._timeout,
                    },
                )

        if failed or timed_out:
            logger.warning(
                "ParallelDispatchProtocol — partial/failure",
                extra={
                    "completed": len(completed),
                    "failed": len(failed),
                    "timed_out": len(timed_out),
                },
            )

        return ParallelDispatchResult(
            completed=completed,
            failed=failed,
            timed_out=timed_out,
        )

    async def _dispatch_with_retry(
        self,
        agent_name: str,
        dispatch_fn: Any,
        context: Any | None,
    ) -> DispatchResult:
        """Dispatch an agent with retry logic."""
        last_error: str | None = None

        for attempt in range(1 + self._max_retries):
            try:
                result = await dispatch_fn(agent_name, context)
                result.agent_name = agent_name
                return result
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "ParallelDispatchProtocol — retry",
                    extra={
                        "agent": agent_name,
                        "attempt": attempt + 1,
                        "error": last_error,
                    },
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay)

        return DispatchResult(
            agent_name=agent_name,
            success=False,
            error=last_error,
        )
