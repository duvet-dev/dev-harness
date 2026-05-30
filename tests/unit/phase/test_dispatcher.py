"""Tests for phase/dispatcher.py: StepDispatcher.

Tests cover agent resolution (team → TeamRegistry, agents → direct),
guidelines injection, sequential/parallel dispatch, error handling,
and LeadAggregator integration.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness.artifact.repository import Artifact
from harness.artifact.types import ArtifactType
from harness.errors import (
    StepDispatchError,
    UnknownTeamError,
)
from harness.phase.aggregator import AggregateResult, LeadAggregator
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchProtocol,
    ParallelDispatchResult,
)
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import LoopConfig, Step
from harness.team.defaults import get_builtin_teams
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


@pytest.fixture
def team_registry() -> TeamRegistry:
    """Create a TeamRegistry with built-in teams."""
    return TeamRegistry(builtin=get_builtin_teams())


@pytest.fixture
def dispatcher(team_registry: TeamRegistry) -> StepDispatcher:
    """Create a StepDispatcher with a simple dispatch stub."""
    return StepDispatcher(team_registry=team_registry)


class TestStepDispatcherInit:
    """StepDispatcher construction tests."""

    def test_default_dispatch_fn(self) -> None:
        d = StepDispatcher(team_registry=TeamRegistry(builtin=[]))
        assert d._dispatch_fn is not None

    def test_custom_parallel_protocol(self) -> None:
        proto = ParallelDispatchProtocol(timeout=99.0)
        d = StepDispatcher(
            team_registry=TeamRegistry(builtin=[]),
            parallel_protocol=proto,
        )
        assert d._parallel._timeout == 99.0


class TestResolveAgents:
    """_resolve_agents tests."""

    def test_resolve_from_team(self, team_registry: TeamRegistry) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(team="architecture")
        agents = d._resolve_agents(step)
        assert "architect" in agents
        assert "architecture-critic" in agents
        assert "code-critic" in agents
        assert "security-critic" in agents

    def test_resolve_from_agents(self, team_registry: TeamRegistry) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(agents=["architect", "tester"])
        agents = d._resolve_agents(step)
        assert agents == ["architect", "tester"]

    def test_resolve_unknown_team(self, team_registry: TeamRegistry) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(team="nonexistent-team")
        with pytest.raises(UnknownTeamError):
            d._resolve_agents(step)

    def test_resolve_no_agents_no_team(
        self, team_registry: TeamRegistry
    ) -> None:
        d = StepDispatcher(team_registry=team_registry)
        # A loop step with no agents/team
        step = Step(loop=LoopConfig(count=1))
        with pytest.raises(StepDispatchError):
            d._resolve_agents(step)


class TestGetGuidelines:
    """_get_guidelines tests (D36)."""

    def test_guidelines_for_team(self, team_registry: TeamRegistry) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(team="architecture")
        guidelines = d._get_guidelines(step)
        assert guidelines is not None
        assert "Architecture Team Guidelines" in guidelines
        assert "safety-first" in guidelines

    def test_no_guidelines_for_direct_agents(
        self, team_registry: TeamRegistry
    ) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(agents=["architect"])
        guidelines = d._get_guidelines(step)
        assert guidelines is None

    def test_guidelines_for_team_without_guidelines(
        self, team_registry: TeamRegistry
    ) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(team="review")  # review team has None guidelines
        guidelines = d._get_guidelines(step)
        assert guidelines is None

    def test_guidelines_unknown_team(
        self, team_registry: TeamRegistry
    ) -> None:
        d = StepDispatcher(team_registry=team_registry)
        step = Step(team="nonexistent")
        # Should return None gracefully, not crash
        guidelines = d._get_guidelines(step)
        assert guidelines is None


class TestDispatch:
    """StepDispatcher.dispatch tests."""

    @pytest.mark.asyncio
    async def test_dispatch_sequential(self, team_registry: TeamRegistry) -> None:
        results: list[str] = []

        async def track_dispatch(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            results.append(agent)
            return f"{agent} completed"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=track_dispatch,
        )
        step = Step(agents=["architect", "tester"])
        result = await d.dispatch(step)
        assert result.success is True
        assert len(results) == 2
        assert results == ["architect", "tester"]
        assert len(result.artifacts) == 2

    @pytest.mark.asyncio
    async def test_dispatch_sequential_failure(
        self, team_registry: TeamRegistry
    ) -> None:
        async def failing_dispatch(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            if agent == "failing":
                raise RuntimeError("Dispatch crashed")
            return f"{agent} completed"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=failing_dispatch,
        )
        step = Step(agents=["architect", "failing"])
        result = await d.dispatch(step)
        assert result.success is False
        assert "failing" in (result.error or "")

    @pytest.mark.asyncio
    async def test_dispatch_parallel(self, team_registry: TeamRegistry) -> None:
        results: list[str] = []

        async def track_dispatch(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            results.append(agent)
            return f"{agent} completed"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=track_dispatch,
        )
        step = Step(agents=["architect", "tester"], parallel=True)
        result = await d.dispatch(step)
        # Both should have been dispatched
        assert set(results) == {"architect", "tester"}

    @pytest.mark.asyncio
    async def test_dispatch_with_guidelines_injection(
        self, team_registry: TeamRegistry
    ) -> None:
        """Guidelines should be passed to dispatch_fn."""
        received_guidelines: list[str | None] = []

        async def capture_guidelines(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            received_guidelines.append(guidelines)
            return f"{agent} done"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=capture_guidelines,
        )
        step = Step(team="architecture")
        await d.dispatch(step)
        # All 4 architecture team agents should have received guidelines
        assert len(received_guidelines) == 4
        for g in received_guidelines:
            assert g is not None
            assert "Architecture Team Guidelines" in g

    @pytest.mark.asyncio
    async def test_dispatch_with_lead_aggregator(
        self, team_registry: TeamRegistry
    ) -> None:
        """LeadAggregator should process parallel results."""
        async def simple_dispatch(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            return f"{agent} report"

        aggregator = LeadAggregator()
        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=simple_dispatch,
            lead_aggregator=aggregator,
        )
        step = Step(agents=["architect", "tester"], parallel=True)
        result = await d.dispatch(step)
        assert result.success is True
        assert len(result.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_dispatch_team_step(self, team_registry: TeamRegistry) -> None:
        """Team steps should resolve to the team's agents."""
        dispatched: list[str] = []

        async def record(agent: str, ctx: Any, step: Step | None = None,
                         guidelines: str | None = None) -> str:
            dispatched.append(agent)
            return f"{agent} done"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=record,
        )
        step = Step(team="coding", parallel=True)
        result = await d.dispatch(step)
        assert result.success is True
        assert "coding-agent" in dispatched
        assert "testing-agent" in dispatched

    @pytest.mark.asyncio
    async def test_dispatch_no_agents_returns_error(
        self, team_registry: TeamRegistry
    ) -> None:
        """Empty team should return an error StepResult."""
        empty_registry = TeamRegistry(builtin=[
            AgentTeam(name="empty", agents=[]),
        ])
        d = StepDispatcher(team_registry=empty_registry)
        step = Step(team="empty")
        result = await d.dispatch(step)
        assert result.success is False
        assert "No agents resolved" in (result.error or "")

    @pytest.mark.asyncio
    async def test_dispatch_with_default_stub(self, team_registry: TeamRegistry) -> None:
        """Default _stub_dispatch is used when no custom dispatch_fn given (line 326)."""
        d = StepDispatcher(team_registry=team_registry)
        step = Step(agents=["architect"])
        result = await d.dispatch(step)
        assert result.success is True
        assert len(result.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_dispatch_with_parallel_timeout(
        self, team_registry: TeamRegistry
    ) -> None:
        """Agents that timeout should be reported."""
        async def slow_dispatch(
            agent: str, ctx: Any, step: Step | None = None,
            guidelines: str | None = None,
        ) -> str:
            await asyncio.sleep(10.0)
            return "too late"

        d = StepDispatcher(
            team_registry=team_registry,
            dispatch_fn=slow_dispatch,
            parallel_protocol=ParallelDispatchProtocol(timeout=0.05),
        )
        step = Step(agents=["slowpoke"], parallel=True)
        result = await d.dispatch(step)
        # Timeout means no success or failure
        assert result.success is False
