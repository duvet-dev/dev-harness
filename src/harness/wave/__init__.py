"""Per-wave code and test cycle orchestration.

Each wave in a development plan represents a self-contained unit of work.
The ``WaveCycleRunner`` walks a single wave through:

1. Implementation (coder agent writes code + tests)
2. Test analysis (tester agent validates and supplements tests)
3. Test suite execution (actual ``pytest`` run)
4. Fix loop (if tests fail, coder revises with test output)
5. Commit (wave marked complete in plan)

This ensures every wave can be raised as a PR with full confidence.
"""

from .wave_cycle import (
    WaveCycleConfig,
    WaveCycleResult,
    WaveCycleRunner,
)

__all__ = [
    "WaveCycleConfig",
    "WaveCycleResult",
    "WaveCycleRunner",
]
