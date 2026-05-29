"""Phase orchestration package.

Core recursive step model, phase definitions, state management,
step dispatch, parallel dispatch, and lead aggregation.
"""

from __future__ import annotations

from harness.phase.aggregator import AggregateResult, LeadAggregator
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchProtocol,
    ParallelDispatchResult,
)
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import LoopConfig, Phase, Step
from harness.phase.state_manager import PhaseStateManager

__all__ = [
    "AggregateResult",
    "DispatchResult",
    "LeadAggregator",
    "LoopConfig",
    "ParallelDispatchProtocol",
    "ParallelDispatchResult",
    "Phase",
    "PhaseStateManager",
    "Step",
    "StepDispatcher",
    "StepResult",
]
