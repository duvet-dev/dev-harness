"""Shared types for analysis results.

Defines the Finding and ScanResult dataclasses used across all
analysis modules (fast scan, deep analysis, observer mode).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_SEVERITIES = ("info", "warning", "error")
VALID_CATEGORIES = (
    "structure",
    "coverage",
    "dead_code",
    "arch_conformance",
    "convention",
    "dependency",
    "duplication",
    # Analysis agent categories
    "architecture",
    "code_quality",
    "naming",
    "complexity",
    "error_handling",
    "redundancy",
    "project_profile",
    "purpose",
    "test_quality",
    "test_isolation",
    "dependency_analysis",
    "build_system",
    "project_type",
)


@dataclass
class Finding:
    """A single observation from analysis."""

    severity: str = "info"
    """One of: info, warning, error."""

    category: str = "structure"
    """Analysis category this finding belongs to."""

    message: str = ""
    """Human-readable description of the finding."""

    file: str = ""
    """File path this finding relates to (relative)."""

    line: int | None = None
    """Line number within the file."""

    details: dict[str, Any] | None = None
    """Optional structured data about the finding."""

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(VALID_SEVERITIES)}"
            )
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. "
                f"Must be one of: {', '.join(VALID_CATEGORIES)}"
            )


@dataclass
class ScanResult:
    """Result of an analysis scan."""

    scan_name: str = ""
    """Name identifying what was scanned (e.g. 'fast-scan', 'deep-analysis')."""

    findings: list[Finding] = field(default_factory=list)
    """All findings discovered during the scan."""

    metrics: dict[str, Any] = field(default_factory=dict)
    """Numerical metrics: file_count, total_lines, coverage_pct, etc."""

    summary: str = ""
    """Human-readable one-line summary of findings."""

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")

    def merge(self, other: ScanResult) -> ScanResult:
        """Combine two scan results."""
        self.findings.extend(other.findings)
        self.metrics.update(other.metrics)
        return self
