"""Typed handlers for analysis operations.

Covers: SummaryHandler, InspectHandler, AssessHandler.
"""

from __future__ import annotations

import asyncio

from harness.command.types import TypedHandler
from harness.command.commands.analysis import (
    AssessCommand,
    InspectCommand,
    SummaryCommand,
)
from harness.command.results.analysis import (
    AssessResult,
    InspectResult,
    SummaryResult,
)


class SummaryTypedHandler(TypedHandler[SummaryCommand, SummaryResult]):
    """Run project summary analysis."""

    def handle(self, command: SummaryCommand) -> SummaryResult:
        try:
            from pathlib import Path
            from harness.analysis.fast import scan_git_diff, scan_structure
            from harness.analysis.summary import format_report

            root = Path.cwd()
            deep = command.deep
            assess_flag = command.assess_flag
            json_flag = command.json_flag
            reconcile = command.reconcile

            if reconcile:
                from harness.cli.helpers import reconcile_before_summary
                reconcile_before_summary(root)

            results = []
            results.append(scan_structure(root))
            results.append(scan_git_diff(root))

            if deep:
                from harness.analysis.deep import (
                    assess_coverage,
                    check_architecture_conformance,
                    find_dead_code,
                )
                results.append(check_architecture_conformance(root, project_type="python"))
                results.append(assess_coverage(root))
                results.append(find_dead_code(root))

            output_format = "json" if json_flag else "markdown"
            report = format_report(results, format=output_format)

            if assess_flag:
                try:
                    from harness.analysis.assessment import assess as run_assessment
                    assessment = asyncio.run(run_assessment(root, deep=True))
                    if output_format == "json":
                        import json as json_mod
                        base = json_mod.loads(report)
                        base["assessment"] = assessment.to_dict().get("assessment", {})
                        report = json_mod.dumps(base, indent=2, default=str)
                    else:
                        report += "\n\n---\n\n" + assessment.report_text
                except Exception as exc:
                    report += (
                        "\n\n## LLM-Based Assessment\n\n"
                        f"\u26a0\ufe0f Assessment agents unavailable: {exc}\n"
                    )

            return SummaryResult(
                success=True,
                message="Summary generated",
                report=report,
                output_format=output_format,
            )

        except Exception as exc:
            return SummaryResult(
                success=False,
                error=str(exc),
                message=f"Summary failed: {exc}",
            )


class InspectTypedHandler(TypedHandler[InspectCommand, InspectResult]):
    """Run observer analysis."""

    def handle(self, command: InspectCommand) -> InspectResult:
        try:
            from harness.analysis.observer import analyse

            result = analyse(path=command.root, deep=True)

            if result["status"] == "error":
                return InspectResult(
                    success=False,
                    error=result.get("message", "Unknown error"),
                    message=f"Inspect analysis failed: {result.get('message', '')}",
                )

            assessment_dict = result.get("assessment")
            findings_count = "?"
            score = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings_count = len(ad.get("findings", []))

            return InspectResult(
                success=True,
                message=f"Assessment complete: {findings_count} findings, score: {score}",
                report=result["report"],
                findings_count=findings_count,
                score=score,
            )

        except Exception as exc:
            return InspectResult(
                success=False,
                error=str(exc),
                message=f"Inspect analysis failed: {exc}",
            )


class AssessTypedHandler(TypedHandler[AssessCommand, AssessResult]):
    """Run the full assessment on the project."""

    def handle(self, command: AssessCommand) -> AssessResult:
        try:
            from harness.analysis.observer import analyse

            result = analyse(path=command.root, deep=True, project_type=command.project_type)

            if result["status"] == "error":
                return AssessResult(
                    success=False,
                    error=result.get("message", "Unknown error"),
                    message=f"Assessment failed: {result.get('message', '')}",
                )

            assessment_dict = result.get("assessment")
            findings_count = "?"
            score = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings_count = len(ad.get("findings", []))

            return AssessResult(
                success=True,
                message=f"Assessment complete: {findings_count} findings, score: {score}",
                report=result["report"],
                findings_count=findings_count,
                score=score,
            )

        except Exception as exc:
            return AssessResult(
                success=False,
                error=str(exc),
                message=f"Assessment failed: {exc}",
            )
