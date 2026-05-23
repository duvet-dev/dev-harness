"""Report formatter — produces human-readable and structured output.

Converts ScanResult lists into formatted reports suitable for
terminal output or file export.

Also provides ``debt_section()`` for architecture debt reporting
(with estimated effort) in ``harness summary`` output.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from harness.analysis.base import ScanResult
from harness.refactor.debt import DebtReport

# ── Effort estimation heuristics ───────────────────────────────────────────

_DEBT_EFFORT_HOURS: dict[str, float] = {
    "domain_infrastructure_leak": 4.0,
    "direct_db_access": 4.0,
    "missing_adapter": 2.0,
    "framework_coupling_in_domain": 2.0,
    "circular_dependency": 3.0,
    "layer_violation": 3.0,
    "default_error": 4.0,
    "default_warning": 2.0,
    "default_info": 0.5,
}


def _estimate_effort(violations: list) -> tuple[float, str]:
    """Estimate total effort in hours for a list of violations.

    Returns (total_hours, formatted_string).
    """
    total = 0.0
    for v in violations:
        total += _DEBT_EFFORT_HOURS.get(
            v.rule_name,
            _DEBT_EFFORT_HOURS.get(
                f"default_{v.severity}", 1.0
            ),
        )
    if total < 1.0:
        fmt = f"~{int(total * 60)} min"
    elif total < 8.0:
        fmt = f"~{total:.1f} hours"
    else:
        days = total / 8.0
        fmt = f"~{days:.1f} days ({total:.0f} hours)"
    return total, fmt


def debt_section(
    report: DebtReport,
    effort: bool = True,
    max_violations: int = 20,
) -> str:
    """Format a DebtReport as a markdown section for inclusion in a
    harness summary.

    Args:
        report: The architecture debt report from a DebtDetector scan.
        effort: If True, include estimated effort to fix.
        max_violations: Maximum violations to list individually (beyond
            this, show counts only).

    Returns:
        A markdown-formatted debt section.
    """
    lines: list[str] = []

    if not report.violations:
        lines.append("### Architecture Debt")
        lines.append("")
        lines.append("✅ No architecture debt detected. The codebase is "
                      "clean against the architecture goal.")
        lines.append("")
        return "\n".join(lines)

    lines.append("### Architecture Debt")
    lines.append("")
    lines.append(
        f"{len(report.violations)} violation(s) found across "
        f"{len(set(v.file for v in report.violations if v.file))} file(s)."
    )
    lines.append("")

    # Summary table
    lines.append("| Severity | Count | Estimated Effort |")
    lines.append("|----------|-------|-------------------|")

    for severity, label in [
        ("error", "Error"),
        ("warning", "Warning"),
        ("info", "Info"),
    ]:
        group = [v for v in report.violations if v.severity == severity]
        if not group:
            effort_str = "—"
        elif effort:
            _, effort_str = _estimate_effort(group)
        else:
            effort_str = "—"
        lines.append(f"| {label} | {len(group)} | {effort_str} |")

    if effort and report.violations:
        total_hours, total_str = _estimate_effort(report.violations)
        lines.append(f"| **Total** | **{len(report.violations)}** | **{total_str}** |")

    lines.append("")
    lines.append(f"**Files scanned:** {report.scanned_files}")
    lines.append("")

    # Detailed violations (limited)
    violations_to_show = report.violations[:max_violations]
    if violations_to_show:
        lines.append("#### Violation Details")
        lines.append("")
        for v in violations_to_show:
            file_ref = f" `{v.file}`" if v.file else ""
            line_ref = f":{v.line}" if v.line else ""
            icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                v.severity, "⚪"
            )
            lines.append(
                f"- {icon} **[{v.rule_name}]{file_ref}{line_ref}**"
            )
            lines.append(f"  - {v.message}")
            if effort and v.rule_name in _DEBT_EFFORT_HOURS:
                h = _DEBT_EFFORT_HOURS[v.rule_name]
                if h < 1.0:
                    est = f"~{int(h * 60)} min"
                else:
                    est = f"~{h:.0f}h"
                lines.append(f"  - *Effort: {est}*")

    remaining = len(report.violations) - max_violations
    if remaining > 0:
        lines.append("")
        lines.append(
            f"*...and {remaining} more violation(s). "
            f"Run `harness observe` for the full report.*"
        )

    lines.append("")
    return "\n".join(lines)


def format_report(
    results: list[ScanResult],
    include_summary: bool = True,
    format: str = "markdown",
    debt_report: Optional[DebtReport] = None,
) -> str:
    """Format scan results into a human-readable report.

    Args:
        results: List of scan results to format.
        include_summary: If True, prepend a one-line summary.
        format: Output format — 'markdown' or 'json'.
        debt_report: Optional DebtReport to include as a "Debt" section.

    Returns:
        Formatted report string.
    """
    body = ""
    if format == "json":
        body = format_json(results, include_summary, debt_report=debt_report)
    else:
        body = format_markdown(results, include_summary)

    # Append debt section for markdown
    if debt_report is not None and format != "json":
        sep = "\n---\n\n" if body.strip() else ""
        body += sep + debt_section(debt_report)

    return body


def format_markdown(
    results: list[ScanResult],
    include_summary: bool,
) -> str:
    """Format results as markdown."""
    lines: list[str] = []

    if include_summary and results:
        summaries = [r.summary for r in results if r.summary]
        if summaries:
            lines.append("## Analysis Summary")
            lines.append("")
            for s in summaries:
                lines.append(f"- {s}")
            lines.append("")

    for result in results:
        if not result.findings:
            continue

        lines.append(f"### {result.scan_name.replace('-', ' ').title()}")
        lines.append("")

        # Group by severity
        for severity in ("error", "warning", "info"):
            severity_findings = [
                f for f in result.findings if f.severity == severity
            ]
            if not severity_findings:
                continue

            label = severity.upper()
            for finding in severity_findings:
                file_ref = f" `{finding.file}`" if finding.file else ""
                line_ref = f":{finding.line}" if finding.line else ""
                lines.append(
                    f"- **[{label}]{file_ref}{line_ref}** — {finding.message}"
                )
        lines.append("")

    # Show clean results
    for result in results:
        if not result.findings:
            lines.append(f"### {result.scan_name.replace('-', ' ').title()}")
            lines.append("")
            lines.append("✅ No issues found.")
            lines.append("")

    return "\n".join(lines)


def format_json(
    results: list[ScanResult],
    include_summary: bool,
    debt_report: Optional[DebtReport] = None,
) -> str:
    """Format results as JSON."""
    data: dict[str, Any] = {
        "scans": [],
    }

    if include_summary:
        data["summary"] = " | ".join(r.summary for r in results if r.summary)

    if debt_report is not None:
        data["architecture_debt"] = {
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "message": v.message,
                    "file": v.file,
                    "line": v.line,
                    "details": v.details,
                }
                for v in debt_report.violations
            ],
            "scanned_files": debt_report.scanned_files,
            "summary": debt_report.summary,
        }
        total_effort, effort_str = _estimate_effort(debt_report.violations)
        data["architecture_debt"]["estimated_effort_hours"] = round(total_effort, 1)
        data["architecture_debt"]["estimated_effort_display"] = effort_str

    for result in results:
        scan_data = {
            "scan_name": result.scan_name,
            "summary": result.summary,
            "metrics": result.metrics,
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "message": f.message,
                    "file": f.file,
                    "line": f.line,
                    "details": f.details,
                }
                for f in result.findings
            ],
        }
        data["scans"].append(scan_data)

    return json.dumps(data, indent=2, default=str)
