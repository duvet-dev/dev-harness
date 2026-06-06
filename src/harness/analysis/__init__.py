"""Analysis package — code analysis and metrics.

Provides fast scanning, deep static analysis, observer mode,
and LLM-based independent assessment (R22).
"""

from harness.analysis.agents import (
    PROJECT_PROFILER,
    RESPONSIBILITY_DECODER,
    ARCHITECTURE_CRITIC,
    CODE_CRITIC,
    TEST_AUDITOR,
    AnalysisAgent,
    AnalysisAgentRegistry,
)
from harness.analysis.assessment import (
    AssessmentReport,
    assess,
    format_assessment_report,
    gather_context,
)
from harness.analysis.base import VALID_CATEGORIES, Finding, ScanResult
from harness.analysis.observer import analyse, analyse_async
from harness.analysis.summary import debt_section

__all__ = [
    "AnalysisAgent",
    "AnalysisAgentRegistry",
    "AssessmentReport",
    "Finding",
    "ScanResult",
    "VALID_CATEGORIES",
    "PROJECT_PROFILER",
    "RESPONSIBILITY_DECODER",
    "ARCHITECTURE_CRITIC",
    "CODE_CRITIC",
    "TEST_AUDITOR",
    "assess",
    "analyse",
    "analyse_async",
    "debt_section",
    "format_assessment_report",
    "gather_context",
]
