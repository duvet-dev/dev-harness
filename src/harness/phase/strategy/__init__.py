"""Phase strategy package.

Execution strategies for running phases: sequential (default) and
parallel. StrategyRunner selects and runs the appropriate strategy.
"""

from __future__ import annotations

from harness.phase.strategy.base import PhaseResult, PhaseStrategy, PhaseStrategyError
from harness.phase.strategy.parallel import ParallelPhaseStrategy
from harness.phase.strategy.runner import StrategyRunner
from harness.phase.strategy.sequential import SequentialPhaseStrategy

__all__ = [
    "ParallelPhaseStrategy",
    "PhaseResult",
    "PhaseStrategy",
    "PhaseStrategyError",
    "SequentialPhaseStrategy",
    "StrategyRunner",
]
