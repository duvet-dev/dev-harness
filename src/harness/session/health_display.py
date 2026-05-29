"""HealthDisplay — format health check results for user display — V7 §5.13.

Takes a HealthReport from EngagementHealthCheck and produces
human-readable output suitable for terminal or log display.

Format:
- Global pass/fail header
- Per-check results with severity indicators
- Action items for warnings

Usage::

    display = HealthDisplay()
    output = display.format(report)
    print(output)
"""

from __future__ import annotations

from typing import Any


class HealthDisplay:
    """Formats HealthReport data into human-readable output.

    Produces a structured display with:
    - Overall pass/fail banner
    - Severity-coloured checks (pass, warning, error)
    - Human-readable descriptions
    - Action items for each warning
    """

    # Severity style indicators
    _SEVERITY_ICONS: dict[str, str] = {
        "pass": "✓",
        "fail": "✗",
        "warn": "!",
        "info": "i",
    }

    _SEVERITY_LABELS: dict[str, str] = {
        "pass": "PASS",
        "fail": "FAIL",
        "warn": "WARN",
        "info": "INFO",
    }

    def format(
        self,
        report: Any,
    ) -> str:
        """Format a HealthReport into a human-readable string.

        Args:
            report: A HealthReport object (from
                harness.engagement.health). Must have attributes:
                - all_ok (bool)
                - warnings (list of objects with type, message)
                - slug (str)
                - engagement (optional, any state info)

        Returns:
            A formatted multi-line string ready for display.
        """
        lines: list[str] = []

        # ── Header ──────────────────────────────────────────────────
        slug = self._get_attr(report, "slug", "unknown")
        all_ok = self._get_attr(report, "all_ok", True)
        warnings = self._get_attr(report, "warnings", [])

        lines.append(f"Health Report — {slug}")
        lines.append("─" * 50)

        if all_ok:
            lines.append(f"  {self._SEVERITY_ICONS['pass']} All checks passed")
        else:
            lines.append(f"  {self._SEVERITY_ICONS['fail']} {len(warnings)} warning(s) found")

        lines.append("")

        # ── Engagement summary ───────────────────────────────────────
        engagement = self._get_attr(report, "engagement", None)
        if engagement:
            status = self._get_attr(engagement, "status", "unknown")
            current_phase = self._get_attr(engagement, "current_phase", None)
            last_active = self._get_attr(engagement, "last_active", None)

            lines.append("  Engagement:")
            lines.append(f"    Status:       {status}")
            if current_phase:
                lines.append(f"    Phase:        {current_phase}")
            if last_active:
                lines.append(f"    Last active:  {last_active}")
            lines.append("")

        # ── Warnings table ───────────────────────────────────────────
        if warnings:
            lines.append("  Checks:")
            for i, w in enumerate(warnings, 1):
                w_type = self._get_attr(w, "type", "unknown")
                w_msg = self._get_attr(w, "message", "No details")

                severity = self._classify_severity(w_type)
                icon = self._SEVERITY_ICONS.get(severity, "?")
                label = self._SEVERITY_LABELS.get(severity, "UNKNOWN")

                lines.append(f"    {i}. [{label}] {w_type}")
                lines.append(f"       {w_msg}")
                lines.append(f"       Action: {self._action_item(w_type, w_msg)}")
            lines.append("")

        # ── Footer ───────────────────────────────────────────────────
        lines.append("─" * 50)
        lines.append(
            "Run /status to recheck or /abort to stop the engagement."
        )

        return "\n".join(lines)

    def _classify_severity(
        self,
        warning_type: str,
    ) -> str:
        """Classify a warning type into a severity level.

        Args:
            warning_type: The machine-readable warning type.

        Returns:
            Severity string: "pass", "fail", "warn", or "info".
        """
        severe_types = {
            "corrupt_state", "engagement_not_found", "load_error",
            "slug_mismatch", "branch_missing",
        }
        warn_types = {
            "branch_mismatch", "dirty_repo", "stale_engagement",
        }
        info_types = {
            "no_git_repo",
        }

        if warning_type in severe_types:
            return "fail"
        if warning_type in warn_types:
            return "warn"
        if warning_type in info_types:
            return "info"
        return "warn"

    def _action_item(
        self,
        warning_type: str,
        message: str,
    ) -> str:
        """Generate a human-readable action item for a warning.

        Args:
            warning_type: The machine-readable warning type.
            message: The original warning message.

        Returns:
            Actionable advice string.
        """
        actions: dict[str, str] = {
            "branch_mismatch": "Switch to the correct git branch or "
                "update the engagement's target_branch.",
            "dirty_repo": "Commit or stash uncommitted changes "
                "before continuing.",
            "branch_missing": "Create the target branch, or update "
                "the engagement's target_branch to an existing branch.",
            "corrupt_state": "Engagement state is corrupted. Check "
                "the engagement JSON file for errors or recreate "
                "the engagement.",
            "engagement_not_found": "The engagement may have been "
                "deleted or never created. Verify the slug.",
            "load_error": "Check the engagement file format and "
                "ensure all required fields are present.",
            "slug_mismatch": "The engagement file's slug doesn't "
                "match the requested slug. Check for file naming "
                "errors.",
            "stale_engagement": "The engagement has been inactive "
                "for over 24 hours. Consider pausing or aborting it.",
            "no_git_repo": "Not a git repository. Health checks for "
                "branch alignment and dirty state are unavailable.",
        }
        return actions.get(warning_type, f"Investigate: {message}")

    @staticmethod
    def _get_attr(obj: Any, attr: str, default: Any = "") -> Any:
        """Get an attribute from an object or dict safely."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)
