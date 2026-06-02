"""Harness health and configuration validation — public API wrapper.

All logic lives in the domain, infrastructure, and application layers.
This module provides backward-compatible imports for the CLI and shell.
"""

from __future__ import annotations

from pathlib import Path

from harness.domain.health import HealthCheck, HealthReport
from harness.application.services.health_service import HealthService
from harness.infrastructure.git.git_health_service import GitHealthChecker
from harness.infrastructure.config.validator import ConfigValidator
from harness.infrastructure.engagement.engagement_health_service import (
    EngagementHealthChecker,
)


def _build_service(root: Path) -> HealthService:
    """Build a fully-wired HealthService for the given project root."""
    from harness.scm.git import GitRepo
    from harness.domain.engagement.lifecycle import read_active_engagement
    from harness.state.freshness import load_freshness, save_freshness, FreshnessRecord
    from harness.plan.plan_manager import PlanManager
    import yaml
    import os

    _git = GitRepo(root)

    class _FreshnessStore:
        def load(self, r: Path):
            return load_freshness(r)
        def save(self, rec, r: Path):
            return save_freshness(rec, r)

    _git_checker = GitHealthChecker(_git, read_active_engagement, _FreshnessStore())

    class _YamlReader:
        def read(self, p: Path):
            with open(p) as f:
                return yaml.safe_load(f)

    class _EnvProvider:
        def get(self, name: str):
            return os.environ.get(name)

    _config_validator = ConfigValidator(_YamlReader(), _EnvProvider())

    _engagement_checker = EngagementHealthChecker(
        read_active_engagement,
        _YamlReader(),
        lambda r, s: PlanManager(r, s),
        lambda r: GitRepo(r),
        load_freshness,
    )

    return HealthService(_git_checker, _config_validator, _engagement_checker)


def run_health_checks(root: Path) -> HealthReport:
    """Run all health checks and return a report.

    Args:
        root: Project root directory.

    Returns:
        Aggregated ``HealthReport`` with all check results.

    Delegates to ``HealthService.run_all_checks``.
    """
    return _build_service(root).run_all_checks(root)


def format_health_report(report: HealthReport, verbose: bool = False) -> str:
    """Format a health report for terminal output.

    Args:
        report: The ``HealthReport`` to format.
        verbose: If True, include INFO-level checks.

    Returns:
        Formatted string ready for ``click.echo()``.

    Delegates to ``HealthService.format_report``.
    """
    return HealthService(None, None, None).format_report(report, verbose=verbose)


def run_fixes(root: Path) -> list[str]:
    """Run all auto-fixes on engagement metadata and state.

    Args:
        root: Project root directory.

    Returns:
        List of human-readable fix messages.

    Delegates to ``HealthService.run_fixes``.
    """
    return _build_service(root).run_fixes(root)


def fix_engagement(root: Path, slug: str) -> list[str]:
    """Fix engagement metadata and state for a specific engagement.

    Args:
        root: Project root directory.
        slug: Engagement slug to fix.

    Returns:
        List of human-readable fix messages.

    Delegates to ``HealthService.fix_engagement``.
    """
    from harness.scm.git import GitRepo
    from harness.plan.plan_manager import PlanManager
    import yaml

    class _YamlReader:
        def read(self, p: Path):
            with open(p) as f:
                return yaml.safe_load(f)

    _engagement_checker = EngagementHealthChecker(
        lambda _: {"slug": slug},
        _YamlReader(),
        lambda r, s: PlanManager(r, s),
        lambda r: GitRepo(r),
        lambda _: None,
    )
    return _engagement_checker.fix_engagement(root, slug)


__all__ = [
    "HealthCheck",
    "HealthReport",
    "run_health_checks",
    "format_health_report",
    "run_fixes",
    "fix_engagement",
]
