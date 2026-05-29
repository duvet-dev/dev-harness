"""Internal data models for the LoopRunner package.

Provides LoopState for per-loop iteration tracking and re-entry
semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoopState:
    """Per-loop state tracking for re-entry semantics (R18).

    Attributes:
        current_iteration: The current iteration number (0 = not started).
        total_iterations: Total iterations configured for this loop.
        iteration_results: Results from completed iterations.
        created_at: Timestamp or iteration count when this state
            was created.
        reentry_resume: If True, counters continue on re-entry
            instead of resetting.
    """

    current_iteration: int = 0
    total_iterations: int = 0
    iteration_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    created_at: int = 0
    reentry_resume: bool = False
