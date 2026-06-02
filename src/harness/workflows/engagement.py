"""EngagementWorkflow — root workflow for the Dev Harness.

Orchestrates an engagement through its lifecycle phases with iteration
support. When a gate review returns ``request_changes``, the workflow
re-processes the same phase with feedback context instead of advancing
linearly. Iteration is bounded by ``IterationConfig.max_iterations``.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from typing import Optional

    from harness.workflows.signals import (
        EngagementQueryResult,
        FeedbackItem,
        GateReviewSignal,
        IterationConfig,
        StateReconcileSignal,
        WorkDoneSignal,
    )


GATE_TIMEOUT = timedelta(hours=72)

# Default phase list used when no phases are provided in config
DEFAULT_PHASES = ["requirements", "design", "planning", "implementation", "testing", "review"]


@workflow.defn(name="engagement-workflow")
class EngagementWorkflow:
    """Root workflow for a single engagement.

    Manages the engagement lifecycle:
    1. Accepts signals for gate review, work done, state reconcile
    2. Proceeds through phases with iteration (request_changes loops back)
    3. Exposes queries for summary and state
    """

    def __init__(self):
        self._engagement_id = ""
        self._description = ""
        self._status = "planning"
        self._phase = "requirements"
        self._gate_mode = "auto"
        self._pending_items = []
        self._retry_count = 0
        self._phases = []
        self._phase_list = list(DEFAULT_PHASES)
        self._tasks = []
        self._decisions = []
        self._gate_decision = None
        self._gate_event = None

        # Iteration state
        self._max_iterations = 5
        self._current_iteration = 0
        self._pending_feedback: list[FeedbackItem] = []
        self._escalation_after_max = True
        self._partial_approval = True

    @workflow.run
    async def run(self, config: dict) -> dict:
        """Run the engagement workflow with iteration support."""
        self._engagement_id = config.get("engagement_id", "unknown")
        self._description = config.get("description", "")
        self._gate_mode = config.get("gate_mode", "auto")
        self._phase = config.get("start_phase", "requirements")
        self._phase_list = config.get("phases", DEFAULT_PHASES)

        # Load iteration config if provided
        iteration_config_dict = config.get("iteration_config", {})
        iteration_config = IterationConfig.from_dict(iteration_config_dict)
        self._max_iterations = iteration_config.max_iterations
        self._escalation_after_max = iteration_config.escalation_after_max
        self._partial_approval = iteration_config.partial_approval

        self._status = "in_progress"

        # Iterate through phases
        phase_idx = self._phase_list.index(self._phase)

        while phase_idx < len(self._phase_list):
            self._phase = self._phase_list[phase_idx]
            self._current_iteration = 0

            # Inner iteration loop for the current phase
            while True:
                feedback_for_phase = (
                    self._pending_feedback if self._current_iteration > 0 else []
                )
                phase_result = await self._run_phase(feedback_for_phase)
                self._phases.append(phase_result)

                # Check gate
                if self._gate_mode == "full" or self._gate_mode == "auto" and self._pending_items:
                    await self._wait_for_gate()
                elif self._gate_mode == "auto" and feedback_for_phase:
                    # With iteration feedback, always wait for gate on non-first runs
                    await self._wait_for_gate()

                # Process gate decision
                if self._gate_decision == "approved":
                    self._current_iteration = 0
                    self._pending_feedback = []
                    break  # Exit inner loop, advance to next phase

                elif self._gate_decision == "request_changes":
                    self._current_iteration += 1
                    self._pending_feedback = list(getattr(self, "_pending_feedback_raw", []))

                    if self._current_iteration >= self._max_iterations:
                        # Escalate — hit iteration limit
                        self._status = "needs_human"
                        self._decisions.append({
                            "phase": self._phase,
                            "decision": "escalated",
                            "notes": (
                                f"Exceeded max iterations ({self._max_iterations}) "
                                f"on phase {self._phase}. Requires human intervention."
                            ),
                        })
                        return {
                            "engagement_id": self._engagement_id,
                            "status": self._status,
                            "phase": self._phase,
                            "iteration_count": self._current_iteration,
                        }

                    # Loop back to re-process same phase with feedback
                    workflow.logger.info(
                        f"Iteration {self._current_iteration}/{self._max_iterations} "
                        f"for phase {self._phase} — re-processing with feedback"
                    )
                    # Clear gate decision so we wait again
                    self._gate_decision = None

                elif self._gate_decision == "rejected":
                    self._status = "rejected"
                    return {
                        "engagement_id": self._engagement_id,
                        "status": self._status,
                        "phase": self._phase,
                        "iteration_count": self._current_iteration,
                    }
                else:
                    # No gate decision (timeout or user never sent one) — auto-advance
                    break

            # Advance to next phase
            phase_idx += 1

            # If we get here after escalation, the outer loop also exits
            if self._status == "needs_human":
                break

        if self._status != "needs_human" and self._status != "rejected":
            self._status = "completed"

        return {"engagement_id": self._engagement_id, "status": self._status}

    async def _run_phase(self, feedback_context: Optional[list[FeedbackItem]] = None) -> dict:
        """Execute the current phase, optionally with feedback context.

        Stub for now — in production this delegates to PhaseManager.
        """
        workflow.logger.info(
            f"Running phase: {self._phase} "
            f"(iteration {self._current_iteration}, "
            f"feedback_items: {len(feedback_context) if feedback_context else 0})"
        )
        return {
            "phase": self._phase,
            "status": "completed",
            "iteration": self._current_iteration,
            "feedback_count": len(feedback_context) if feedback_context else 0,
        }

    async def _wait_for_gate(self):
        """Wait for human gate review signal with timeout."""
        self._gate_decision = None
        self._pending_items = []

        try:
            await workflow.wait_condition(
                lambda: self._gate_decision is not None,
                timeout=GATE_TIMEOUT,
            )
        except Exception:
            workflow.logger.warning(f"Gate timeout after {GATE_TIMEOUT}")

    @workflow.signal
    async def gate_review(self, signal: GateReviewSignal) -> None:
        """Handle a gate review signal from the user."""
        self._gate_decision = signal.decision
        self._pending_feedback_raw = signal.feedback
        self._decisions.append({
            "phase": self._phase,
            "decision": signal.decision,
            "notes": signal.notes,
            "feedback": [f.to_dict() for f in signal.feedback],
        })
        if signal.decision == "rejected":
            self._retry_count += 1

    @workflow.signal
    async def work_done(self, signal: WorkDoneSignal) -> None:
        """Handle a work completion signal."""
        self._tasks.append({
            "task_id": signal.task_id,
            "status": signal.status,
            "summary": signal.summary,
        })

    @workflow.signal
    async def state_reconcile(self, signal: StateReconcileSignal) -> None:
        """Handle a state reconciliation signal."""
        self._pending_items = []
        if signal.corrected_fields.get("status"):
            self._status = signal.corrected_fields["status"]
        if signal.corrected_fields.get("phase"):
            self._phase = signal.corrected_fields["phase"]

    @workflow.query
    def summary(self) -> dict:
        """Return a summary of current engagement state."""
        return EngagementQueryResult(
            engagement_id=self._engagement_id,
            status=self._status,
            phase=self._phase,
            description=self._description,
            gate_mode=self._gate_mode,
            pending_items=self._pending_items,
            retry_count=self._retry_count,
            phases=self._phases,
            tasks=self._tasks,
        ).to_dict()

    @workflow.query
    def state(self) -> dict:
        """Return full engagement state."""
        return {
            "engagement_id": self._engagement_id,
            "description": self._description,
            "status": self._status,
            "phase": self._phase,
            "gate_mode": self._gate_mode,
            "pending_items": self._pending_items,
            "retry_count": self._retry_count,
            "phases": self._phases,
            "tasks": self._tasks,
            "decisions": self._decisions,
            "max_iterations": self._max_iterations,
            "current_iteration": self._current_iteration,
            "pending_feedback": [f.to_dict() for f in self._pending_feedback],
        }
