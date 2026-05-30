"""Typed results for batch and lower priority wave operations.

Covers: create_waves_from_assessment, create_wave_from_finding,
list_waves, wave_status, generate_docs, annotate_changelog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class CreateWavesFromAssessmentResult(TypedResult):
    """Result of creating waves from assessment."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    created: int = 0
    matched: int = 0
    slug: str = ""
    error: str = ""


@dataclass(frozen=True)
class CreateWaveFromFindingResult(TypedResult):
    """Result of creating a wave from a finding."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    wave_id: str = ""
    finding_id: str = ""
    title: str = ""
    severity: str = ""
    category: str = ""
    skipped: bool = False
    error: str = ""


@dataclass(frozen=True)
class ListWavesResult(TypedResult):
    """Result of listing waves."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    waves: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class WaveStatusResult(TypedResult):
    """Result of wave status query."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    summary: str = ""
    error: str = ""


@dataclass(frozen=True)
class GenerateDocsResult(TypedResult):
    """Result of generating documentation."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    generated: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class AnnotateChangelogResult(TypedResult):
    """Result of annotating changelog."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    path: str = ""
    error: str = ""


__all__ = [
    "CreateWavesFromAssessmentResult",
    "CreateWaveFromFindingResult",
    "ListWavesResult",
    "WaveStatusResult",
    "GenerateDocsResult",
    "AnnotateChangelogResult",
]
