"""CycleRunner — generic multi-agent iteration engine.

Provides:
- ``CycleRunnerDefinition`` — declarative configuration for a multi-agent loop
- ``CycleStep`` — a single step in the cycle (produce, critique, gate, consult)
- ``CycleConvergence`` — when a cycle terminates
- ``CycleStepResult`` / ``CycleResult`` — per-step and final outputs
- ``CycleRunner`` — the engine that runs a definition

This is the foundation for Phase 0 of Wave 18 (Option G). All multi-agent
loops (critic loops, wave cycles, design↔analyser iterations) should be
expressed as ``CycleRunnerDefinition`` instances and run through this engine.

Usage::

    definition = CycleRunnerDefinition(
        name="arch-loop",
        steps=[
            CycleStep(agent=AGENT_ARCHITECT, step_type=STEP_PRODUCE, artifact=ARTIFACT_DESIGN),
            CycleStep(agent=AGENT_ARCHITECTURE_ANALYSER, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_REVIEW),
            CycleStep(agent=AGENT_ARCHITECT, step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact=ARTIFACT_REQUIREMENTS,
        final_artifact=ARTIFACT_DESIGN,
    )

    runner = CycleRunner(root)
    result = await runner.run(definition, spec_content=spec, engagement_slug=slug)
    if result.status == "complete":
        print(f"Converged in {result.iterations} iteration(s)")
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from harness.agents.backends.base import BackendResult
from harness.agents.context import ContextPacket, OutputContract
from harness.agents.agent_registry import AgentRole
from harness.agents.detectors import (
    BUILD_PYPROJECT_TOML,
    BUILD_PYTEST_INI,
    BUILD_SETUP_CFG,
)

logger = logging.getLogger(__name__)


# ── Constants: artifact names ──────────────────────────────────────────────

# Artifact file names used across cycle definitions.
# These identify step outputs for context passing and convergence checking.
ARTIFACT_DESIGN = "design.md"
ARTIFACT_DESIGN_REVIEW = "design-review.md"
ARTIFACT_REVIEW = "review.md"
ARTIFACT_REQUIREMENTS = "requirements.md"
ARTIFACT_RESEARCH_NOTES = "research-notes.md"
ARTIFACT_PLAN = "plan.md"
ARTIFACT_PLAN_REVIEW = "plan-review.md"
ARTIFACT_IMPLEMENTATION = "implementation.md"
ARTIFACT_TESTING = "testing.md"
ARTIFACT_CONFORMANCE_REVIEW = "conformance-review.md"
ARTIFACT_VALIDATION_REPORT = "validation-report.md"
ARTIFACT_DEAD_CODE_REPORT = "dead-code-report.md"
ARTIFACT_COMPONENT_REPORT = "component-report.md"
ARTIFACT_CRITICAL_REVIEW = "critical-review.md"
ARTIFACT_FINAL_VALIDATION = "final-validation.md"
ARTIFACT_DOMAIN_INTERFACE = "domain-interface.md"

# Agent role strings used in cycle steps.
AGENT_ARCHITECT = "architect"
AGENT_ARCHITECTURE_ANALYSER = "architecture-analyser"
AGENT_REVIEWER = "reviewer"
AGENT_DEAD_CODE = "dead-code-analyser"
AGENT_COMPONENT = "component-analyser"
AGENT_CRITICAL = "critical-analyser"
AGENT_VALIDATION = "validation-agent"
AGENT_COORDINATOR = "coordinator"
AGENT_ARCHITECT_CRITIC = "architect-critic"
AGENT_PLANNER = "planner"
AGENT_CODER = "coder"
AGENT_TESTER = "tester"
AGENT_CONFORMANCE_REVIEWER = "requirements-conformance-reviewer"
AGENT_DOMAIN_TESTER = "domain-interface-tester"
AGENT_SYNC = "sync"

# Step type strings
STEP_PRODUCE = "produce"
STEP_CRITIQUE = "critique"
STEP_GATE = "gate"
STEP_CONSULT = "consult"

# Cycle names
CYCLE_DESIGN_CRITIC = "design-critic"
CYCLE_SELF_TEST = "self-test"
CYCLE_REQUIREMENTS = "requirements"
CYCLE_PLANNING = "planning"
CYCLE_TESTING = "testing-loop"
CYCLE_REVIEW = "review-loop"
CYCLE_DOMAIN_INT = "domain-int-loop"
CYCLE_COORDINATOR = "coordinator"
CYCLE_WAVE = "wave-cycle"

# Convergence settings
CONVERGENCE_AGENT_JUDGMENT = "agent_judgment"
CONVERGENCE_TIMEOUT_BEST_EFFORT = "best_effort"
CONVERGENCE_TIMEOUT_FAIL = "fail"


# ── Step: one action in the cycle ──────────────────────────────────────────


@dataclass
class CycleStep:
    """A single step in a multi-agent iteration cycle.

    Attributes:
        agent: Agent role name (e.g. ``"architect"``, ``"tester"``).
            Must match a registered AgentRole.
        step_type: What this step does.
            - ``"produce"``: Agent creates or updates an artifact.
            - ``"critique"``: Agent reviews the previous step's output.
            - ``"gate"``: Check convergence or pass/fail condition.
              The agent's output is inspected for convergence signals.
            - ``"consult"``: Ask a cross-fleet advisory question.
              Results are recorded but never block iteration.
        artifact: Optional artifact key for this step's output.
            Used for context passing between steps and convergence checking.
        max_retries: Number of retries on agent dispatch failure.
    """
    agent: str
    step_type: str  # "produce" | "critique" | "gate" | "consult"
    artifact: Optional[str] = None
    max_retries: int = 1

    def is_produce(self) -> bool:
        return self.step_type == "produce"

    def is_critique(self) -> bool:
        return self.step_type == "critique"

    def is_gate(self) -> bool:
        return self.step_type == "gate"

    def is_consult(self) -> bool:
        return self.step_type == "consult"


# ── Convergence: when the cycle stops ─────────────────────────────────────


@dataclass
class CycleConvergence:
    """Determines when a multi-agent cycle terminates.

    Attributes:
        condition: How convergence is detected.
            - ``"all_gates_pass"``: All gate steps must indicate pass.
            - ``"no_changes"``: Output hasn't changed between iterations.
            - ``"approval"``: User confirms convergence via callback.
            - ``"agent_judgment"``: The gate step's agent declares done.
            - ``"test_gate"``: Run the project test suite. Converged when
              all tests pass. On failure, test output is injected into
              ``accumulated_artifacts["test_output"]`` for the next
              iteration's agent context.
              The test command is auto-detected from the project root
              (pytest, npm test, cargo test, go test, make test, etc.)
              or can be overridden via ``test_command``.
        max_iterations: Hard cap on loop iterations before timeout.
        on_timeout: What happens when max_iterations is reached.
            - ``"best_effort"``: Return whatever we have (status "timeout").
            - ""fail"": The cycle fails with status "error".
        test_command: Explicit test command override for the
            ``"test_gate"`` convergence strategy. If empty (default),
            the command is auto-detected from the project root.
            Examples: ``"npm test"``, ``"cargo test"``, ``"go test ./..."``,
            ``"make test"``, ``"python -m pytest"``.
    """
    condition: str = "all_gates_pass"  # all_gates_pass | no_changes | approval | agent_judgment | test_gate
    max_iterations: int = 3
    on_timeout: str = "best_effort"  # best_effort | fail
    test_command: str = ""
    """Explicit test command override. Auto-detected when empty."""

    def reached_timeout(self, iteration: int) -> bool:
        """Check if the current iteration exceeds the maximum."""
        return iteration >= self.max_iterations


# ── Definition: the full cycle blueprint ────────────────────────────────────


@dataclass
class CycleRunnerDefinition:
    """Blueprint for a multi-agent iteration cycle.

    Attributes:
        name: Unique identifier (e.g. "arch-loop", "wave", "design-loop").
        steps: Ordered list of steps in one full iteration.
        convergence: When the cycle terminates.
        initial_phase_artifact: Comma-separated artifact keys from the
            engagement that form the initial context fed to the first step.
            Can be empty if no initial context is needed.
        final_artifact: Artifact key that the cycle produces as its
            output. Set to ``""`` if the cycle does not produce a single
            output artifact.
    """
    name: str
    steps: list[CycleStep]
    convergence: CycleConvergence = field(default_factory=CycleConvergence)
    initial_phase_artifact: str = ""
    final_artifact: str = ""


# ── Step and iteration results ─────────────────────────────────────────────


@dataclass
class CycleStepResult:
    """Result of a single step in a cycle iteration.

    Attributes:
        agent: The agent role dispatched.
        step_type: The type of step that ran.
        artifact: The artifact key (if any).
        artifacts: All artifacts produced by the agent run.
        status: ``"success"``, ``"failure"``, or ``"skipped"``.
        error: Error message on failure.
        iteration: Which iteration this step belonged to.
    """
    agent: str
    step_type: str
    artifact: Optional[str]
    artifacts: dict[str, str] = field(default_factory=dict)
    status: str = "success"
    error: Optional[str] = None
    iteration: int = 0


@dataclass
class CycleResult:
    """Final result of running a full cycle.

    Attributes:
        status: How the cycle ended.
            - ``"complete"``: Normal completion (convergence reached).
            - ``"timeout"``: Max iterations hit without convergence.
            - ``"error"``: Fatal error during execution.
            - ``"phase_jump:<phase_name>"``: Cycle requests a phase
              transition (e.g. ``"phase_jump:design"``).
        artifacts: The final output artifacts map (artifact_key → content).
        step_results: All step results across all iterations.
        iterations: Number of iterations executed.
        summary: Human-readable summary of what happened.
        error: Optional error message.
    """
    status: str = "complete"
    artifacts: dict[str, str] = field(default_factory=dict)
    step_results: list[CycleStepResult] = field(default_factory=list)
    iterations: int = 0
    summary: str = ""
    error: Optional[str] = None

    @property
    def is_phase_jump(self) -> bool:
        return self.status is not None and self.status.startswith("phase_jump:")

    @property
    def jump_target(self) -> Optional[str]:
        if self.is_phase_jump:
            return self.status[len("phase_jump:"):]
        return None


# ── Built-in cycle definitions ──────────────────────────────────────────────


def design_cycle_definition() -> CycleRunnerDefinition:
    """Built-in architect ↔ architecture-analyser loop.

    The architect produces a design, the architecture-analyser critiques
    it, and the architect gates (accepts or requests changes). Loops up
    to 3 iterations or until the architect signals convergence.
    """
    return CycleRunnerDefinition(
        name="arch-loop",
        steps=[
            CycleStep(agent=AGENT_ARCHITECT, step_type=STEP_PRODUCE, artifact=ARTIFACT_DESIGN),
            CycleStep(agent=AGENT_ARCHITECTURE_ANALYSER, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_DESIGN_REVIEW),
            CycleStep(agent=AGENT_ARCHITECT, step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact="requirements.md, research.md",
        final_artifact=ARTIFACT_DESIGN,
    )


def discovery_cycle_definition() -> CycleRunnerDefinition:
    """Built-in requirements-builder ↔ researcher loop.

    The requirements-builder scopes the work, the researcher investigates,
    and they iterate until requirements are complete.
    """
    return CycleRunnerDefinition(
        name="discovery-loop",
        steps=[
            CycleStep(agent="requirements-builder", step_type=STEP_PRODUCE,
                      artifact=ARTIFACT_REQUIREMENTS),
            CycleStep(agent="researcher", step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_RESEARCH_NOTES),
            CycleStep(agent="requirements-builder", step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact="",
        final_artifact=ARTIFACT_REQUIREMENTS,
    )


def wave_cycle_definition() -> CycleRunnerDefinition:
    """Built-in wave cycle with implement→test→consult→review→fix→gate.

    Includes an advisory consult step to the architecture fleet (checks
    architectural soundness during implementation) and a review step before
    final gate. Consultations in cycles are always advisory (design rule 5).

    Full step sequence:
        1. coder PRODUCE — implement the wave
        2. tester CRITIQUE — write and run tests
        3. architect CONSULT — advisory architecture check
        4. reviewer CRITIQUE — code review
        5. coder PRODUCE — fix from review feedback
        6. tester GATE — verify all tests pass
    """
    return CycleRunnerDefinition(
        name="wave",
        steps=[
            CycleStep(agent=AGENT_CODER, step_type=STEP_PRODUCE, artifact="code"),
            CycleStep(agent=AGENT_TESTER, step_type=STEP_CRITIQUE, artifact="test-results"),
            CycleStep(agent=AGENT_ARCHITECT, step_type=STEP_CONSULT,
                      artifact="consultation"),
            CycleStep(agent=AGENT_REVIEWER, step_type=STEP_CRITIQUE, artifact="review"),
            CycleStep(agent=AGENT_CODER, step_type=STEP_PRODUCE, artifact="final"),
            CycleStep(agent=AGENT_TESTER, step_type=STEP_GATE, artifact="test-results"),
        ],
        convergence=CycleConvergence(
            condition="all_gates_pass",
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_FAIL,
        ),
        initial_phase_artifact=ARTIFACT_PLAN,
        final_artifact=ARTIFACT_IMPLEMENTATION,
    )


def testing_cycle_definition() -> CycleRunnerDefinition:
    """Built-in tester ↔ conformance reviewer ↔ validation loop.

    The tester produces test scenarios and results, the requirements
    conformance reviewer checks that tests cover every acceptance
    criterion, the validation agent verifies completeness, and the
    tester gates (accepts or requests changes). Loops up to 3
    iterations or until convergence.

    Step sequence:
        1. tester PRODUCE — write and run tests
        2. conformance reviewer CRITIQUE — check AC coverage
        3. validation-agent CRITIQUE — verify completeness
        4. tester GATE — accept or iterate
    """
    return CycleRunnerDefinition(
        name=CYCLE_TESTING,
        steps=[
            CycleStep(agent=AGENT_TESTER, step_type=STEP_PRODUCE, artifact=ARTIFACT_TESTING),
            CycleStep(agent=AGENT_CONFORMANCE_REVIEWER, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_CONFORMANCE_REVIEW),
            CycleStep(agent=AGENT_VALIDATION, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_VALIDATION_REPORT),
            CycleStep(agent=AGENT_TESTER, step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact=ARTIFACT_IMPLEMENTATION,
        final_artifact=ARTIFACT_TESTING,
    )


def review_cycle_definition() -> CycleRunnerDefinition:
    """Built-in multi-agent review loop.

    The reviewer produces a quality assessment, the dead-code analyser
    finds unused code, the component analyser evaluates interface
    granularity, the critical analyser does a holistic pass, and the
    validation agent checks acceptance criteria. The reviewer gates
    (accepts or requests changes). Loops up to 3 iterations.

    Step sequence:
        1. reviewer PRODUCE — quality assessment
        2. dead-code-analyser CRITIQUE — dead code findings
        3. component-analyser CRITIQUE — component health findings
        4. critical-analyser CRITIQUE — holistic findings
        5. validation-agent CRITIQUE — acceptance criteria check
        6. reviewer GATE — accept or iterate
    """
    return CycleRunnerDefinition(
        name=CYCLE_REVIEW,
        steps=[
            CycleStep(agent=AGENT_REVIEWER, step_type=STEP_PRODUCE, artifact=ARTIFACT_REVIEW),
            CycleStep(agent=AGENT_DEAD_CODE, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_DEAD_CODE_REPORT),
            CycleStep(agent=AGENT_COMPONENT, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_COMPONENT_REPORT),
            CycleStep(agent=AGENT_CRITICAL, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_CRITICAL_REVIEW),
            CycleStep(agent=AGENT_VALIDATION, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_FINAL_VALIDATION),
            CycleStep(agent=AGENT_REVIEWER, step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact="testing.md, implementation.md",
        final_artifact=ARTIFACT_REVIEW,
    )


def planning_cycle_definition() -> CycleRunnerDefinition:
    """Built-in planning-agent ↔ validation loop.

    The planning agent produces a task breakdown, and the validation agent
    checks that the plan is complete and actionable.
    """
    return CycleRunnerDefinition(
        name="planning-loop",
        steps=[
            CycleStep(agent="planning-agent", step_type=STEP_PRODUCE,
                      artifact=ARTIFACT_PLAN),
            CycleStep(agent=AGENT_VALIDATION, step_type=STEP_CRITIQUE,
                      artifact=ARTIFACT_PLAN_REVIEW),
            CycleStep(agent="planning-agent", step_type=STEP_GATE),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=3,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact="design.md, requirements.md",
        final_artifact=ARTIFACT_PLAN,
    )


def self_test_cycle_definition(
    max_iterations: int = 5,
    task_description: str = "",
    test_command: str = "",
) -> CycleRunnerDefinition:
    """Built-in coding-agent self-test cycle (Wave 19 Phase 1).

    A sub-cycle that wraps the coding step with a write-test-run-fix loop.
    The coding agent:
    1. Produces the implementation
    2. Writes tests for it
    3. Fixes failures until the full test suite passes

    Convergence is driven by ``test_gate``: after each iteration,
    the project's test suite is run (auto-detected from project root
    markers, or via an explicit ``test_command``). If all tests pass,
    the cycle converges. On failure, test output is fed back into the
    agent's context for the next iteration.

    Args:
        max_iterations: Maximum iterations before timeout (default 5).
        task_description: Optional extra task instructions for the
            coding agent (e.g. which file to implement).
        test_command: Explicit test command override. Auto-detected
            from the project root when empty. Examples:
            ``"npm test"``, ``"cargo test"``, ``"go test ./..."``,
            ``"make test"``, ``"python -m pytest"``.

    Returns:
        A ``CycleRunnerDefinition`` configured for self-test.
    """
    spec = (
        "Implement the required code. After writing the initial "
        "implementation, write unit tests. Then run the full test "
        "suite: analyse any failures, fix the code or tests, and "
        "repeat until all tests pass.\n\n"
        f"{task_description}"
    ).strip()

    return CycleRunnerDefinition(
        name="self-test-loop",
        steps=[
            CycleStep(
                agent="coding-agent",
                step_type=STEP_PRODUCE,
                artifact=ARTIFACT_IMPLEMENTATION,
            ),
            CycleStep(
                agent="coding-agent",
                step_type=STEP_PRODUCE,
                artifact="tests.md",
            ),
            CycleStep(
                agent="coding-agent",
                step_type=STEP_GATE,
                artifact="fix-report.md",
            ),
        ],
        convergence=CycleConvergence(
            condition="test_gate",
            max_iterations=max_iterations,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
            test_command=test_command,
        ),
        initial_phase_artifact="",
        final_artifact="",
    )


# ── Built-in definition registry ────────────────────────────────────────────


def domain_interface_cycle_definition() -> CycleRunnerDefinition:
    """Built-in domain interface testing cycle.

    The domain interface tester discovers ABCs and Protocols, generates
    probe tests, runs them, and produces a conformance report. A single
    produce step with the agent running its full pipeline.
    """
    return CycleRunnerDefinition(
        name=CYCLE_DOMAIN_INT,
        steps=[
            CycleStep(agent=AGENT_DOMAIN_TESTER, step_type=STEP_PRODUCE,
                      artifact="domain-interface-report.md"),
        ],
        convergence=CycleConvergence(
            condition=CONVERGENCE_AGENT_JUDGMENT,
            max_iterations=1,
            on_timeout=CONVERGENCE_TIMEOUT_BEST_EFFORT,
        ),
        initial_phase_artifact="implementation.md, design.md",
        final_artifact="domain-interface-report.md",
    )


BUILTIN_CYCLE_DEFINITIONS: dict[str, CycleRunnerDefinition] = {
    "arch-loop": design_cycle_definition(),
    "discovery-loop": discovery_cycle_definition(),
    "wave": wave_cycle_definition(),
    "testing-loop": testing_cycle_definition(),
    "review-loop": review_cycle_definition(),
    "planning-loop": planning_cycle_definition(),
    "self-test-loop": self_test_cycle_definition(),
    "domain-int-loop": domain_interface_cycle_definition(),
}


def get_cycle_definition(name: str) -> CycleRunnerDefinition | None:
    """Look up a built-in cycle definition by name.

    Args:
        name: The cycle definition name (e.g. "arch-loop", "wave").

    Returns:
        The ``CycleRunnerDefinition``, or ``None`` if not found.
    """
    return BUILTIN_CYCLE_DEFINITIONS.get(name)


def list_cycle_definitions() -> list[str]:
    """Return names of all available built-in cycle definitions."""
    return list(BUILTIN_CYCLE_DEFINITIONS.keys())


# ── Phase jump helpers ──────────────────────────────────────────────────────


MAX_PHASE_JUMPS_PER_PHASE = 3
"""Hard limit on how many times a phase can jump back to the same target
in a single session, preventing infinite loops."""


def is_phase_jump_status(status: str) -> bool:
    """Check if a CycleResult status signals a phase jump request."""
    return status is not None and status.startswith("phase_jump:")


def parse_phase_jump_target(status: str) -> str | None:
    """Extract the target phase name from a phase-jump status string.

    Example: ``parse_phase_jump_target("phase_jump:design")`` returns
    ``"design"``.
    """
    if not is_phase_jump_status(status):
        return None
    return status[len("phase_jump:"):]


def format_phase_jump_status(target_phase: str) -> str:
    """Format a phase-jump status string for a CycleResult.

    Example: ``format_phase_jump_status("design")`` returns
    ``"phase_jump:design"``.
    """
    return f"phase_jump:{target_phase}"


# ── The engine ──────────────────────────────────────────────────────────────


class CycleRunner:
    """Generic multi-agent iteration engine.

    Takes a ``CycleRunnerDefinition`` and runs the defined steps in
    iterations, checking convergence after each iteration. Each step
    dispatches to the AgentRunner with a ContextPacket built from the
    accumulated cycle context.

    The engine is **linear-sequential**: exactly one agent runs per step,
    and agents are dispatched one at a time. Multiple agents per phase
    is the norm (each named explicitly in the step list).

    Args:
        root: Optional project root directory for context resolution.
        agent_runner: An optional pre-configured AgentRunner instance.
            If omitted, a new default AgentRunner is created lazily.
    """

    def __init__(
        self,
        root: Path | None = None,
        agent_runner: Any | None = None,
    ) -> None:
        self._root = root
        self._agent_runner = agent_runner  # lazy; can be set externally

    async def run(
        self,
        definition: CycleRunnerDefinition,
        engagement_slug: str = "",
        spec_content: str = "",
        architecture_rules: list[str] | None = None,
        backend_name: str | None = None,
        initial_artifacts: dict[str, str] | None = None,
        on_convergence_check: callable = None,
    ) -> CycleResult:
        """Run a cycle definition.

        Args:
            definition: The cycle blueprint.
            engagement_slug: Current engagement identifier.
            spec_content: The task description / requirements for agents.
            architecture_rules: Optional architecture constraints.
            backend_name: Backend name for agent dispatch (None = default).
            initial_artifacts: Artifacts to seed the cycle context
                (e.g. from previous phases).
            on_convergence_check: Optional callable ``(definition, iteration,
                step_results, artifacts) -> bool`` that overrides the
                default convergence check. Returns True if converged.

        Returns:
            ``CycleResult`` with step results and final artifacts.
        """
        iteration_results: list[CycleStepResult] = []
        accumulated_artifacts: dict[str, str] = dict(initial_artifacts or {})

        for iteration in range(definition.convergence.max_iterations):
            iteration_step_results: list[CycleStepResult] = []
            logger.info(
                "Cycle '%s' iteration %d/%d",
                definition.name,
                iteration + 1,
                definition.convergence.max_iterations,
            )

            for step in definition.steps:
                step_result = await self._run_step(
                    step=step,
                    definition=definition,
                    engagement_slug=engagement_slug,
                    spec_content=spec_content,
                    architecture_rules=architecture_rules or [],
                    accumulated_artifacts=accumulated_artifacts,
                    backend_name=backend_name,
                    iteration=iteration,
                )
                iteration_step_results.append(step_result)

                # Accumulate step outputs
                if step_result.status == "success" and step.artifact:
                    accumulated_artifacts[step.artifact] = (
                        "\n\n".join(step_result.artifacts.values())
                        if step_result.artifacts
                        else ""
                    )

                # Check for fatal error (not timeout, not convergence fail)
                if step_result.status == "failure" and not step.is_consult():
                    total_results = iteration_results + iteration_step_results
                    return CycleResult(
                        status="error",
                        artifacts=accumulated_artifacts,
                        step_results=total_results,
                        iterations=iteration + 1,
                        error=step_result.error or f"Step '{step.agent}:{step.step_type}' failed",
                    )

            # Collect results for this iteration
            iteration_results.extend(iteration_step_results)

            # Check convergence
            converged = False
            if on_convergence_check is not None:
                converged = on_convergence_check(
                    definition, iteration, iteration_step_results, accumulated_artifacts
                )
            else:
                converged = self._check_convergence(
                    definition, iteration_step_results, accumulated_artifacts
                )

            if converged:
                logger.info(
                    "Cycle '%s' converged after %d iteration(s)",
                    definition.name,
                    iteration + 1,
                )
                return CycleResult(
                    status="complete",
                    artifacts=accumulated_artifacts,
                    step_results=iteration_results,
                    iterations=iteration + 1,
                    summary=f"Converged after {iteration + 1} iteration(s)",
                )

        # Max iterations reached without convergence
        logger.warning(
            "Cycle '%s' hit max iterations (%d)",
            definition.name,
            definition.convergence.max_iterations,
        )
        timeout_status = (
            "error" if definition.convergence.on_timeout == "fail" else "timeout"
        )
        return CycleResult(
            status=timeout_status,
            artifacts=accumulated_artifacts,
            step_results=iteration_results,
            iterations=definition.convergence.max_iterations,
            summary=(
                f"Max iterations ({definition.convergence.max_iterations}) "
                f"reached without convergence"
            ),
        )

    async def _run_step(
        self,
        step: CycleStep,
        definition: CycleRunnerDefinition,
        engagement_slug: str,
        spec_content: str,
        architecture_rules: list[str],
        accumulated_artifacts: dict[str, str],
        backend_name: str | None,
        iteration: int,
    ) -> CycleStepResult:
        """Run a single step, dispatching the agent and collecting output."""
        attempt = 0
        last_error: str | None = None

        while attempt <= step.max_retries:
            # Build context
            previous_context = _format_artifacts_for_context(accumulated_artifacts)

            phase_name = f"{definition.name}-iteration-{iteration}"
            task_id = f"{step.agent}-{definition.name}-i{iteration}"

            if step.is_consult():
                # Consult steps: question from context, advisory only
                spec = (
                    f"# Consultation Request for: {definition.name}\n\n"
                    f"## Context\n{previous_context}\n\n"
                    f"## Question\n{spec_content}\n\n"
                    "Respond with an assessment. Your response is advisory only."
                )
            elif step.is_gate():
                # Gate steps: assess current state against criteria
                spec = (
                    f"# Gate Check for: {definition.name}\n\n"
                    f"## Current State\n{previous_context}\n\n"
                    "## Instructions\n"
                    "Assess whether the current state is complete and acceptable. "
                    "If it is, respond with a message containing:\n"
                    "'CONVERGED' or 'converged' or 'no new issues' or 'design approved'\n\n"
                    "If changes are still needed, explain what needs to change."
                )
            elif step.is_critique():
                # Critique steps: review the previous step's output
                spec = (
                    f"# Review for: {definition.name}\n\n"
                    f"## Context\n{previous_context}\n\n"
                    f"## Spec\n{spec_content}\n\n"
                    "## Instructions\n"
                    "Review the latest output. Identify issues, gaps, and "
                    "improvements. Your review will feed into the next iteration."
                )
            else:
                # Produce steps: create or update an artifact
                spec = (
                    f"# Task: {definition.name}\n\n"
                    f"## Spec\n{spec_content}\n\n"
                    f"## Architecture Rules\n"
                    f"{chr(10).join(architecture_rules)}\n\n"
                    f"## Previous Context\n{previous_context}\n\n"
                    "## Instructions\n"
                    "Produce the required output based on the spec, architecture "
                    "rules, and previous context. Write complete, well-structured "
                    "output."
                )

            packet = ContextPacket(
                engagement_id=engagement_slug or "_cycle",
                phase_name=phase_name,
                task_id=task_id,
                spec_content=spec,
                architecture_rules=architecture_rules,
                target_directory=(
                    Path(self._root) if self._root else None
                ),
                output_contract=OutputContract(),
                constraint_section={
                    "agent_role": step.agent,
                    "backend": backend_name or "",
                },
            )

            # Run the agent (lazy import to avoid circular dependency)
            try:
                runner = self._agent_runner
                if runner is None:
                    from harness.agents.runner import AgentRunner
                    runner = AgentRunner()
                    self._agent_runner = runner
                result: BackendResult = await runner.run(
                    packet, backend_name=backend_name or None,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Step %s (agent=%s) attempt %d failed: %s",
                    definition.name, step.agent, attempt + 1, last_error,
                )
                attempt += 1
                continue

            if result.status == "success":
                return CycleStepResult(
                    agent=step.agent,
                    step_type=step.step_type,
                    artifact=step.artifact,
                    artifacts=result.artifacts,
                    status="success",
                    iteration=iteration,
                )
            else:
                last_error = result.errors[0] if result.errors else "Unknown error"
                logger.warning(
                    "Step %s (agent=%s) attempt %d returned '%s': %s",
                    definition.name, step.agent, attempt + 1,
                    result.status, last_error,
                )
                attempt += 1
                continue

        # All retries exhausted
        return CycleStepResult(
            agent=step.agent,
            step_type=step.step_type,
            artifact=step.artifact,
            status="failure",
            error=last_error or f"Step failed after {step.max_retries + 1} attempt(s)",
            iteration=iteration,
        )

    def _check_convergence(
        self,
        definition: CycleRunnerDefinition,
        step_results: list[CycleStepResult],
        artifacts: dict[str, str],
    ) -> bool:
        """Default convergence check based on definition configuration.

        Applies the configured ``condition``:
        - ``"agent_judgment"``: Inspect gate step outputs for convergence keywords.
        - ``"all_gates_pass"``: All gate steps must have output indicating pass.
        - ``"no_changes"``: Compare latest produce output against previous.
        - ``"approval"``: Not supported in default check (return False).
        - ``"test_gate"``: Run the project test suite. Converged when
          all tests pass. Test output injected into ``artifacts["test_output"]``.
        """
        condition = definition.convergence.condition

        if condition == "all_gates_pass":
            return self._check_all_gates_passing(step_results)

        if condition == "agent_judgment":
            return self._check_agent_judgment(step_results)

        if condition == "no_changes":
            return self._check_no_changes(step_results, artifacts)

        if condition == "test_gate":
            return self._check_test_gate(definition, artifacts)

        if condition == "approval":
            # External approval — default never converges without callback
            return False

        return False

    def _check_all_gates_passing(self, step_results: list[CycleStepResult]) -> bool:
        """Check that all gate steps produced non-empty output content."""
        gate_results = [r for r in step_results if r.step_type == "gate"]
        if not gate_results:
            return False
        return all(
            r.status == "success"
            and bool(r.artifacts)
            and any(v.strip() for v in r.artifacts.values())
            for r in gate_results
        )

    def _check_agent_judgment(self, step_results: list[CycleStepResult]) -> bool:
        """Check if any gate step's output contains convergence keywords."""
        keywords = ["converged", "convergence", "no new issues",
                     "design approved", "no issues found"]
        for result in step_results:
            if result.step_type not in ("gate", "critique"):
                continue
            if result.status != "success":
                continue
            text = " ".join(result.artifacts.values()).lower()
            if any(kw.lower() in text for kw in keywords):
                return True
        return False

    def _check_no_changes(
        self,
        step_results: list[CycleStepResult],
        artifacts: dict[str, str],
    ) -> bool:
        """Check if produce outputs haven't changed since the last iteration.

        Note: This is best-effort — if we don't have enough history, we
        report not-converged. The caller must call this function consistently
        each iteration for proper tracking.
        """
        produce_results = [r for r in step_results if r.step_type == "produce"]
        if not produce_results:
            return False

        # Check each produce step: if its artifact key value matches the
        # previous iteration's value, it hasn't changed.
        for pr in produce_results:
            if not pr.artifact:
                continue
            prev = artifacts.get(f"_{pr.artifact}_prev", "")
            current = artifacts.get(pr.artifact, "")
            if prev and current and prev.strip() == current.strip():
                continue  # No change — this is fine
            elif prev and current:
                return False  # Changed — not converged
            else:
                # First iteration — track for next time
                # Store prev via mutation on artifacts dict (prefix-keys)
                artifacts[f"_{pr.artifact}_prev"] = current
                return False  # No history to compare yet

        # All produce steps unchanged — converged
        return len(produce_results) > 0

    def _check_test_gate(
        self,
        definition: CycleRunnerDefinition,
        artifacts: dict[str, str],
    ) -> bool:
        """Run the project test suite (language-agnostic).

        If all tests pass, the cycle is converged. On failure, the
        test output is injected into ``artifacts["test_output"]`` so
        the next iteration's agent can analyse and fix the failures.

        The test command is resolved in this order:

        1. ``definition.convergence.test_command`` (explicit override)
        2. Auto-detected from project root markers
           (see :meth:`_detect_test_command`)

        The project root is determined from ``self._root`` or, if that
        is not set, by walking up from the current directory to find
        a ``.git`` marker.

        If the test runner is not found or fails with a non-exit-code
        error, the method reports not-converged and stores the error in
        ``artifacts["test_output"]``.
        """
        repo_root = self._resolve_project_root()

        # Resolve the test command
        explicit = (definition.convergence.test_command or "").strip()
        if explicit:
            command = shlex.split(explicit)
        else:
            detected = self._detect_test_command(repo_root)
            if detected is None:
                msg = (
                    "Could not auto-detect test runner for this project. "
                    "Set test_command explicitly on CycleConvergence "
                    "(e.g. 'npm test', 'cargo test', 'go test ./...')."
                )
                artifacts["test_output"] = msg
                logger.warning(msg)
                return False
            command = detected

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(repo_root) if repo_root else None,
            )
            test_output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            test_output = "Test suite timed out (120s)."
            artifacts["test_output"] = test_output
            return False
        except FileNotFoundError as exc:
            test_output = f"Test runner not found: {exc}"
            artifacts["test_output"] = test_output
            return False
        except Exception as exc:
            test_output = f"Test runner error: {exc}"
            artifacts["test_output"] = test_output
            return False

        artifacts["test_output"] = test_output

        if result.returncode == 0:
            logger.info(
                "test_gate: all tests passed (exit %d)",
                result.returncode,
            )
            return True

        logger.info(
            "test_gate: exit %d, %.1fkb output injected",
            result.returncode,
            len(test_output) / 1024,
        )
        return False

    @staticmethod
    def _detect_test_command(repo_root: Path | None) -> list[str] | None:
        """Auto-detect the test command from project root markers.

        Checks for language/framework-specific files and returns an
        appropriate shell command list. Returns ``None`` if no known
        test runner is detected.

        Current detectors:
        - pytest (Python): ``pytest.ini``, ``pyproject.toml`` with
          ``[tool.pytest]``, or ``setup.cfg`` with ``[tool:pytest]``
        - npm/yarn: ``package.json`` with a ``"test"`` script
        - Cargo (Rust): ``Cargo.toml``
        - Go: ``go.mod``
        - Make: ``Makefile`` or ``makefile`` with a ``test:`` target
        - Gradle: ``build.gradle`` or ``build.gradle.kts``
        - Maven: ``pom.xml``
        - Just: ``justfile`` with a ``test`` recipe
        - Rake: ``Rakefile``
        - CTest: ``CMakeLists.txt`` (assumes build dir is ``build/``)
        """
        if repo_root is None:
            return None

        import os

        files = {}
        try:
            for entry in os.listdir(str(repo_root)):
                files[entry.lower()] = entry
        except PermissionError:
            return None

        # Python: pytest
        if BUILD_PYTEST_INI in files or BUILD_SETUP_CFG in files:
            return [sys.executable, "-m", "pytest", "-q", "--tb=short"]
        if BUILD_PYPROJECT_TOML in files:
            pyproject_path = repo_root / BUILD_PYPROJECT_TOML
            try:
                content = pyproject_path.read_text()
                if "[tool.pytest_ini_options]" in content or "[tool.pytest]" in content:
                    return [sys.executable, "-m", "pytest", "-q", "--tb=short"]
            except (OSError, UnicodeDecodeError):
                pass

        # Node.js: npm test / yarn test
        if "package.json" in files:
            pkg_path = repo_root / files["package.json"]
            try:
                import json
                pkg = json.loads(pkg_path.read_text())
                if "scripts" in pkg and "test" in pkg["scripts"]:
                    # Prefer yarn if yarn.lock exists, else npm
                    if "yarn.lock" in files:
                        return ["yarn", "test"]
                    return ["npm", "test"]
            except (OSError, json.JSONDecodeError):
                pass

        # Rust: cargo test
        if "cargo.toml" in files:
            return ["cargo", "test"]

        # Go: go test
        if "go.mod" in files:
            return ["go", "test", "./..."]

        # Make: make test
        if "makefile" in files or "gnumakefile" in files:
            _mk = files.get("makefile") or files.get("gnumakefile")
            if _mk:
                try:
                    mk_content = (repo_root / _mk).read_text()
                    if "test:" in mk_content or "check:" in mk_content:
                        return ["make", "test"]
                except (OSError, UnicodeDecodeError):
                    pass

        # Gradle
        if "build.gradle" in files or "build.gradle.kts" in files:
            return ["./gradlew", "test"] if "gradlew" in files else ["gradle", "test"]

        # Maven
        if "pom.xml" in files:
            return ["./mvnw", "test"] if "mvnw" in files else ["mvn", "test"]

        # Just: just test
        if "justfile" in files:
            # Check if it has a test recipe (best-effort)
            try:
                jf_content = (repo_root / files["justfile"]).read_text()
                if "test:" in jf_content:
                    return ["just", "test"]
            except (OSError, UnicodeDecodeError):
                pass

        # Rake
        if "rakefile" in files:
            return ["rake", "test"]

        # CMake / CTest
        if "cmakelists.txt" in files:
            return ["ctest", "--test-dir", "build"]

        return None

    def _resolve_project_root(self) -> Path | None:
        """Resolve the project root, walking up to find .git."""
        start = self._root or Path.cwd()
        try:
            resolved = start.resolve()
        except Exception:
            resolved = Path.cwd()
        for parent in [resolved] + list(resolved.parents):
            if (parent / ".git").exists():
                return parent
        return resolved


# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_artifacts_for_context(artifacts: dict[str, str]) -> str:
    """Format accumulated artifacts as a context string for the agent."""
    if not artifacts:
        return ""

    parts = []
    for key, value in artifacts.items():
        if key.startswith("_"):
            continue  # Skip internal tracking keys
        content = value[:2000] if value else ""
        parts.append(f"--- {key} ---\n{content}")

    return "\n\n".join(parts)
