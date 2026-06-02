"""Tests for phase/circuit_breaker.py: CircuitBreaker and Registry.

Tests cover:
- CircuitBreakerState: attempt tracking, tripping, auto-reset
- CircuitBreakerRegistry: get/create, can_dispatch, failure/success recording
- Escalation chain determination
- Edge cases: negative attempt values, clean state
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from harness.phase.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitBreakerState,
)


class TestCircuitBreakerState:
    """CircuitBreakerState data object tests."""

    def test_default_values(self) -> None:
        """Default state values."""
        state = CircuitBreakerState(step_key="test.step_0")
        assert state.step_key == "test.step_0"
        assert state.max_attempts == 3
        assert state.reset_window_seconds == 60.0
        assert state.failures == []
        assert state.tripped is False
        assert state.tripped_at is None

    def test_custom_values(self) -> None:
        """Custom max_attempts and reset window."""
        state = CircuitBreakerState(
            step_key="custom.step",
            max_attempts=5,
            reset_window_seconds=120.0,
        )
        assert state.max_attempts == 5
        assert state.reset_window_seconds == 120.0

    def test_attempt_count_empty(self) -> None:
        """No failures means zero attempts."""
        state = CircuitBreakerState(step_key="test.step")
        assert state.attempt_count == 0

    def test_attempt_count_with_failures(self) -> None:
        """Failures within window are counted."""
        state = CircuitBreakerState(step_key="test.step", max_attempts=3)
        state.failures = [time.time(), time.time() - 5]
        assert state.attempt_count == 2

    def test_remaining_attempts(self) -> None:
        """Remaining attempts decrease with failures."""
        state = CircuitBreakerState(step_key="test.step", max_attempts=3)
        assert state.remaining_attempts == 3

        state.failures = [time.time(), time.time() - 5]
        assert state.remaining_attempts == 1

    def test_record_failure_trips_when_limit_reached(self) -> None:
        """Circuit trips when max_attempts reached."""
        state = CircuitBreakerState(step_key="test.step", max_attempts=2)
        state.record_failure()
        assert state.tripped is False  # 1 < 2

        state.record_failure()
        assert state.tripped is True
        assert state.tripped_at is not None

    def test_record_success_resets(self) -> None:
        """Recording success clears failures and un-trips."""
        state = CircuitBreakerState(step_key="test.step", max_attempts=2)
        state.failures = [time.time(), time.time() - 5]
        state.tripped = True
        state.tripped_at = time.time()

        state.record_success()

        assert state.failures == []
        assert state.tripped is False
        assert state.tripped_at is None

    def test_is_tripped_auto_reset_after_window(self) -> None:
        """Circuit auto-resets after the reset window elapses."""
        state = CircuitBreakerState(
            step_key="test.step",
            max_attempts=2,
            reset_window_seconds=0.01,  # Very short window
        )
        state.tripped = True
        state.tripped_at = time.time() - 0.1  # 100ms ago

        time.sleep(0.02)  # Wait for window to pass

        assert state.is_tripped() is False
        assert state.tripped is False

    def test_is_tripped_no_auto_reset_within_window(self) -> None:
        """Circuit stays tripped within the reset window."""
        state = CircuitBreakerState(
            step_key="test.step",
            max_attempts=2,
            reset_window_seconds=60.0,
        )
        state.tripped = True
        state.tripped_at = time.time() - 5  # 5 seconds ago

        assert state.is_tripped() is True

    def test_is_tripped_false_when_not_tripped(self) -> None:
        """Circuit not tripped returns False."""
        state = CircuitBreakerState(step_key="test.step")
        assert state.is_tripped() is False

    def test_old_failures_excluded_from_attempt_count(self) -> None:
        """Failures outside the reset window are excluded."""
        state = CircuitBreakerState(
            step_key="test.step",
            max_attempts=3,
            reset_window_seconds=10.0,
        )
        state.failures = [time.time() - 20, time.time() - 15,
                          time.time() - 5]

        assert state.attempt_count == 1  # Only last one within window


class TestCircuitBreakerRegistry:
    """CircuitBreakerRegistry tests."""

    @pytest.fixture
    def registry(self) -> CircuitBreakerRegistry:
        """Create a fresh registry."""
        return CircuitBreakerRegistry()

    def test_get_or_create_new(self, registry: CircuitBreakerRegistry) -> None:
        """get_or_create creates a new breaker when none exists."""
        breaker = registry.get_or_create("test.step_0")
        assert breaker.step_key == "test.step_0"
        assert breaker.max_attempts == 3

    def test_get_or_create_existing(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """get_or_create returns existing breaker."""
        b1 = registry.get_or_create("test.step_0")
        b2 = registry.get_or_create("test.step_0")
        assert b1 is b2

    def test_get_returns_none_when_not_found(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """get returns None for unknown step key."""
        assert registry.get("nonexistent") is None

    def test_get_returns_breaker(self, registry: CircuitBreakerRegistry) -> None:
        """get returns the correct breaker."""
        registry.get_or_create("test.step_0")
        breaker = registry.get("test.step_0")
        assert breaker is not None
        assert breaker.step_key == "test.step_0"

    def test_can_dispatch_new_step(self, registry: CircuitBreakerRegistry) -> None:
        """New steps can always be dispatched."""
        assert registry.can_dispatch("new.step") is True

    def test_can_dispatch_blocked_when_tripped(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Tripped circuit blocks dispatch."""
        breaker = registry.get_or_create("test.step", max_attempts=1)
        breaker.record_failure()  # Trips on first failure

        assert registry.can_dispatch("test.step") is False

    def test_can_dispatch_allowed_after_success(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Circuit allows dispatch after success resets."""
        breaker = registry.get_or_create("test.step", max_attempts=1)
        breaker.record_failure()
        breaker.record_success()

        assert registry.can_dispatch("test.step") is True

    def test_record_failure_returns_tripped(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """record_failure returns trip status."""
        registry.get_or_create("test.step", max_attempts=2)

        tripped = registry.record_failure("test.step")
        assert tripped is False

        tripped = registry.record_failure("test.step")
        assert tripped is True

    def test_record_success_nonexistent(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """record_success on unknown step key does nothing."""
        registry.record_success("nonexistent")  # Should not raise

    def test_determine_escalation_unknown(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Unknown step returns 'step' escalation."""
        assert registry.determine_escalation("unknown") == "step"

    def test_determine_escalation_tripped(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Tripped circuit returns 'workflow' escalation."""
        registry.get_or_create("test.step", max_attempts=1)
        registry.record_failure("test.step")

        assert registry.determine_escalation("test.step") == "workflow"

    def test_determine_escalation_step_level(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """One failure within limits returns 'step' escalation."""
        registry.get_or_create("test.step", max_attempts=3)
        registry.record_failure("test.step")

        assert registry.determine_escalation("test.step") == "step"

    def test_determine_escalation_phase_level(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Two out of three attempts returns 'phase' escalation."""
        registry.get_or_create("test.step", max_attempts=3)
        registry.record_failure("test.step")
        registry.record_failure("test.step")

        assert registry.determine_escalation("test.step") == "phase"

    def test_list_all_empty(self, registry: CircuitBreakerRegistry) -> None:
        """Empty registry returns empty list."""
        assert registry.list_all() == []

    def test_list_all(self, registry: CircuitBreakerRegistry) -> None:
        """Registry lists all breakers."""
        registry.get_or_create("a")
        registry.get_or_create("b")
        registry.get_or_create("c")

        all_breakers = registry.list_all()
        assert len(all_breakers) == 3

    def test_reset_all(self, registry: CircuitBreakerRegistry) -> None:
        """reset_all clears all breakers."""
        registry.get_or_create("a")
        registry.get_or_create("b")
        registry.reset_all()

        assert registry.list_all() == []

    def test_custom_max_attempts_and_window(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Custom parameters are passed through."""
        breaker = registry.get_or_create(
            "test.step", max_attempts=5, reset_window_seconds=300.0
        )
        assert breaker.max_attempts == 5
        assert breaker.reset_window_seconds == 300.0
