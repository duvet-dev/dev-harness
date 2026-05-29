"""Per-wave code and test cycle orchestration.

The ``WaveCycleResult`` dataclass is still re-exported for callers that
process results from the (deprecated) wave-cycle runner.

The old ``WaveCycleRunner`` and ``WaveCycleConfig`` classes are deprecated
(Wave 4, R33). Use ``LoopRunner`` in ``harness.loop.runner`` instead.
"""

from .wave_cycle import (
    WaveCycleResult,
)

__all__ = [
    "WaveCycleResult",
]
