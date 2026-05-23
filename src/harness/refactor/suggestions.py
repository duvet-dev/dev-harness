"""Debt-triggered refactoring suggestions.

Generates actionable refactoring suggestions from a ``DebtReport``,
gated by the ``allow_refactoring_suggestions`` configuration setting.

Each violation type maps to a specific refactoring pattern with
estimated effort and priority.

Usage::

    engine = DebtSuggestionEngine()
    suggestions = engine.generate(report)
    for s in suggestions:
        print(f"{s.priority}: {s.title}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from harness.config.manager import allow_refactoring_suggestions
from harness.refactor.debt import DebtDetector, DebtReport, DebtViolation

# ── Suggestion model ───────────────────────────────────────────────────────


@dataclass
class RefactoringSuggestion:
    """A single actionable refactoring suggestion.

    Attributes:
        title: Short description of the recommended change.
        description: Detailed explanation of what to do and why.
        affected_files: List of file paths involved.
        effort_hours: Estimated effort in hours.
        priority: ``high``, ``medium``, or ``low``.
        rule_name: The detection rule that triggered this suggestion.
        pattern: The refactoring pattern to apply (e.g. ``extract-adapter``,
            ``move-to-layer``, ``wrap-dependency``).
    """

    title: str = ""
    description: str = ""
    affected_files: list[str] = field(default_factory=list)
    effort_hours: float = 1.0
    priority: str = "medium"
    rule_name: str = ""
    pattern: str = ""


# ── Refactoring pattern templates ─────────────────────────────────────────


_REFACTORING_PATTERNS: dict[str, dict] = {
    "domain_infrastructure_leak": {
        "title": "Extract infrastructure dependency from domain layer",
        "description": (
            "The domain layer should not import infrastructure packages. "
            "Extract the infrastructure dependency behind an adapter interface "
            "in the adapters layer, then inject it into domain code via the "
            "application layer."
        ),
        "pattern": "extract-adapter",
        "effort_hours": 4.0,
        "priority": "high",
    },
    "direct_db_access": {
        "title": "Wrap direct database access behind a repository",
        "description": (
            "Direct database API calls (execute, query, commit) should be "
            "wrapped behind a repository or data access layer in the "
            "infrastructure/adapters package. Business logic should only "
            "talk to repository interfaces."
        ),
        "pattern": "introduce-repository",
        "effort_hours": 4.0,
        "priority": "high",
    },
    "missing_adapter": {
        "title": "Wrap external dependency behind an adapter",
        "description": (
            "External libraries should not be imported directly in "
            "application or domain code. Create an adapter interface in "
            "the adapters layer, implement it with the external library, "
            "and inject the interface where needed."
        ),
        "pattern": "wrap-dependency",
        "effort_hours": 2.0,
        "priority": "medium",
    },
    "framework_coupling_in_domain": {
        "title": "Remove framework coupling from domain layer",
        "description": (
            "Domain logic should be framework-free. Extract framework-"
            "dependent code into the application or adapters layer, "
            "keeping domain classes as pure business objects."
        ),
        "pattern": "move-to-layer",
        "effort_hours": 2.0,
        "priority": "medium",
    },
    "circular_dependency": {
        "title": "Resolve circular dependency between modules",
        "description": (
            "Circular dependencies violate layering and make code brittle. "
            "Introduce an interface or event-driven mediation to break "
            "the cycle."
        ),
        "pattern": "introduce-interface",
        "effort_hours": 3.0,
        "priority": "high",
    },
    "layer_violation": {
        "title": "Move code to correct architecture layer",
        "description": (
            "This file violates the declared layer boundaries. Move it "
            "to the appropriate layer or restructure the dependency flow "
            "to point inward."
        ),
        "pattern": "move-to-layer",
        "effort_hours": 3.0,
        "priority": "medium",
    },
}


# ── Suggestion engine ──────────────────────────────────────────────────────


class DebtSuggestionEngine:
    """Generates refactoring suggestions from a DebtReport.

    Gated by the ``allow_refactoring_suggestions`` configuration —
    callers should check the config before generating suggestions.
    """

    def generate(
        self,
        report: DebtReport,
    ) -> list[RefactoringSuggestion]:
        """Generate refactoring suggestions from a debt report.

        Each unique rule name in the report generates one consolidated
        suggestion (grouping all files affected by that rule).

        Args:
            report: A ``DebtReport`` from ``DebtDetector.scan()``.

        Returns:
            A list of ``RefactoringSuggestion`` instances.
        """
        if not report.violations:
            return []

        # Group violations by rule_name
        by_rule: dict[str, list[DebtViolation]] = {}
        for v in report.violations:
            by_rule.setdefault(v.rule_name, []).append(v)

        suggestions: list[RefactoringSuggestion] = []
        for rule_name, violations in by_rule.items():
            suggestion = self._suggestion_for_rule(rule_name, violations)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by priority (high first, then medium, then low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(
            key=lambda s: priority_order.get(s.priority, 99)
        )

        return suggestions

    def _suggestion_for_rule(
        self,
        rule_name: str,
        violations: list[DebtViolation],
    ) -> Optional[RefactoringSuggestion]:
        """Build a suggestion for a single rule, or ``None`` if unknown."""
        pattern = _REFACTORING_PATTERNS.get(rule_name)
        if pattern is None:
            # Unknown rule — generate a generic suggestion
            affected = [
                f"{v.file or '(unknown)'}:{v.line}" if v.line
                else v.file or "(unknown)"
                for v in violations
            ]
            return RefactoringSuggestion(
                title=f"Address {len(violations)} architecture issue(s) "
                      f"({rule_name})",
                description=(
                    f"{len(violations)} violation(s) found for rule "
                    f"'{rule_name}'. Review and apply appropriate fixes."
                ),
                affected_files=list(set(
                    v.file for v in violations if v.file
                )),
                effort_hours=len(violations) * 0.5,  # fallback per-violation estimate
                priority="medium",
                rule_name=rule_name,
                pattern="manual-review",
            )

        affected = list(set(
            f"{v.file or '(unknown)'}:{v.line}" if v.line
            else v.file or "(unknown)"
            for v in violations
        ))

        # Estimate total effort based on number of occurrences
        total_effort = pattern["effort_hours"] * len(violations)

        return RefactoringSuggestion(
            title=pattern["title"],
            description=(
                f"{pattern['description']}\n\n"
                f"Affects {len(violations)} location(s) across "
                f"{len(set(v.file for v in violations if v.file))} file(s)."
            ),
            affected_files=affected,
            effort_hours=total_effort,
            priority=pattern["priority"],
            rule_name=rule_name,
            pattern=pattern["pattern"],
        )

    def to_markdown(
        self,
        suggestions: list[RefactoringSuggestion],
    ) -> str:
        """Format suggestions as a markdown section."""
        lines: list[str] = [
            "## Refactoring Suggestions",
            "",
        ]

        if not suggestions:
            lines.append("✅ No refactoring suggested.")
            lines.append("")
            return "\n".join(lines)

        for s in suggestions:
            priority_icon = {
                "high": "🔴", "medium": "🟡", "low": "🟢",
            }.get(s.priority, "⚪")
            lines.append(
                f"### {priority_icon} [{s.priority.upper()}] {s.title}"
            )
            lines.append("")
            lines.append(s.description)
            lines.append("")
            if s.affected_files:
                lines.append("**Affected files:**")
                for f in s.affected_files[:10]:  # Show top 10
                    lines.append(f"- `{f}`")
                if len(s.affected_files) > 10:
                    lines.append(
                        f"- *...and {len(s.affected_files) - 10} more*"
                    )
            lines.append("")
            if s.effort_hours < 1.0:
                est = f"~{int(s.effort_hours * 60)} min"
            else:
                est = f"~{s.effort_hours:.0f}h"
            lines.append(f"**Estimated effort:** {est}")
            lines.append(f"**Pattern:** `{s.pattern}`")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


# ── Convenience: full pipeline ─────────────────────────────────────────────


def generate_suggestions(
    root: Path,
    slug: Optional[str] = None,
    debt_report: Optional[DebtReport] = None,
    skip_config_check: bool = False,
) -> list[RefactoringSuggestion]:
    """Convenience: generate refactoring suggestions for a project.

    Checks the ``allow_refactoring_suggestions`` config gate first,
    then runs the DebtDetector if no report is provided, and generates
    suggestions.

    Args:
        root: Project root directory.
        slug: Optional engagement slug for config resolution.
        debt_report: Optional pre-scanned debt report. If not provided,
            one will be generated.
        skip_config_check: If True, skip the config gate check.

    Returns:
        A list of ``RefactoringSuggestion`` instances. Empty if the
        config gate is closed.
    """
    if not skip_config_check:
        if not allow_refactoring_suggestions(root, slug):
            return []

    # Scan for debt if not provided
    if debt_report is None:
        detector = DebtDetector()
        debt_report = detector.scan(root)

    engine = DebtSuggestionEngine()
    return engine.generate(debt_report)
