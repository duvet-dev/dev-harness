"""Typed results for Findings Registry operations.

Covers: list_findings, show_finding, update_finding_status,
       confirm_signoff, sync_findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class FindingsListResult(TypedResult):
    """Result of listing findings."""

    success: bool = True
    message: str = ""
    error: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    delta_summary: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FindingsShowResult(TypedResult):
    """Result of showing a single finding."""

    success: bool = True
    message: str = ""
    error: str = ""
    finding: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FindingsUpdateStatusResult(TypedResult):
    """Result of updating finding status."""

    success: bool = True
    message: str = ""
    error: str = ""
    finding_id: str = ""
    old_status: str = ""
    new_status: str = ""


@dataclass(frozen=True)
class FindingsConfirmSignoffResult(TypedResult):
    """Result of confirming human sign-off."""

    success: bool = True
    message: str = ""
    error: str = ""
    finding_id: str = ""
    confirmed: bool = False


@dataclass(frozen=True)
class FindingsSyncResult(TypedResult):
    """Result of syncing analysis findings."""

    success: bool = True
    message: str = ""
    error: str = ""
    new_count: int = 0
    resolved_count: int = 0
    regression_count: int = 0
    wont_fix_regression_count: int = 0
    delta_summary: list[str] = field(default_factory=list)


__all__ = [
    "FindingsListResult",
    "FindingsShowResult",
    "FindingsUpdateStatusResult",
    "FindingsConfirmSignoffResult",
    "FindingsSyncResult",
]
