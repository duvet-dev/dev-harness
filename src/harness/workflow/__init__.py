"""Workflow orchestration package — V7 §5.14 / §5.15.

Workflow definitions, state tracking, multi-phase orchestration,
and phase-to-phase transition logic (ripple engine).

Exports:
    - Workflow, WorkflowState, WorkflowResult, WorkflowStatus (model)
    - WorkflowOrchestrator (orchestrator)
    - WorkflowRippleEngine, PhaseTransition, TransitionType,
      ArtifactConditionRule, FailureConditionRule (ripple_engine)
"""

from __future__ import annotations

from harness.workflow.model import (
    Workflow,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
)
from harness.workflow.orchestrator import WorkflowOrchestrator
from harness.workflow.ripple_engine import (
    ArtifactConditionRule,
    FailureConditionRule,
    PhaseTransition,
    RippleEffect,
    TransitionType,
    WorkflowRippleEngine,
)

__all__ = [
    "Workflow",
    "WorkflowResult",
    "WorkflowState",
    "WorkflowStatus",
    "WorkflowOrchestrator",
    "WorkflowRippleEngine",
    "PhaseTransition",
    "TransitionType",
    "RippleEffect",
    "ArtifactConditionRule",
    "FailureConditionRule",
]
