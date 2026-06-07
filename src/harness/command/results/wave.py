"""Typed results for wave operations.

Covers: run_wave.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.command.types import TypedResult


@dataclass(frozen=True)
class RunWaveResult(TypedResult):
    """Result of running a wave."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    wave_id: str = ""
    iteration_count: int = 0
    error: str = ""


__all__ = [
    "RunWaveResult",
]
