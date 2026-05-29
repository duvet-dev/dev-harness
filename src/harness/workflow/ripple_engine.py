"""WorkflowRippleEngine — phase-to-phase transition logic — V7 §5.15.

Determines what happens when a phase completes: what's the next phase?
Handles conditional transitions, ripple effects, and artifact passing
between phases.

The ripple engine:
- Determines the next phase after completion (linear or conditional)
- Passes artifacts between phases
- Handles conditional jumps based on phase outputs
- Detects ripple effects: changes that propagate to downstream phases
- Supports optional phases that can be skipped

See V7 §5.15 for the design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from harness.phase.strategy.base import PhaseResult
from harness.tracing import TraceLogger
from harness.workflow.model import (
    WorkflowState,
    WorkflowStatus,
)

logger = TraceLogger("harness.workflow.ripple_engine")


class TransitionType(str, Enum):
    """Type of phase-to-phase transition.

    LINEAR: Simple sequential transition to the next phase.
    CONDITIONAL: Transition depends on phase outputs/outcomes.
    OPTIONAL_SKIP: Phase was optional and was skipped.
    END_OF_WORKFLOW: No more phases — workflow is complete.
    """

    LINEAR = "linear"
    CONDITIONAL = "conditional"
    OPTIONAL_SKIP = "optional_skip"
    END_OF_WORKFLOW = "end_of_workflow"


@dataclass
class PhaseTransition:
    """Result of a phase-to-phase transition evaluation.

    Attributes:
        transition_type: Type of transition determined.
        next_phase: Name of the next phase, or None if workflow
            is complete.
        reason: Human-readable explanation for the transition.
        artifacts_passed: List of artifacts passed to the next
            phase.
        conditional_result: Description of conditional evaluation
            result, if applicable.
        re_enter_current: If True, the current phase should be
            re-entered (e.g., for retry or iteration).
    """

    transition_type: TransitionType
    next_phase: str | None = None
    reason: str = ""
    artifacts_passed: list[Any] = field(default_factory=list)
    conditional_result: str | None = None
    re_enter_current: bool = False


@dataclass
class RippleEffect:
    """A detected ripple effect — a change in one phase that
    affects downstream phases.

    Attributes:
        source_phase: Name of the phase where the change occurred.
        affected_phases: Names of phases that may need re-execution
            due to the change.
        description: Description of the change and its impact.
        severity: Severity level ("info", "warning", "critical").
    """

    source_phase: str
    affected_phases: list[str] = field(default_factory=list)
    description: str = ""
    severity: str = "info"


class WorkflowRippleEngine:
    """Determines phase-to-phase transitions and ripple effects.

    Evaluates what should happen after a phase completes, handling
    linear progressions, conditional jumps, optional skips, and
    artifact passing.

    Usage::

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(
            state=workflow_state,
            phase_result=phase_result,
            artifact_map=artifact_map,
        )
    """

    def __init__(self) -> None:
        self._conditional_rules: dict[
            str, list[_ConditionalRule]
        ] = {}

    # ── Transition Determination ─────────────────────────────────────

    def determine_transition(
        self,
        state: WorkflowState,
        phase_result: PhaseResult | None = None,
        artifact_map: dict[str, list[Any]] | None = None,
    ) -> PhaseTransition:
        """Determine the next phase transition after a phase completes.

        Args:
            state: Current workflow state.
            phase_result: Optional PhaseResult from the completed
                phase, used for conditional transitions.
            artifact_map: Optional mapping of phase names to
                artifacts they produced, used for artifact passing
                and conditional evaluation.

        Returns:
            PhaseTransition describing the next step.
        """
        # Determine which phase just completed (or failed)
        source_phase = None
        if state.completed_phases:
            source_phase = state.completed_phases[-1]
        elif state.failed_phases:
            source_phase = state.failed_phases[-1]

        if source_phase is None:
            return PhaseTransition(
                transition_type=TransitionType.LINEAR,
                next_phase=state.current_phase or (
                    state.pending_phases[0]
                    if state.pending_phases
                    else None
                ),
                reason="Starting first phase",
            )

        # Check for conditional rules on the source phase
        if source_phase in self._conditional_rules:
            rules = self._conditional_rules[source_phase]
            for rule in rules:
                transition = rule.evaluate(
                    phase_result=phase_result,
                    artifact_map=artifact_map,
                )
                if transition is not None:
                    logger.info(
                        "WorkflowRippleEngine — conditional transition",
                        extra={
                            "from_phase": source_phase,
                            "to_phase": transition.next_phase,
                            "condition": rule.description,
                        },
                    )
                    return transition

        # Check if phase failed — may need re-entry
        if phase_result and not phase_result.success:
            if source_phase in state.failed_phases:
                return PhaseTransition(
                    transition_type=TransitionType.CONDITIONAL,
                    next_phase=source_phase,
                    reason=(
                        f"Phase '{source_phase}' failed. "
                        f"Re-entering for retry."
                    ),
                    re_enter_current=True,
                )

        # Standard linear progression
        if state.pending_phases:
            next_phase = state.pending_phases[0]
            # Check if the next phase depends on artifacts from
            # previous phases
            passed_artifacts = self._collect_artifacts(
                target_phase=next_phase,
                source_phase=source_phase,
                artifact_map=artifact_map or {},
            )

            return PhaseTransition(
                transition_type=TransitionType.LINEAR,
                next_phase=next_phase,
                reason=(
                    f"Linear progression: '{source_phase}' → "
                    f"'{next_phase}'"
                ),
                artifacts_passed=passed_artifacts,
            )

        # No more phases — workflow complete
        return PhaseTransition(
            transition_type=TransitionType.END_OF_WORKFLOW,
            next_phase=None,
            reason="All phases complete — end of workflow",
        )

    def determine_ripple_effects(
        self,
        changed_phase: str,
        completed_phases: list[str],
        pending_phases: list[str],
        artifact_map: dict[str, list[Any]] | None = None,
    ) -> list[RippleEffect]:
        """Detect ripple effects when a phase result changes downstream.

        When a phase produces different output than expected, it may
        affect downstream phases that depend on it.

        Args:
            changed_phase: Name of the phase whose output changed.
            completed_phases: List of completed phase names (in
                order).
            pending_phases: List of pending phase names.
            artifact_map: Optional mapping of phase names to
                artifacts, used to detect artifact changes.

        Returns:
            List of RippleEffect objects describing detected
            ripple effects.
        """
        effects: list[RippleEffect] = []

        # Phases after the changed phase may be affected
        all_phases = completed_phases + pending_phases
        changed_idx = next(
            (i for i, p in enumerate(all_phases) if p == changed_phase),
            None,
        )
        if changed_idx is None:
            return effects

        downstream_phases = all_phases[changed_idx + 1 :]
        if not downstream_phases:
            return effects

        # Detect which downstream phases depend on this phase
        affected = self._find_affected_downstream(
            source_phase=changed_phase,
            downstream_phases=downstream_phases,
            artifact_map=artifact_map or {},
        )

        if affected:
            effects.append(
                RippleEffect(
                    source_phase=changed_phase,
                    affected_phases=affected,
                    description=(
                        f"Change in '{changed_phase}' may affect "
                        f"{len(affected)} downstream phase(s): "
                        f"{', '.join(affected)}"
                    ),
                    severity="warning",
                )
            )

        return effects

    # ── Conditional Rules ────────────────────────────────────────────

    def add_conditional_rule(
        self,
        from_phase: str,
        rule: _ConditionalRule,
    ) -> None:
        """Register a conditional transition rule for a phase.

        When a phase completes, the engine evaluates all registered
        rules for that phase. The first matching rule determines
        the transition.

        Args:
            from_phase: Name of the phase to attach the rule to.
            rule: The conditional rule to register.
        """
        if from_phase not in self._conditional_rules:
            self._conditional_rules[from_phase] = []
        self._conditional_rules[from_phase].append(rule)
        logger.debug(
            "WorkflowRippleEngine — conditional rule added",
            extra={
                "from_phase": from_phase,
                "description": rule.description,
                "target": rule.target_phase,
            },
        )

    def add_conditional_rules(
        self,
        from_phase: str,
        rules: list[_ConditionalRule],
    ) -> None:
        """Register multiple conditional rules for a phase.

        Args:
            from_phase: Name of the phase to attach rules to.
            rules: List of conditional rules to register.
        """
        for rule in rules:
            self.add_conditional_rule(from_phase, rule)

    def get_rules_for_phase(
        self, phase_name: str
    ) -> list[_ConditionalRule]:
        """Get all conditional rules registered for a phase.

        Args:
            phase_name: Name of the phase.

        Returns:
            List of conditional rules for the phase (may be empty).
        """
        return list(self._conditional_rules.get(phase_name, []))

    # ── Optional Phase Support ───────────────────────────────────────

    def is_phase_optional(
        self,
        phase_name: str,
        state: WorkflowState,
    ) -> bool:
        """Check if a phase is optional in the current workflow.

        A phase may be optional based on:
        - Phase naming convention (e.g., prefixed with "optional-")
        - Workflow metadata
        - Runtime conditions

        Args:
            phase_name: Name of the phase to check.
            state: Current workflow state.

        Returns:
            True if the phase is optional.
        """
        # Phases prefixed with "optional-" are always optional
        if phase_name.startswith("optional-"):
            return True

        # Check metadata for optional flag
        optional_phases = state.metadata.get("optional_phases", [])
        if phase_name in optional_phases:
            return True

        return False

    def skip_optional_phase(
        self,
        phase_name: str,
        state: WorkflowState,
    ) -> PhaseTransition:
        """Skip an optional phase and advance to the next one.

        Args:
            phase_name: Name of the optional phase to skip.
            state: Current workflow state.

        Returns:
            PhaseTransition skipping to the next non-optional
            phase or the end of the workflow.

        Raises:
            ValueError: If the phase is not in pending phases.
        """
        if phase_name not in state.pending_phases:
            raise ValueError(
                f"Cannot skip '{phase_name}': not in pending phases"
            )

        state.pending_phases.remove(phase_name)

        next_phase = (
            state.pending_phases[0] if state.pending_phases else None
        )

        return PhaseTransition(
            transition_type=TransitionType.OPTIONAL_SKIP,
            next_phase=next_phase,
            reason=f"Optional phase '{phase_name}' skipped",
        )

    # ── Internal Helpers ─────────────────────────────────────────────

    def _collect_artifacts(
        self,
        target_phase: str,
        source_phase: str,
        artifact_map: dict[str, list[Any]],
    ) -> list[Any]:
        """Collect artifacts from source phase to pass to target.

        Args:
            target_phase: The phase being entered.
            source_phase: The phase that just completed.
            artifact_map: Full artifact map for context.

        Returns:
            List of artifacts to pass. Currently returns all
            artifacts from completed phases, building up a
            cumulative context for the next phase.
        """
        passed: list[Any] = []

        # Collect artifacts from all completed phases
        for phase_name, artifacts in artifact_map.items():
            if artifacts:
                passed.extend(artifacts)

        logger.debug(
            "WorkflowRippleEngine — collecting artifacts",
            extra={
                "source_phase": source_phase,
                "target_phase": target_phase,
                "artifacts_count": len(passed),
            },
        )

        return passed

    def _find_affected_downstream(
        self,
        source_phase: str,
        downstream_phases: list[str],
        artifact_map: dict[str, list[Any]],
    ) -> list[str]:
        """Find downstream phases affected by a change in source.

        Uses heuristic: all downstream phases are potentially
        affected unless we have evidence to the contrary.

        Args:
            source_phase: The phase where the change occurred.
            downstream_phases: List of phases after source.
            artifact_map: Mapping of phase names to artifacts.

        Returns:
            List of phase names that may be affected.
        """
        affected: list[str] = []

        for phase in downstream_phases:
            # Heuristic: if source produced artifacts and phase
            # exists downstream, it could be affected
            source_artifacts = artifact_map.get(source_phase, [])
            if source_artifacts:
                affected.append(phase)
            else:
                # Still potentially affected by indirect changes
                affected.append(phase)

        return affected


# ── Conditional Rule Types ───────────────────────────────────────────


class _ConditionalRule:
    """Internal: a conditional transition rule.

    Defines a condition under which a phase transitions to a
    specific target instead of the default linear progression.
    """

    def __init__(
        self,
        target_phase: str,
        description: str = "",
    ) -> None:
        """Initialise a conditional rule.

        Args:
            target_phase: Name of the phase to transition to when
                the condition is met.
            description: Human-readable description of the rule.
        """
        self.target_phase = target_phase
        self.description = description

    def evaluate(
        self,
        phase_result: PhaseResult | None = None,
        artifact_map: dict[str, list[Any]] | None = None,
    ) -> PhaseTransition | None:
        """Evaluate whether this rule's condition is met.

        Subclasses override this with specific condition logic.

        Args:
            phase_result: Result of the completed phase.
            artifact_map: Artifacts produced by completed phases.

        Returns:
            A PhaseTransition if the condition is met, or None
            to fall through to the next rule or default.
        """
        return None


class ArtifactConditionRule(_ConditionalRule):
    """A rule that triggers when a specific artifact type is present.

    Transitions to the target phase when the completed phase
    produced a specific type of artifact.
    """

    def __init__(
        self,
        target_phase: str,
        artifact_type: str,
        description: str = "",
    ) -> None:
        """Initialise an artifact-based conditional rule.

        Args:
            target_phase: Name of the phase to transition to.
            artifact_type: Artifact type to check for (from
                ArtifactType enum).
            description: Human-readable description of the rule.
        """
        super().__init__(target_phase, description or (
            f"If '{artifact_type}' artifact is produced, "
            f"transition to '{target_phase}'"
        ))
        self.artifact_type = artifact_type

    def evaluate(
        self,
        phase_result: PhaseResult | None = None,
        artifact_map: dict[str, list[Any]] | None = None,
    ) -> PhaseTransition | None:
        """Evaluate whether the required artifact type is present.

        Args:
            phase_result: Result of the completed phase.
            artifact_map: Artifacts produced by completed phases.

        Returns:
            A PhaseTransition if the artifact is found, or None.
        """
        if not artifact_map:
            return None

        for phase_name, artifacts in artifact_map.items():
            for artifact in artifacts:
                if hasattr(artifact, "artifact_type"):
                    if artifact.artifact_type == self.artifact_type:
                        return PhaseTransition(
                            transition_type=TransitionType.CONDITIONAL,
                            next_phase=self.target_phase,
                            reason=self.description,
                            conditional_result=(
                                f"Artifact '{self.artifact_type}' "
                                f"found from phase '{phase_name}'"
                            ),
                        )
                elif isinstance(artifact, dict):
                    if artifact.get("type") == self.artifact_type:
                        return PhaseTransition(
                            transition_type=TransitionType.CONDITIONAL,
                            next_phase=self.target_phase,
                            reason=self.description,
                            conditional_result=(
                                f"Artifact '{self.artifact_type}' "
                                f"found from phase '{phase_name}'"
                            ),
                        )

        return None


class FailureConditionRule(_ConditionalRule):
    """A rule that triggers when a phase fails.

    Transitions to the target phase (e.g., a recovery or triage
    phase) when the source phase fails.
    """

    def __init__(
        self,
        target_phase: str,
        description: str = "",
    ) -> None:
        """Initialise a failure-based conditional rule.

        Args:
            target_phase: Name of the phase to transition to on
                failure.
            description: Human-readable description of the rule.
        """
        super().__init__(target_phase, description or (
            f"On failure, transition to '{target_phase}'"
        ))

    def evaluate(
        self,
        phase_result: PhaseResult | None = None,
        artifact_map: dict[str, list[Any]] | None = None,
    ) -> PhaseTransition | None:
        """Evaluate whether the phase failed.

        Args:
            phase_result: Result of the completed phase.
            artifact_map: Not used for this rule type.

        Returns:
            A PhaseTransition if the phase failed, or None.
        """
        if phase_result and not phase_result.success:
            return PhaseTransition(
                transition_type=TransitionType.CONDITIONAL,
                next_phase=self.target_phase,
                reason=self.description,
                conditional_result=(
                    f"Phase failed with error: {phase_result.error}"
                ),
            )
        return None
