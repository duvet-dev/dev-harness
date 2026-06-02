"""Typed results for wave operations.

Covers: create_wave, execute_step, run_wave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class CreateWaveResult(TypedResult):
    """Result of creating a wave."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    wave_title: str = ""
    wave_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class ExecuteStepResult(TypedResult):
    """Result of executing a step."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    step: Any = ""
    error: str = ""


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
    "CreateWaveResult",
    "ExecuteStepResult",
    "RunWaveResult",
]
