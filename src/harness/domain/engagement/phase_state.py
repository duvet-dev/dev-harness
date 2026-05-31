"""Phase state model for cross-phase navigation.

Tracks the state of each phase in an engagement and supports
non-linear transitions (ACTIVE → PAUSED → ACTIVE, etc.).

State is persisted in ``.harness/engagements/<slug>/phases.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from harness.domain.engagement.lifecycle import ENGAGEMENTS_DIR


class PhaseState(str, Enum):
    """Possible states for a phase in the lifecycle."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FEEDBACK_SENT = "feedback_sent"
    FEEDBACK_WAIT = "feedback_wait"


# ── Valid transitions ──────────────────────────────────────────────────────

_VALID_TRANSITIONS: dict[PhaseState, set[PhaseState]] = {
    PhaseState.NOT_STARTED: {PhaseState.ACTIVE},
    PhaseState.ACTIVE: {PhaseState.COMPLETED, PhaseState.PAUSED, PhaseState.FEEDBACK_SENT, PhaseState.FEEDBACK_WAIT},
    PhaseState.PAUSED: {PhaseState.ACTIVE, PhaseState.FEEDBACK_SENT},
    PhaseState.COMPLETED: set(),  # terminal
    PhaseState.FEEDBACK_SENT: {PhaseState.COMPLETED},
    PhaseState.FEEDBACK_WAIT: {PhaseState.ACTIVE, PhaseState.COMPLETED},
}


# ── Exceptions ─────────────────────────────────────────────────────────────


class InvalidTransitionError(ValueError):
    """Raised when attempting an invalid phase state transition."""

    def __init__(self, current: PhaseState, target: PhaseState, phase: str) -> None:
        super().__init__(
            f"Cannot transition phase '{phase}' from {current.value} "
            f"to {target.value}"
        )


class PhaseNotFoundError(KeyError):
    """Raised when referencing a phase that doesn't exist."""


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass
class PhaseRecord:
    """State of a single phase."""

    state: PhaseState = PhaseState.NOT_STARTED
    completed_at: Optional[str] = None
    paused_at: Optional[str] = None
    checkpoint_ref: Optional[str] = None
    feedback_target: Optional[str] = None

    def to_dict(self) -> dict:
        result: dict = {"state": self.state.value}
        if self.completed_at:
            result["completed_at"] = self.completed_at
        if self.paused_at:
            result["paused_at"] = self.paused_at
        if self.checkpoint_ref:
            result["checkpoint_ref"] = self.checkpoint_ref
        if self.feedback_target:
            result["feedback_target"] = self.feedback_target
        return result

    @classmethod
    def from_dict(cls, data: dict) -> PhaseRecord:
        state = PhaseState(data.get("state", "not_started"))
        return cls(
            state=state,
            completed_at=data.get("completed_at"),
            paused_at=data.get("paused_at"),
            checkpoint_ref=data.get("checkpoint_ref"),
            feedback_target=data.get("feedback_target"),
        )


# ── Phase state manager ────────────────────────────────────────────────────


class PhaseStateManager:
    """Manages the state of all phases in an engagement.

    Loads and persists state from ``phases.yaml`` in the engagement
    directory. Validates all transitions.
    """

    def __init__(self, root: Path, slug: str) -> None:
        self._root = root
        self._slug = slug
        self._phases: dict[str, PhaseRecord] = {}
        self._dirty = False
        self._load()

    # ── Path ────────────────────────────────────────────────────────────────

    @property
    def state_path(self) -> Path:
        """Path to the phases.yaml file for this engagement."""
        return (
            self._root
            / ENGAGEMENTS_DIR
            / self._slug
            / "phases.yaml"
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def ensure_phase(self, name: str) -> PhaseRecord:
        """Get or create a phase record.

        Returns the existing record if the phase already exists,
        otherwise creates a new NOT_STARTED record.
        """
        if name not in self._phases:
            self._phases[name] = PhaseRecord()
            self._dirty = True
        return self._phases[name]

    def list_phases(self) -> dict[str, PhaseRecord]:
        """Return a copy of all phase records."""
        return dict(self._phases)

    def get_state(self, name: str) -> PhaseState:
        """Get the current state of a phase."""
        return self.ensure_phase(name).state

    def transition(self, name: str, target: PhaseState) -> PhaseRecord:
        """Transition a phase to a new state.

        Validates the transition is allowed. Automatically sets
        timestamps for COMPLETED and PAUSED states.
        """
        record = self.ensure_phase(name)
        current = record.state

        if target not in _VALID_TRANSITIONS.get(current, set()):
            raise InvalidTransitionError(current, target, name)

        record.state = target
        now = datetime.now(timezone.utc).isoformat()

        if target == PhaseState.COMPLETED:
            record.completed_at = now
        elif target == PhaseState.PAUSED:
            record.paused_at = now
        elif target == PhaseState.ACTIVE and current == PhaseState.PAUSED:
            # Resuming — clear pause timestamp
            record.paused_at = None

        self._dirty = True
        self._save()
        return record

    def mark_feedback_sent(
        self,
        name: str,
        target_phase: str,
        checkpoint_ref: str,
    ) -> PhaseRecord:
        """Transition a phase to FEEDBACK_SENT with target and checkpoint.

        Shorthand for:
            record.feedback_target = target_phase
            record.checkpoint_ref = checkpoint_ref
            transition(name, PhaseState.FEEDBACK_SENT)
        """
        self.transition(name, PhaseState.FEEDBACK_SENT)
        record = self._phases[name]
        record.feedback_target = target_phase
        record.checkpoint_ref = checkpoint_ref
        self._dirty = True
        self._save()
        return record

    def clear_feedback(self, name: str) -> None:
        """Clear feedback metadata after transitioning to COMPLETED."""
        if name in self._phases:
            self._phases[name].feedback_target = None
            self._phases[name].checkpoint_ref = None
            self._dirty = True
            self._save()

    def reset(self, name: str) -> None:
        """Reset a phase to NOT_STARTED (for re-entering)."""
        record = self.ensure_phase(name)
        record.state = PhaseState.NOT_STARTED
        record.completed_at = None
        record.paused_at = None
        record.checkpoint_ref = None
        record.feedback_target = None
        self._dirty = True
        self._save()

    def save(self) -> None:
        """Force-save state to disk if dirty."""
        if self._dirty:
            self._save()
            self._dirty = False

    # ── Persistence ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load phase state from phases.yaml."""
        path = self.state_path
        if not path.is_file():
            self._phases = {}
            return

        try:
            data = yaml.safe_load(path.read_text()) or {}
            phases_data = data.get("phases", {})
            self._phases = {
                name: PhaseRecord.from_dict(record)
                for name, record in phases_data.items()
            }
        except Exception:
            self._phases = {}

    def _save(self) -> None:
        """Write phase state to phases.yaml."""
        path = self.state_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "phases": {
                name: record.to_dict()
                for name, record in sorted(self._phases.items())
            }
        }
        path.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
