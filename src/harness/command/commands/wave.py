"""Typed commands for wave operations.

Covers: run_wave.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class RunWaveCommand(TypedCommand):
    """Run a wave through the implement-test-verify cycle."""

    slug: str
    wave_id: str = ""
    no_test: bool = False
    backend: str | None = None


__all__ = [
    "RunWaveCommand",
]
