"""Per-step circuit breaker for iteration failure handling — V7 §5.8.

Tracks dispatch attempts per step within configurable reset windows.
When max_attempts is exceeded, the circuit trips and further
dispatches are blocked until the reset window elapses.

Escalation chain: step → loop → phase → workflow (V7 §5.8).

Failure state is recorded using the `.failed.md` artifact naming
convention (V7 §2.2).

See V7 §5.8 for the escalation chain design.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.circuit_breaker")


@dataclass
class CircuitBreakerState:
    """State tracking for a single circuit breaker.

    Attributes:
        step_key: Unique key identifying the step (e.g. "phase_name.step_0").
        max_attempts: Maximum dispatch attempts before tripping.
        reset_window_seconds: Seconds before the circuit auto-resets.
        failures: Timestamped list of failure events.
        tripped: Whether the circuit is currently tripped.
        tripped_at: Timestamp when the circuit was tripped.
    """

    step_key: str
    max_attempts: int = 3
    reset_window_seconds: float = 60.0
    failures: list[float] = field(default_factory=list)
    tripped: bool = False
    tripped_at: float | None = None

    @property
    def attempt_count(self) -> int:
        """Count failures within the current reset window.

        Filters out failures older than the reset window to
        support sliding-window counting.
        """
        now = time.time()
        window_start = now - self.reset_window_seconds
        return sum(1 for t in self.failures if t >= window_start)

    @property
    def remaining_attempts(self) -> int:
        """Number of remaining attempts before tripping."""
        return max(0, self.max_attempts - self.attempt_count)

    def record_failure(self) -> None:
        """Record a failure event and check if circuit should trip.

        Adds the current timestamp to the failures list. If
        max_attempts is reached within the reset window, the
        circuit trips.
        """
        now = time.time()
        self.failures.append(now)

        if self.attempt_count >= self.max_attempts:
            self.tripped = True
            self.tripped_at = now
            logger.warning(
                "CircuitBreaker — tripped",
                extra={
                    "step_key": self.step_key,
                    "attempt_count": self.attempt_count,
                    "max_attempts": self.max_attempts,
                    "reset_window": self.reset_window_seconds,
                },
            )

    def record_success(self) -> None:
        """Record a success — clears the failure history.

        A successful dispatch resets the circuit back to closed.
        """
        self.failures = []
        self.tripped = False
        self.tripped_at = None
        logger.debug(
            "CircuitBreaker — success, reset",
            extra={"step_key": self.step_key},
        )

    def is_tripped(self) -> bool:
        """Check if the circuit is currently tripped.

        If tripped but the reset window has elapsed, auto-resets.

        Returns:
            True if the circuit is still tripped (within reset window).
        """
        if not self.tripped:
            return False
        if self.tripped_at is None:
            return False
        if time.time() - self.tripped_at >= self.reset_window_seconds:
            self.tripped = False
            self.tripped_at = None
            self.failures = []
            logger.info(
                "CircuitBreaker — auto-reset",
                extra={
                    "step_key": self.step_key,
                    "reset_window": self.reset_window_seconds,
                },
            )
            return False
        return True


class CircuitBreakerRegistry:
    """Registry of per-step circuit breakers.

    Manages circuit breaker instances keyed by step identifier
    (e.g. "phase_name.step_index").

    Usage::

        registry = CircuitBreakerRegistry()
        cb = registry.get_or_create("my_phase.step_0", max_attempts=3)
        if cb.can_dispatch():
            # dispatch step
            cb.record_success()
        else:
            cb.record_failure()
            # escalate
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreakerState] = {}

    def get_or_create(
        self,
        step_key: str,
        max_attempts: int = 3,
        reset_window_seconds: float = 60.0,
    ) -> CircuitBreakerState:
        """Get an existing circuit breaker or create a new one.

        Args:
            step_key: Unique key for the step.
            max_attempts: Maximum failures before tripping.
            reset_window_seconds: Window in seconds for reset.

        Returns:
            The CircuitBreakerState for the given step_key.
        """
        if step_key not in self._breakers:
            self._breakers[step_key] = CircuitBreakerState(
                step_key=step_key,
                max_attempts=max_attempts,
                reset_window_seconds=reset_window_seconds,
            )
        return self._breakers[step_key]

    def get(self, step_key: str) -> CircuitBreakerState | None:
        """Get an existing circuit breaker, or None if not found.

        Args:
            step_key: Unique key for the step.

        Returns:
            The CircuitBreakerState or None.
        """
        return self._breakers.get(step_key)

    def can_dispatch(self, step_key: str) -> bool:
        """Check if a step can be dispatched.

        Returns True if the circuit is not tripped and has
        remaining attempts.

        Args:
            step_key: Unique key for the step.

        Returns:
            True if dispatch is allowed.
        """
        breaker = self.get(step_key)
        if breaker is None:
            return True
        if breaker.is_tripped():
            logger.warning(
                "CircuitBreaker — dispatch blocked (tripped)",
                extra={"step_key": step_key},
            )
            return False
        if breaker.remaining_attempts <= 0:
            logger.warning(
                "CircuitBreaker — dispatch blocked "
                "(no remaining attempts)",
                extra={
                    "step_key": step_key,
                    "remaining": breaker.remaining_attempts,
                },
            )
            return False
        return True

    def record_failure(self, step_key: str) -> bool:
        """Record a failure and return whether the circuit tripped.

        Args:
            step_key: Unique key for the step.

        Returns:
            True if the circuit is now tripped.
        """
        breaker = self.get_or_create(step_key)
        breaker.record_failure()
        return breaker.is_tripped()

    def record_success(self, step_key: str) -> None:
        """Record a success and reset the circuit breaker.

        Args:
            step_key: Unique key for the step.
        """
        breaker = self.get(step_key)
        if breaker:
            breaker.record_success()

    def determine_escalation(self, step_key: str) -> str:
        """Determine the escalation target based on circuit state.

        Escalation chain per V7 §5.8:
        - step → loop → phase → workflow

        Args:
            step_key: Unique key for the step.

        Returns:
            Escalation target: "step", "loop", "phase", or "workflow".
        """
        breaker = self.get(step_key)
        if breaker is None:
            return "step"

        if breaker.tripped:
            return "workflow"

        # Based on how many attempts have been consumed
        attempts_used = breaker.attempt_count
        if attempts_used >= breaker.max_attempts:
            return "workflow"
        elif attempts_used >= breaker.max_attempts - 1:
            return "phase"
        elif attempts_used >= 2:
            return "loop"
        else:
            return "step"

    def list_all(self) -> list[CircuitBreakerState]:
        """List all registered circuit breakers.

        Returns:
            List of all CircuitBreakerState instances.
        """
        return list(self._breakers.values())

    def reset_all(self) -> None:
        """Reset all circuit breakers to initial state."""
        self._breakers = {}
        logger.info("CircuitBreakerRegistry — all breakers reset")
