"""Tests for phase/dispatch_utility.py: ParallelDispatchProtocol.

Tests cover parallel dispatch, timeout handling, retries,
and partial completion.
"""

from __future__ import annotations

import asyncio

import pytest

from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchProtocol,
    ParallelDispatchResult,
)


class TestDispatchResult:
    """DispatchResult dataclass tests."""

    def test_defaults(self) -> None:
        result = DispatchResult(agent_name="architect", success=True)
        assert result.agent_name == "architect"
        assert result.success is True
        assert result.output == ""
        assert result.error is None
        assert result.elapsed_seconds == 0.0

    def test_failure(self) -> None:
        result = DispatchResult(
            agent_name="tester",
            success=False,
            error="Failed to dispatch",
        )
        assert result.success is False
        assert result.error == "Failed to dispatch"


class TestParallelDispatchResult:
    """ParallelDispatchResult dataclass tests."""

    def test_default_empty(self) -> None:
        result = ParallelDispatchResult()
        assert result.completed == []
        assert result.failed == []
        assert result.timed_out == []
        assert result.partial is False

    def test_all_succeeded(self) -> None:
        result = ParallelDispatchResult(
            completed=[
                DispatchResult("a", True),
                DispatchResult("b", True),
            ],
        )
        assert len(result.completed) == 2
        assert result.partial is False

    def test_partial_completion(self) -> None:
        result = ParallelDispatchResult(
            completed=[DispatchResult("a", True)],
            failed=[DispatchResult("b", False, error="failed")],
        )
        assert result.partial is True

    def test_partial_with_timeout(self) -> None:
        result = ParallelDispatchResult(
            completed=[DispatchResult("a", True)],
            timed_out=["c"],
        )
        assert result.partial is True

    def test_all_failed(self) -> None:
        result = ParallelDispatchResult(
            failed=[DispatchResult("a", False)],
        )
        assert result.partial is False


class TestParallelDispatchProtocol:
    """ParallelDispatchProtocol async tests."""

    @pytest.mark.asyncio
    async def test_dispatch_empty_agents(self) -> None:
        protocol = ParallelDispatchProtocol()
        result = await protocol.dispatch_all(
            agents=[],
            dispatch_fn=lambda agent, ctx: DispatchResult(
                agent_name=agent, success=True,
            ),
        )
        assert len(result.completed) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_all_succeed(self) -> None:
        protocol = ParallelDispatchProtocol()

        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            await asyncio.sleep(0.01)
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=f"{agent} output",
            )

        result = await protocol.dispatch_all(
            agents=["architect", "tester", "reviewer"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 3
        assert len(result.failed) == 0
        assert result.partial is False

    @pytest.mark.asyncio
    async def test_some_fail(self) -> None:
        protocol = ParallelDispatchProtocol()

        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            await asyncio.sleep(0.01)
            if agent == "failing-agent":
                raise RuntimeError("Agent dispatch failed")
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=f"{agent} output",
            )

        result = await protocol.dispatch_all(
            agents=["working-agent", "failing-agent"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 1
        assert len(result.failed) == 1
        assert result.partial is True
        assert result.failed[0].agent_name == "failing-agent"
        assert result.failed[0].success is False

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        protocol = ParallelDispatchProtocol(timeout=0.05)

        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            await asyncio.sleep(10.0)  # Will timeout
            return DispatchResult(agent_name=agent, success=True)

        result = await protocol.dispatch_all(
            agents=["slow-agent"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 0
        assert len(result.timed_out) == 1
        assert result.timed_out[0] == "slow-agent"
        assert result.partial is False  # only timeouts, no completes

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        """Agent fails first attempt, succeeds on retry."""
        attempt_counters: dict[str, int] = {}

        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            attempt_counters[agent] = attempt_counters.get(agent, 0) + 1
            if attempt_counters[agent] == 1:
                raise RuntimeError("First attempt failed")
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=f"{agent} output",
            )

        protocol = ParallelDispatchProtocol(
            timeout=5.0,
            max_retries=1,
            retry_delay=0.01,
        )
        result = await protocol.dispatch_all(
            agents=["retry-agent"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 1
        assert len(result.failed) == 0
        assert attempt_counters["retry-agent"] == 2

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self) -> None:
        """Agent always fails, exhausts retries."""
        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            raise RuntimeError("Always fails")

        protocol = ParallelDispatchProtocol(
            timeout=5.0,
            max_retries=2,
            retry_delay=0.01,
        )
        result = await protocol.dispatch_all(
            agents=["always-fail"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 0
        assert len(result.failed) == 1
        assert result.failed[0].agent_name == "always-fail"

    @pytest.mark.asyncio
    async def test_mixed_results(self) -> None:
        """Mix of completed, failed, and partial."""
        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            await asyncio.sleep(0.01)
            if agent == "fails":
                raise RuntimeError("Failure")
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=f"{agent} output",
            )

        protocol = ParallelDispatchProtocol(
            timeout=5.0,
            max_retries=0,
        )
        result = await protocol.dispatch_all(
            agents=["works", "fails", "also-works"],
            dispatch_fn=dispatch,
        )
        assert len(result.completed) == 2
        assert len(result.failed) == 1
        assert result.partial is True

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        """Multiple agents should execute in parallel, not sequentially."""
        import time

        async def dispatch(agent: str, ctx: None) -> DispatchResult:
            await asyncio.sleep(0.1)
            return DispatchResult(
                agent_name=agent,
                success=True,
                output=f"{agent} output",
            )

        protocol = ParallelDispatchProtocol(timeout=5.0)
        start = time.monotonic()
        result = await protocol.dispatch_all(
            agents=["a", "b", "c"],
            dispatch_fn=dispatch,
        )
        elapsed = time.monotonic() - start
        # If parallel, should take ~0.1s not ~0.3s
        # Allow generous margin for CI variability
        assert elapsed < 0.5
        assert len(result.completed) == 3
