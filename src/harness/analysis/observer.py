"""Observer mode — stand-alone analysis of any codebase.

Runs fast scan (and optionally deep analysis) on any directory, with
no dependency on harness state or constitution. Pure filesystem analysis.
Designed for the `harness observe <path>` command.

R22 — when --deep is used, also runs the LLM-based independent assessment
(P1-P5 analysis agents) for a comprehensive codebase evaluation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from harness.analysis.fast import scan_git_diff, scan_structure
from harness.analysis.deep import (
    assess_coverage,
    check_architecture_conformance,
    find_dead_code,
)
from harness.analysis.summary import format_report

logger = logging.getLogger(__name__)


def analyse(
    path: str | Path,
    deep: bool = False,
    project_type: str = "python",
    report_file: str | None = None,
) -> dict[str, Any]:
    """Analyse a codebase as an external observer.

    Args:
        path: Directory to analyse.
        deep: If True, run full deep analysis and LLM-based assessment (slower).
        project_type: Project archetype for conformance checks.
        report_file: If set, write report to this file.

    Returns:
        Dict with all scan results and the human-readable report.
    """
    root = Path(path).resolve()
    if not root.exists():
        return {
            "status": "error",
            "message": f"Path does not exist: {path}",
            "report": "",
        }

    results: list[ScanResult] = []

    # Always run fast scan
    from harness.analysis.base import ScanResult

    structure = scan_structure(root)
    results.append(structure)

    diff = scan_git_diff(root)
    results.append(diff)

    # Deep analysis (optional) — existing static checks
    if deep:
        conformance = check_architecture_conformance(root, project_type=project_type)
        results.append(conformance)

        coverage = assess_coverage(root)
        results.append(coverage)

        dead = find_dead_code(root)
        results.append(dead)

    # Produce combined report (fast + deep scans)
    report_parts = [format_report(results, include_summary=True)]

    # R22: LLM-based independent assessment when --deep
    assessment_report = None
    if deep:
        try:
            from harness.analysis.assessment import assess as run_assessment
            # Run asynchronously in a fresh event loop if needed
            assessment_report = asyncio.run(
                run_assessment(path, deep=True)
            )
            assessment_dict = assessment_report.to_dict()
            report_parts.append(assessment_dict["report"])
        except Exception as exc:
            logger.warning("LLM-based assessment failed (graceful degradation): %s", exc)
            report_parts.append(
                "\n## LLM-Based Assessment\n\n"
                "⚠️ Assessment agents unavailable — API key or backend may not be configured.\n"
                "Existing static deep analysis results are shown above.\n"
            )

    # Combine reports
    report = "\n\n---\n\n".join(report_parts)

    # Optionally write report to file
    report_path: Path | None = None
    if report_file:
        report_path = Path(report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

    return {
        "status": "ok",
        "path": str(root),
        "deep": deep,
        "scans": (
            {r.scan_name: {"findings": len(r.findings), "summary": r.summary} for r in results}
            if results
            else {}
        ),
        "assessment": assessment_report.to_dict() if assessment_report else None,
        "report": report,
        "report_file": str(report_path) if report_file else None,
    }


async def analyse_async(
    path: str | Path,
    deep: bool = False,
    project_type: str = "python",
    report_file: str | None = None,
) -> dict[str, Any]:
    """Analyse a codebase asynchronously as an external observer.

    Same flow as analyse() but safe to call from an existing running
    event loop (no asyncio.run() internally). Use this from Temporal
    activities, agent workers, or async CLI commands.

    Args:
        path: Directory to analyse.
        deep: If True, run full deep analysis and LLM-based assessment (slower).
        project_type: Project archetype for conformance checks.
        report_file: If set, write report to this file.

    Returns:
        Dict with all scan results and the human-readable report.
    """
    root = Path(path).resolve()
    if not root.exists():
        return {
            "status": "error",
            "message": f"Path does not exist: {path}",
            "report": "",
        }

    results: list[ScanResult] = []

    # Always run fast scan
    from harness.analysis.base import ScanResult

    structure = scan_structure(root)
    results.append(structure)

    diff = scan_git_diff(root)
    results.append(diff)

    # Deep analysis (optional) — existing static checks
    if deep:
        conformance = check_architecture_conformance(root, project_type=project_type)
        results.append(conformance)

        coverage = assess_coverage(root)
        results.append(coverage)

        dead = find_dead_code(root)
        results.append(dead)

    # Produce combined report (fast + deep scans)
    report_parts = [format_report(results, include_summary=True)]

    # R22: LLM-based independent assessment when --deep
    assessment_report = None
    if deep:
        try:
            from harness.analysis.assessment import assess as run_assessment
            # Await directly — safe in async context
            assessment_report = await run_assessment(path, deep=True)
            assessment_dict = assessment_report.to_dict()
            report_parts.append(assessment_dict["report"])
        except Exception as exc:
            logger.warning("LLM-based assessment failed (graceful degradation): %s", exc)
            report_parts.append(
                "\n## LLM-Based Assessment\n\n"
                "⚠️ Assessment agents unavailable — API key or backend may not be configured.\n"
                "Existing static deep analysis results are shown above.\n"
            )

    # Combine reports
    report = "\n\n---\n\n".join(report_parts)

    # Optionally write report to file
    report_path: Path | None = None
    if report_file:
        report_path = Path(report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

    return {
        "status": "ok",
        "path": str(root),
        "deep": deep,
        "scans": (
            {r.scan_name: {"findings": len(r.findings), "summary": r.summary} for r in results}
            if results
            else {}
        ),
        "assessment": assessment_report.to_dict() if assessment_report else None,
        "report": report,
        "report_file": str(report_path) if report_file else None,
    }
