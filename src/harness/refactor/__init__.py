"""Refactoring support — boundary analysis, test generation, orchestrator loop.

Provides:
- ``BoundaryCandidate`` — identified application boundary
- ``scan_boundary_candidates()`` — structural boundary inference
- ``present_and_confirm_boundaries()`` — user confirmation flow
- ``register_boundaries()`` / ``read_boundary_registration()`` — YAML persistence
- ``BoundaryTest`` — immutable behaviour-capturing test
- ``generate_boundary_test()`` — test file generation
- ``generate_boundary_test_module()`` — consolidated test module
- ``RefactorPhase`` — valid phases in a refactoring session
- ``RefactorSessionLoop`` — top-level refactoring orchestrator
- ``DebtDetector`` — rule-based architecture debt detection
- ``DebtReport`` / ``DebtViolation`` — debt data model
- ``VerificationRunner`` — post-refactoring verification pass
- ``RefactoringVerificationResult`` — verification results
"""

from .boundaries import (
    BoundaryCandidate,
    scan_boundary_candidates,
    present_and_confirm_boundaries,
    register_boundaries,
    read_boundary_registration,
)

from .boundary_tests import (
    BoundaryTest,
    IMMUTABLE_HEADER,
    generate_boundary_test,
    generate_boundary_test_module,
    verify_boundary_test_integrity,
)

from .loop import (
    RefactorPhase,
    validate_transition,
    RefactorSessionConfig,
    RefactorSessionState,
    RefactorSessionResult,
    RefactorSessionLoop,
    REFACTOR_PHASE_LABELS,
    REFACTOR_PHASE_ORDER,
)

from .debt import (
    DebtViolation,
    DebtReport,
    DebtDetector,
)

from .verification import (
    BoundaryTestCheck,
    TestSuiteResult,
    SummaryEntry,
    RefactoringVerificationResult,
    VerificationRunner,
)
from .suggestions import (
    RefactoringSuggestion,
    DebtSuggestionEngine,
    generate_suggestions,
)

__all__ = [
    "BoundaryCandidate",
    "scan_boundary_candidates",
    "present_and_confirm_boundaries",
    "register_boundaries",
    "read_boundary_registration",
    "BoundaryTest",
    "IMMUTABLE_HEADER",
    "generate_boundary_test",
    "generate_boundary_test_module",
    "verify_boundary_test_integrity",
    "RefactorPhase",
    "validate_transition",
    "RefactorSessionConfig",
    "RefactorSessionState",
    "RefactorSessionResult",
    "RefactorSessionLoop",
    "REFACTOR_PHASE_LABELS",
    "REFACTOR_PHASE_ORDER",
    "DebtViolation",
    "DebtReport",
    "DebtDetector",
    "BoundaryTestCheck",
    "TestSuiteResult",
    "SummaryEntry",
    "RefactoringVerificationResult",
    "VerificationRunner",
    "RefactoringSuggestion",
    "DebtSuggestionEngine",
    "generate_suggestions",
]
