"""PassThroughContext — unchanged context tracking — V7 §5.17.

Records which phases' context was passed through unchanged (i.e., no
new, modified, or removed artifacts). Used to skip artifact passing
for phases whose context hasn't changed, optimising the phase-to-phase
transition pipeline.

When the RippleEngine determines a phase's context is unchanged, the
WorkflowOrchestrator calls :meth:`mark_passed` to record the skip.
The next phase can then use :meth:`skip_unless_changed` to determine
which source phases actually contributed new context.

Usage::

    ptc = PassThroughContext()

    # Record that the 'analysis' phase passed through unchanged
    ptc.mark_passed("analysis")

    # Check if it was passed through
    assert ptc.was_passed("analysis") is True

    # Before transitioning to 'design', check which sources changed
    sources = ptc.skip_unless_changed(
        target_phase="design",
        source_phases=["analysis", "specification"],
    )
    # Returns only phases that changed or have never been passed through

See V7 §5.17 for the full design.
"""

from __future__ import annotations

from typing import Any


class PassThroughContext:
    """Tracks which phases' context was passed through unchanged.

    A "pass-through" means the phase produced no new, modified, or
    removed artifacts — its context is identical to what was passed
    in. Recording this allows the orchestrator to skip unnecessary
    context passing operations.

    Attributes:
        _passed: Set of phase names whose context was passed through
            unchanged.
        _phase_changes: Dict mapping phase name to a boolean
            indicating whether it actually had changes (True = had
            changes, i.e., not a pass-through).
    """

    def __init__(self) -> None:
        """Initialise an empty PassThroughContext."""
        self._passed: set[str] = set()
        self._phase_changes: dict[str, bool] = {}

    # ── Public API ──────────────────────────────────────────────────

    def mark_passed(self, phase_name: str) -> None:
        """Record that a phase's context was passed through unchanged.

        Args:
            phase_name: Name of the phase whose context was unchanged.

        Raises:
            TypeError: If ``phase_name`` is not a string.
            ValueError: If ``phase_name`` is empty.
        """
        if not isinstance(phase_name, str):
            raise TypeError(
                f"Expected str for phase_name, got "
                f"{type(phase_name).__name__}"
            )
        if not phase_name.strip():
            raise ValueError("phase_name must not be empty")

        self._passed.add(phase_name)
        self._phase_changes[phase_name] = False

    def mark_changed(self, phase_name: str) -> None:
        """Record that a phase's context actually changed.

        This is the inverse of :meth:`mark_passed` — call this
        when a phase produced new, modified, or removed artifacts.

        Args:
            phase_name: Name of the phase whose context changed.

        Raises:
            TypeError: If ``phase_name`` is not a string.
            ValueError: If ``phase_name`` is empty.
        """
        if not isinstance(phase_name, str):
            raise TypeError(
                f"Expected str for phase_name, got "
                f"{type(phase_name).__name__}"
            )
        if not phase_name.strip():
            raise ValueError("phase_name must not be empty")

        self._passed.discard(phase_name)
        self._phase_changes[phase_name] = True

    def was_passed(self, phase_name: str) -> bool:
        """Check if a phase's context was passed through unchanged.

        Args:
            phase_name: Name of the phase to check.

        Returns:
            True if the phase was marked as passed through (no
            context changes), False otherwise.

        Note:
            A phase that has never been recorded at all (neither
            passed nor changed) will return False.
        """
        return phase_name in self._passed

    def get_passed_phases(self) -> list[str]:
        """Get a sorted list of all phases that were passed through.

        Returns:
            Sorted list of phase names whose context was unchanged.
        """
        return sorted(self._passed)

    def get_changed_phases(self) -> list[str]:
        """Get a sorted list of all phases whose context changed.

        Returns:
            Sorted list of phase names whose context actually
            changed (were NOT passed through).
        """
        return sorted(
            name
            for name, changed in self._phase_changes.items()
            if changed
        )

    def skip_unless_changed(
        self,
        target_phase: str,
        source_phases: list[str],
    ) -> list[str]:
        """Filter source phases to only those that changed.

        Given a list of source phases that could provide context
        for a target phase, returns only those that:
        - Actually changed (were NOT passed through), OR
        - Have never been recorded (neither passed nor changed)

        Args:
            target_phase: Name of the target phase (used for
                logging/context; not used in filtering).
            source_phases: List of source phase names to filter.

        Returns:
            List of source phases that actually changed or have
            unknown status.

        Raises:
            TypeError: If ``target_phase`` is not a string or
                ``source_phases`` is not a list.
            ValueError: If ``target_phase`` is empty.
        """
        if not isinstance(target_phase, str):
            raise TypeError(
                f"Expected str for target_phase, got "
                f"{type(target_phase).__name__}"
            )
        if not target_phase.strip():
            raise ValueError("target_phase must not be empty")
        if not isinstance(source_phases, list):
            raise TypeError(
                f"Expected list for source_phases, got "
                f"{type(source_phases).__name__}"
            )

        result: list[str] = []
        for phase in source_phases:
            if not isinstance(phase, str):
                raise TypeError(
                    f"Each source phase must be a string, got "
                    f"{type(phase).__name__}"
                )
            if phase not in self._passed and not self._phase_changes.get(
                phase
            ):
                # Unknown/unrecorded — include it
                result.append(phase)
            elif self._phase_changes.get(phase, False):
                # It changed — include it
                result.append(phase)
            # Else: it was passed through — skip it

        return result

    def clear(self) -> None:
        """Reset all pass-through tracking.

        Clears both passed and changed records.
        """
        self._passed.clear()
        self._phase_changes.clear()

    def has_any_passes(self) -> bool:
        """Check if any phases have been recorded as passed through.

        Returns:
            True if at least one phase was marked as passed through.
        """
        return len(self._passed) > 0

    def has_any_changes(self) -> bool:
        """Check if any phases have been recorded as changed.

        Returns:
            True if at least one phase was marked as changed.
        """
        return any(self._phase_changes.values())

    # ── Properties ──────────────────────────────────────────────────

    @property
    def all_recorded_phases(self) -> list[str]:
        """Get all phases that have been recorded (passed or changed).

        Returns:
            Sorted list of all phase names with recorded status.
        """
        return sorted(self._phase_changes.keys())

    def __repr__(self) -> str:
        return (
            f"PassThroughContext("
            f"passed={len(self._passed)}, "
            f"changed={self._count_changed()}, "
            f"total={len(self._phase_changes)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PassThroughContext):
            return NotImplemented
        return (
            self._passed == other._passed
            and self._phase_changes == other._phase_changes
        )

    def _count_changed(self) -> int:
        """Count how many phases were recorded as changed."""
        return sum(1 for v in self._phase_changes.values() if v)
