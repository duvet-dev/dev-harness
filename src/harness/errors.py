"""Typed error hierarchy for the Dev Harness.

All errors subclass HarnessError. See V7 §8 for the full hierarchy.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base exception for all Dev Harness errors."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


# ── Validation Errors ────────────────────────────────────────────────


class ValidationError(HarnessError):
    """Base for all validation errors."""


class UnknownTeamError(ValidationError):
    """TeamRegistry: team name not found."""


class EmptyTeamError(ValidationError):
    """TeamRegistry: team has no agents."""


class UnknownPhaseError(ValidationError):
    """PhaseOrchestrator: phase not found."""


class UnknownAgentError(ValidationError):
    """AgentRegistry: agent name not found."""


class UnknownSkillError(ValidationError):
    """SkillsRegistry: skill name not found."""


class UnknownTemplateError(ValidationError):
    """TemplateRegistry: template not found."""


class StepMutualExclusionError(ValidationError):
    """Step: >1 or 0 of agents/team/loop/phase specified."""


class ConfigValidationError(ValidationError):
    """Config loader: schema violation."""


# ── Execution Errors ─────────────────────────────────────────────────


class ExecutionError(HarnessError):
    """Base for all execution errors."""


class StepDispatchError(ExecutionError):
    """StepDispatcher: agent dispatch failed."""


class PhaseExecutionError(ExecutionError):
    """PhaseOrchestrator: phase step failed."""


class LoopExecutionError(ExecutionError):
    """LoopRunner: loop iteration failed."""


class ParallelDispatchError(ExecutionError):
    """Parallel dispatch: partial failure."""


class AgentTimeoutError(ExecutionError):
    """Agent dispatch: timeout exceeded."""


class AggregatorError(ExecutionError):
    """LeadAggregator: technical failure."""


class CircuitBreakerTrippedError(ExecutionError):
    """CircuitBreaker: step dispatch blocked due to tripped circuit."""


# ── State Errors ─────────────────────────────────────────────────────


class StateError(HarnessError):
    """Base for all state errors."""


class EngagementNotFoundError(StateError):
    """EngagementRepository: engagement not found."""


class EngagementCorruptStateError(StateError):
    """Engagement state is corrupt/unreadable."""


class EngagementBranchMissingError(StateError):
    """Target branch for engagement does not exist."""


class EngagementDirtyStateError(StateError):
    """Repository has uncommitted changes."""


class PhaseStateNotFoundError(StateError):
    """PhaseStateManager: state for phase not found."""


# ── Command Errors ───────────────────────────────────────────────────


class CommandError(HarnessError):
    """Base for all command errors."""


class UnknownCommandError(CommandError):
    """CommandBus: unknown command type."""


class HandlerNotFoundError(CommandError):
    """CommandRegistry: no handler registered for command."""


class CommandValidationError(CommandError):
    """CommandBus: command failed validation."""


# ── Other Errors ─────────────────────────────────────────────────────


class NLTranslationError(HarnessError):
    """NL translator could not parse user input."""


class WebSearchUnavailableError(HarnessError):
    """Web search provider is unavailable."""


class BoundaryTestViolationError(HarnessError):
    """Plan validator: first wave not a boundary test (R20)."""
