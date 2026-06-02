"""Phase orchestration package.

Core recursive step model, phase definitions, state management,
step dispatch, parallel dispatch, and lead aggregation.
"""

from __future__ import annotations

from harness.phase.aggregator import AggregateResult, LeadAggregator
from harness.phase.bootstrap import bootstrap_phases, bootstrap_and_register
from harness.phase.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitBreakerState,
)
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchProtocol,
    ParallelDispatchResult,
)
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import LoopConfig, Phase, Step
from harness.phase.orchestrator import PhaseOrchestrator, PhaseOrchestratorResult
from harness.phase.step_executor import StepExecutor
from harness.phase.pruning import ArtifactSummariser, ContextPruner
from harness.phase.state_manager import PhaseStateManager
from harness.phase.strategy.base import PhaseResult, PhaseStrategy
from harness.phase.strategy.runner import StrategyRunner

__all__ = [
    "AggregateResult",
    "ArtifactSummariser",
    "bootstrap_and_register",
    "bootstrap_phases",
    "CircuitBreakerRegistry",
    "CircuitBreakerState",
    "ContextPruner",
    "DispatchResult",
    "LeadAggregator",
    "LoopConfig",
    "ParallelDispatchProtocol",
    "ParallelDispatchResult",
    "Phase",
    "PhaseOrchestrator",
    "PhaseOrchestratorResult",
    "PhaseResult",
    "PhaseStateManager",
    "PhaseStrategy",
    "Step",
    "StepDispatcher",
    "StepExecutor",
    "StepResult",
    "StrategyRunner",
]
