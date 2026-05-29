"""Tests for phase/strategy/base.py: PhaseStrategy ABC and PhaseResult.

Tests cover:
- PhaseStrategy abstract base class enforces execute() contract
- PhaseResult dataclass default values
- PhaseStrategyError exception
"""

from __future__ import annotations

import pytest

from harness.phase.strategy.base import (
    PhaseResult,
    PhaseStrategy,
    PhaseStrategyError,
)


class TestPhaseResult:
    """PhaseResult dataclass tests."""

    def test_default_success_true(self) -> None:
        """PhaseResult success defaults to True."""
        result = PhaseResult(success=True)
        assert result.success is True
        assert result.step_results == []
        assert result.error is None
        assert result.partial is False
        assert result.escalation is None

    def test_default_success_false(self) -> None:
        """PhaseResult with explicit failure."""
        result = PhaseResult(success=False, error="Something failed")
        assert result.success is False
        assert result.error == "Something failed"

    def test_with_step_results(self) -> None:
        """PhaseResult with step results."""
        steps = [
            {"step_name": "step_0", "success": True},
            {"step_name": "step_1", "success": False, "error": "failed"},
        ]
        result = PhaseResult(
            success=False,
            step_results=steps,
            error="One step failed",
            partial=True,
            escalation="phase",
        )
        assert result.success is False
        assert len(result.step_results) == 2
        assert result.partial is True
        assert result.escalation == "phase"


class TestPhaseStrategy:
    """PhaseStrategy ABC tests."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        """PhaseStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc:
            PhaseStrategy()  # type: ignore[abstract]
        assert "abstract" in str(exc.value).lower() or "Can't" in str(exc.value)

    def test_concrete_subclass_must_implement_execute(self) -> None:
        """Subclass without execute() raises TypeError."""
        with pytest.raises(TypeError):

            class IncompleteStrategy(PhaseStrategy):  # type: ignore[abstract]
                pass

            IncompleteStrategy()

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """Subclass with execute() can be instantiated."""

        class GoodStrategy(PhaseStrategy):
            async def execute(self, phase, context=None):
                return PhaseResult(success=True)

        strategy = GoodStrategy()
        assert isinstance(strategy, PhaseStrategy)


class TestPhaseStrategyError:
    """PhaseStrategyError tests."""

    def test_exception_can_be_raised(self) -> None:
        """PhaseStrategyError is a proper exception."""
        error = PhaseStrategyError("Strategy failed")
        assert str(error) == "Strategy failed"
        assert isinstance(error, Exception)
