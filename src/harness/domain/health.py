"""Domain model for health check system.

Pure dataclasses — no I/O, no infrastructure imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from harness.domain.enums import HealthSeverity


_CHECK_DESCRIPTIONS: dict[str, str] = {
    "harness-dir": "``.harness/`` directory exists with required structure",
    "providers-yaml": "``providers.yaml`` is valid YAML and has at least one provider",
    "api-keys": "All ``${VAR}`` references in providers.yaml resolve to environment variables",
    "engagement-fresh": "Active engagement state is not stale",
    "branch-match": "Current git branch matches engagement's stored branch",
    "git-clean": "Git working tree has no uncommitted changes",
    "plan-consistency": "``plan.yaml`` is consistent with engagement state",
    "agent-roles": "All agent roles referenced in team/phase configs exist in agent registry",
    "manifest-link": "Assessment manifest files referenced by engagement exist",
    "python-version": "Python version meets minimum requirements",
}


Status = Literal["pass", "warn", "fail"]


def _result(
    name: str,
    status: Status,
    message: str,
    severity: HealthSeverity = HealthSeverity.WARN,
    fix: str | None = None,
) -> HealthCheck:
    """Create a HealthCheck with its description populated from the check name."""
    return HealthCheck(
        name=name,
        description=_CHECK_DESCRIPTIONS.get(name, name),
        status=status,
        message=message,
        severity=severity,
        fix=fix,
    )


@dataclass
class HealthCheck:
    """Single validation check result.

    Attributes:
        name: Machine-readable check name (e.g. ``"harness-dir"``).
        description: Human-readable description of what was checked.
        status: ``"pass"``, ``"warn"``, or ``"fail"``.
        message: Human-readable result message.
        severity: ``"CRITICAL"``, ``"BRANCH"``, ``"WARN"``, or ``"INFO"``.
        fix: Optional suggested fix command or action.
    """

    name: str
    description: str
    status: Status
    message: str
    severity: HealthSeverity = HealthSeverity.WARN
    fix: str | None = None


@dataclass
class HealthReport:
    """Aggregated health check results.

    Attributes:
        checks: All individual check results.
        summary: Short human-readable summary.
    """

    checks: list[HealthCheck] = field(default_factory=list)
    summary: str = ""

    @property
    def status(self) -> str:
        failures = any(c.status == "fail" for c in self.checks)
        warnings = any(c.status == "warn" for c in self.checks)
        if failures:
            return "fail"
        if warnings:
            return "warn"
        return "pass"

    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")


__all__ = [
    "HealthCheck",
    "HealthReport",
    "Status",
    "_CHECK_DESCRIPTIONS",
    "_result",
]
