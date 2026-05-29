"""Abstract base class for phase execution strategies — V7 §5.5.

Defines the PhaseStrategy protocol that all execution strategies
(sequential, parallel) must implement.

Each strategy receives a Phase definition and context, dispatches
steps via the StepDispatcher, and returns a PhaseResult.

See V7 §5.5 for the design and §5.4 for PhaseOrchestrator integration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class PhaseStrategyError(Exception):
    """Base exception for phase strategy errors."""


@dataclass
class PhaseResult:
    """Result of executing a phase.

    Attributes:
        success: True if the phase completed successfully.
        step_results: List of individual step results (dicts with
            step_name, success, artifacts, error).
        error: Error message if the phase failed.
        partial: True if some steps succeeded and some failed.
        escalation: Escalation chain target if phase failed
            ("loop", "phase", "workflow", or None).
    """

    success: bool
    step_results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    partial: bool = False
    escalation: str | None = None


class PhaseStrategy(ABC):
    """Abstract base class for phase execution strategies.

    Subclasses implement execute() to run a phase's steps using
    the appropriate dispatch mode (sequential, parallel, etc.).

    Usage::

        class MyStrategy(PhaseStrategy):
            async def execute(self, phase, context) -> PhaseResult:
                ...
    """

    @abstractmethod
    async def execute(
        self,
        phase: Any,
        context: Any | None = None,
    ) -> PhaseResult:
        """Execute all steps in a phase.

        Args:
            phase: The Phase definition containing steps to execute.
            context: Optional execution context.

        Returns:
            PhaseResult with success status and step results.
        """
        ...
