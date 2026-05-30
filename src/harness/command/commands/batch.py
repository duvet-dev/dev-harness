"""Typed commands for batch and lower priority wave operations.

Covers: create_waves_from_assessment, create_wave_from_finding,
list_waves, wave_status, generate_docs, annotate_changelog.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class CreateWavesFromAssessmentCommand(TypedCommand):
    """Create waves from assessment findings."""

    slug: str = ""
    focus: str = "high-risk"
    limit: int = 0
    refactoring: bool = False


@dataclass(frozen=True)
class CreateWaveFromFindingCommand(TypedCommand):
    """Create a wave from an assessment finding."""

    slug: str = ""
    finding_id: str = ""


@dataclass(frozen=True)
class ListWavesCommand(TypedCommand):
    """List waves from the engagement plan."""

    slug: str = ""


@dataclass(frozen=True)
class WaveStatusCommand(TypedCommand):
    """Show detailed wave status."""

    slug: str = ""


@dataclass(frozen=True)
class GenerateDocsCommand(TypedCommand):
    """Generate project documentation."""

    slug: str = ""
    root: str = "."
    overwrite: str = "ask"
    doc_type: str = "full"
    source_tier: int = 3
    output_dir: str = ""


@dataclass(frozen=True)
class AnnotateChangelogCommand(TypedCommand):
    """Append a human annotation to the latest changelog entry."""

    slug: str = ""
    wave: str = ""
    text: str = ""


__all__ = [
    "CreateWavesFromAssessmentCommand",
    "CreateWaveFromFindingCommand",
    "ListWavesCommand",
    "WaveStatusCommand",
    "GenerateDocsCommand",
    "AnnotateChangelogCommand",
]
