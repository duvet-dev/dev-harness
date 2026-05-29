"""Artifact type definitions.

Defines the ArtifactType enum for typed artifacts.
See V7 §9 for the full specification.
"""

from __future__ import annotations

from enum import Enum


class ArtifactType(str, Enum):
    """Typed artifacts used as step inputs and outputs.

    Each artifact carries an ArtifactType for schema governance.
    Wave 1 includes a starter set; full 18 members from V7 §9
    can be populated in later waves.

    Key members:
        PLANNING_DOC: High-level planning document.
        REQUIREMENTS_SPEC: Requirements specification.
        ARCHITECTURE_DECISION: Architecture Decision Record (ADR).
        CODE_DIFF: Code changes as a diff/patch.
        TEST_RESULTS: Test execution results.
        COVERAGE_REPORT: Code coverage report.
        REVIEW_REPORT: Code review findings.
        SECURITY_REPORT: Security audit findings.
        DEPENDENCY_REPORT: Dependency analysis report.
        VALIDATION_REPORT: Validation/compliance report.
        BOUNDARY_TEST: Boundary/interface test.
        PLAN: Execution plan.
        SUMMARY: Summary/conclusion document.
    """

    PLANNING_DOC = "planning_doc"
    REQUIREMENTS_SPEC = "requirements_spec"
    ARCHITECTURE_DECISION = "architecture_decision"
    ARCHITECTURAL_OVERVIEW = "architectural_overview"
    CONSOLIDATED_REVIEW = "consolidated_review"
    CODE_DIFF = "code_diff"
    IMPLEMENTATION = "implementation"
    TEST_RESULTS = "test_results"
    COVERAGE_REPORT = "coverage_report"
    REVIEW_REPORT = "review_report"
    SECURITY_REPORT = "security_report"
    DEPENDENCY_REPORT = "dependency_report"
    VALIDATION_REPORT = "validation_report"
    BOUNDARY_TEST = "boundary_test"
    PLAN = "plan"
    ASSESSMENT = "assessment"
    FEEDBACK = "feedback"
    SUMMARY = "summary"
