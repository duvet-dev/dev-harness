"""Per-phase state tracking.

PhaseStateManager provides dict-backed per-phase state storage.
Wave 1 implementation is minimal; will be expanded in later waves
with context pruning and re-entry semantics.
See V7 §5.9 for the component spec.
"""

from __future__ import annotations

from typing import Any

from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.state_manager")


class PhaseStateManager:
    """Per-phase state tracking.

    Maintains a dict of phase → key → value mappings.
    Thread/async-safe for Wave 1 via simple dict operations.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}

    def set_state(self, phase: str, key: str, value: Any) -> None:
        """Set a state value for the given phase and key."""
        if phase not in self._states:
            self._states[phase] = {}
        self._states[phase][key] = value
        logger.debug(
            "PhaseStateManager.set_state",
            extra={"phase": phase, "key": key},
        )

    def get_state(
        self, phase: str, key: str, default: Any = None
    ) -> Any:
        """Get a state value, returning default if not found."""
        return self._states.get(phase, {}).get(key, default)

    def has_state(self, phase: str, key: str) -> bool:
        """Check if a state key exists for the given phase."""
        return key in self._states.get(phase, {})

    def clear_phase(self, phase: str) -> None:
        """Remove all state for a phase."""
        self._states.pop(phase, None)
        logger.debug(
            "PhaseStateManager.clear_phase",
            extra={"phase": phase},
        )

    def list_phases(self) -> list[str]:
        """Return all phase names with stored state."""
        return list(self._states.keys())

    def list_keys(self, phase: str) -> list[str]:
        """Return all state keys for a given phase."""
        return list(self._states.get(phase, {}).keys())
