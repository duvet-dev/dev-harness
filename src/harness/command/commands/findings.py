"""Typed commands for Findings Registry operations.

Covers: list_findings, show_finding, update_finding_status,
       confirm_signoff, sync_findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class FindingsListCommand(TypedCommand):
    """List findings from the registry."""

    slug: str
    status: str = ""
    severity: str = ""
    source: str = ""


@dataclass(frozen=True)
class FindingsShowCommand(TypedCommand):
    """Show a single finding."""

    slug: str
    finding_id: str


@dataclass(frozen=True)
class FindingsUpdateStatusCommand(TypedCommand):
    """Update the status of a finding."""

    slug: str
    finding_id: str
    new_status: str


@dataclass(frozen=True)
class FindingsConfirmSignoffCommand(TypedCommand):
    """Confirm human sign-off for a resolved/pending finding."""

    slug: str
    finding_id: str


@dataclass(frozen=True)
class FindingsSyncCommand(TypedCommand):
    """Sync analysis results into the Findings Registry."""

    slug: str
    deep: bool = False
    assess: bool = False


__all__ = [
    "FindingsListCommand",
    "FindingsShowCommand",
    "FindingsUpdateStatusCommand",
    "FindingsConfirmSignoffCommand",
    "FindingsSyncCommand",
]
