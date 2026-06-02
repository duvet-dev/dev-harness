"""Typed commands for wave operations.

Covers: create_wave, execute_step, run_wave.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class CreateWaveCommand(TypedCommand):
    """Create a new wave."""

    slug: str
    title: str = "New Wave"


@dataclass(frozen=True)
class ExecuteStepCommand(TypedCommand):
    """Execute a step."""

    slug: str
    step: Any = ""  # step spec - dict or string


@dataclass(frozen=True)
class RunWaveCommand(TypedCommand):
    """Run a wave through the implement-test-verify cycle."""

    slug: str
    wave_id: str = ""
    no_test: bool = False
    backend: str | None = None


__all__ = [
    "CreateWaveCommand",
    "ExecuteStepCommand",
    "RunWaveCommand",
]
