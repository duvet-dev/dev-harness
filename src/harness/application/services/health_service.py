"""Health check orchestration service.

Provides ``HealthService`` which coordinates all health checkers
and provides the public API for running checks, fixes, and formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from harness.domain.health import (
    _CHECK_DESCRIPTIONS,
    _result,
    HealthCheck,
    HealthReport,
)
from harness.paths import (
    get_fleets_path,
    get_harness_dir,
)


class HealthService:
    """Orchestrates health checks from multiple checkers.

    Args:
        git_checker: A ``GitHealthChecker`` instance.
        config_validator: A ``ConfigValidator`` instance.
        engagement_checker: An ``EngagementHealthChecker`` instance.
    """

    def __init__(
        self,
        git_checker: Any,
        config_validator: Any,
        engagement_checker: Any,
    ) -> None:
        self._git = git_checker
        self._config = config_validator
        self._eng = engagement_checker

    # ── Check: .harness/ directory ────────────────────────────────────────

    def check_harness_dir(self, root: Path) -> HealthCheck:
        """Verify the ``.harness/`` directory exists with core structure."""
        harness_dir = get_harness_dir(root)
        if not harness_dir.is_dir():
            return _result(
                "harness-dir", "fail",
                "``.harness/`` directory not found. Run ``harness init`` to set up the project.",
                severity="CRITICAL",
                fix="harness init",
            )

        required = [
            "config.yaml",
            "active-engagements.yaml",
            "engagements",
        ]
        missing = [r for r in required if not (harness_dir / r).exists()]
        if missing:
            return _result(
                "harness-dir", "fail",
                f"Missing required files/dirs in .harness/: {', '.join(missing)}",
                severity="CRITICAL",
                fix="harness init --force",
            )

        return _result("harness-dir", "pass", ".harness/ directory structure is intact")

    def check_agent_roles(self, root: Path) -> HealthCheck:
        """Verify all agent roles referenced in fleet/phase configs exist."""
        try:
            from harness.agents.agent_registry import AGENTS

            fleet_path = get_fleets_path(root)
            referenced_roles: set[str] = set()

            if fleet_path.is_file():
                import yaml
                with open(fleet_path) as f:
                    fleet_data = yaml.safe_load(f) or {}
                for fleet_name, fleet_def in fleet_data.items():
                    if isinstance(fleet_def, dict):
                        for agent in fleet_def.get("agents", []):
                            if isinstance(agent, dict):
                                referenced_roles.add(agent.get("name", ""))
                            elif isinstance(agent, str):
                                referenced_roles.add(agent)

            valid_values = set(spec.role for spec in AGENTS)
            missing = [r for r in referenced_roles if r and r not in valid_values]

            if missing:
                return _result(
                    "agent-roles", "warn",
                    f"Referenced agent roles not in agent registry: {', '.join(missing)}. "
                    f"These agents may operate without tool access.",
                    fix=f"Add to agent registry: {', '.join(missing)}",
                )

            return _result(
                "agent-roles", "pass",
                f"All {len(referenced_roles)} referenced agent roles exist in agent registry.",
            )
        except Exception as exc:
            return _result("agent-roles", "warn", f"Cannot check agent roles: {exc}")

    def check_python_version(self, root: Path) -> HealthCheck:
        """Verify Python version meets minimum requirements."""
        _ = root
        major, minor = sys.version_info[:2]
        if major < 3 or (major == 3 and minor < 9):
            return _result(
                "python-version", "warn",
                f"Python {major}.{minor} is below minimum 3.9. Some features may not work.",
            )
        return _result(
            "python-version", "pass",
            f"Python {major}.{minor}.{sys.version_info[2]} — meets minimum 3.9+ requirement.",
        )

    # ── Orchestration ────────────────────────────────────────────────────

    def run_all_checks(self, root: Path) -> HealthReport:
        """Run all health checks and return a report.

        Args:
            root: Project root directory.

        Returns:
            Aggregated ``HealthReport`` with all check results.
        """
        report = HealthReport()

        # Critical checks
        report.checks.append(self.check_harness_dir(root))
        report.checks.append(self._config.check_providers_yaml(root))
        report.checks.append(self._config.check_api_keys(root))
        report.checks.append(self._eng.check_engagement_fresh(root))

        # Branch check (separate category)
        report.checks.append(self._git.check_branch_match(root))

        # Warning checks
        report.checks.append(self._git.check_git_clean(root))
        report.checks.append(self.check_agent_roles(root))
        report.checks.append(self._eng.check_plan_consistency(root))
        report.checks.append(self._eng.check_manifest_link(root))

        # Info checks
        report.checks.append(self.check_python_version(root))

        # Build summary
        passed = report.pass_count()
        warned = report.warn_count()
        failed = report.fail_count()
        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if warned:
            parts.append(f"{warned} warnings")
        if failed:
            parts.append(f"{failed} failures")
        report.summary = f"{', '.join(parts)}" if parts else "All checks passed"

        return report

    def run_fixes(self, root: Path) -> list[str]:
        """Run all auto-fixes on engagement metadata and state.

        Args:
            root: Project root directory.

        Returns:
            List of human-readable fix messages.
        """
        messages: list[str] = []
        messages.append("Attempting auto-fixes...")
        messages.append("")

        messages.extend(self._eng.fix_missing_dir(root))
        messages.append("")

        messages.extend(self._eng.fix_plan_consistency(root))
        messages.append("")

        messages.extend(self._git.fix_branch_match(root))
        messages.append("")

        messages.extend(self._git.fix_git_state(root))
        messages.append("")

        messages.append("Auto-fixes complete. Run 'harness health' to verify.")
        return messages

    def format_report(self, report: HealthReport, verbose: bool = False) -> str:
        """Format a health report for terminal output.

        Args:
            report: The ``HealthReport`` to format.
            verbose: If True, include INFO-level checks.

        Returns:
            Formatted string ready for ``click.echo()``.
        """
        lines: list[str] = []
        lines.append("")
        lines.append("  Harness Health")
        lines.append("  " + "─" * 45)

        severity_order = ["CRITICAL", "BRANCH", "WARN", "INFO"]
        for sev in severity_order:
            checks = [c for c in report.checks if c.severity == sev]
            if not checks:
                continue
            if sev == "INFO" and not verbose:
                continue

            lines.append("")
            lines.append(f"  {sev}")
            for c in checks:
                icon = "✓" if c.status == "pass" else ("⚠" if c.status == "warn" else "✗")
                lines.append(f"    {icon} {c.message}")
                if c.fix and c.status != "pass":
                    lines.append(f"       → Fix: {c.fix}")

        lines.append("")
        lines.append(f"  {'─' * 45}")
        lines.append(f"  Status: {report.status.upper()} — {report.summary}")
        lines.append("")

        return "\n".join(lines)

    def fix_engagement(self, root: Path, slug: str) -> list[str]:
        """Fix engagement metadata and state for a specific engagement.

        Args:
            root: Project root directory.
            slug: Engagement slug to fix.

        Returns:
            List of human-readable fix messages.
        """
        return self._eng.fix_engagement(root, slug)


__all__ = [
    "HealthService",
]
