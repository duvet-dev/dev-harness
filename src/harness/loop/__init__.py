"""LoopRunner package — recursive loop step execution (V7 §5.2, R33).

Provides LoopRunner for executing LoopConfig steps with iteration
tracking, re-entry semantics, convergence-aware iteration with 5
strategies (gate_judgment, all_gates, test_suite, stable,
external_approval), and failure handling via the circuit breaker
escalation chain.

The ``LoopRunner`` class lives in :mod:`harness.loop.engine` (moved
from ``runner.py`` which was deleted).

Usage::

    runner = LoopRunner(step_executor=..., state_manager=...)
    result = await runner.run(loop_config, context)
    if result.success:
        print(f"Completed {result.iteration_count} iterations")
"""

from __future__ import annotations

from harness.loop.convergence import (
    AllGatesStrategy,
    ConvergenceStrategy,
    ExternalApprovalStrategy,
    GateJudgmentStrategy,
    StableStrategy,
    STRATEGY_ALIASES,
    STRATEGY_REGISTRY,
    TestSuiteStrategy,
    resolve_strategy,
    resolve_strategy_name,
)
from harness.loop.model import LoopState
from harness.loop.engine import (
    ConvergenceCheckFn,
    LoopRunner,
    LoopRunnerResult,
)

__all__ = [
    # Runner
    "LoopRunner",
    "LoopRunnerResult",
    "LoopState",
    "ConvergenceCheckFn",
    # Convergence strategies
    "ConvergenceStrategy",
    "GateJudgmentStrategy",
    "AllGatesStrategy",
    "TestSuiteStrategy",
    "StableStrategy",
    "ExternalApprovalStrategy",
    "STRATEGY_REGISTRY",
    "STRATEGY_ALIASES",
    "resolve_strategy",
    "resolve_strategy_name",
]
