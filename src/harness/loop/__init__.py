"""LoopRunner package — recursive loop step execution (V7 §5.2, R33).

Provides LoopRunner for executing LoopConfig steps with iteration
tracking, re-entry semantics, and failure handling via the circuit
breaker escalation chain.

Replaces the old WaveCycleRunner (deprecated in Wave 4).

Usage::

    runner = LoopRunner(step_executor=..., state_manager=...)
    result = await runner.run(loop_config, context)
    if result.success:
        print(f"Completed {result.iteration_count} iterations")
"""

from __future__ import annotations

from harness.loop.model import LoopState
from harness.loop.runner import LoopRunner, LoopRunnerResult

__all__ = [
    "LoopRunner",
    "LoopRunnerResult",
    "LoopState",
]
