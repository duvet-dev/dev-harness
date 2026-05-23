"""Refactoring session orchestrator — phase sequence and loop.

Provides:
- ``RefactorPhase`` — enum of valid refactoring phases
- ``validate_transition()`` — ensure phase transitions are valid
- ``RefactorSessionConfig`` — configuration for a refactoring session
- ``RefactorSessionState`` — mutable state tracking
- ``RefactorSessionResult`` — result after completion
- ``RefactorSessionLoop`` — top-level orchestrator
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

# ── Phase definitions ──────────────────────────────────────────────────────


class RefactorPhase(str, enum.Enum):
    """Phases in a refactoring session, in execution order.

    The intent is sequential: each phase depends on the output of
    the previous one. ``VERIFICATION`` may loop back to ``INTENT_DISCOVERY``
    if issues are found.
    """

    INTENT_DISCOVERY = "intent-discovery"
    ARCHITECTURE_PROPOSAL = "architecture-proposal"
    MIGRATION_ASSESSMENT = "migration-assessment"
    BOUNDARY_TEST_GENERATION = "boundary-test-generation"
    WAVE_EXECUTION = "wave-execution"
    VERIFICATION = "verification"
    SUMMARY = "summary"

    def __str__(self) -> str:
        return self.value


# ── Human-readable labels ──────────────────────────────────────────────────

REFACTOR_PHASE_LABELS: Dict[RefactorPhase, str] = {
    RefactorPhase.INTENT_DISCOVERY: "Intent Discovery",
    RefactorPhase.ARCHITECTURE_PROPOSAL: "Architecture Proposal",
    RefactorPhase.MIGRATION_ASSESSMENT: "Migration Assessment",
    RefactorPhase.BOUNDARY_TEST_GENERATION: "Boundary Test Generation",
    RefactorPhase.WAVE_EXECUTION: "Wave Execution",
    RefactorPhase.VERIFICATION: "Verification",
    RefactorPhase.SUMMARY: "Summary",
}

REFACTOR_PHASE_ORDER: List[RefactorPhase] = [
    RefactorPhase.INTENT_DISCOVERY,
    RefactorPhase.ARCHITECTURE_PROPOSAL,
    RefactorPhase.MIGRATION_ASSESSMENT,
    RefactorPhase.BOUNDARY_TEST_GENERATION,
    RefactorPhase.WAVE_EXECUTION,
    RefactorPhase.VERIFICATION,
    RefactorPhase.SUMMARY,
]


# ── Phase transition rules ─────────────────────────────────────────────────

_VALID_TRANSITIONS: Dict[RefactorPhase, Set[RefactorPhase]] = {
    RefactorPhase.INTENT_DISCOVERY: {RefactorPhase.ARCHITECTURE_PROPOSAL},
    RefactorPhase.ARCHITECTURE_PROPOSAL: {RefactorPhase.MIGRATION_ASSESSMENT},
    RefactorPhase.MIGRATION_ASSESSMENT: {RefactorPhase.BOUNDARY_TEST_GENERATION},
    RefactorPhase.BOUNDARY_TEST_GENERATION: {RefactorPhase.WAVE_EXECUTION},
    RefactorPhase.WAVE_EXECUTION: {RefactorPhase.VERIFICATION},
    RefactorPhase.VERIFICATION: {
        RefactorPhase.SUMMARY,
        RefactorPhase.INTENT_DISCOVERY,  # loop back if issues found
    },
    RefactorPhase.SUMMARY: set(),  # terminal phase
}


def validate_transition(current: RefactorPhase, next_phase: RefactorPhase) -> bool:
    """Check whether moving from *current* to *next_phase* is valid.

    Returns True if the transition is defined in ``_VALID_TRANSITIONS``,
    False otherwise.
    """
    allowed = _VALID_TRANSITIONS.get(current, set())
    return next_phase in allowed


# ── Config ─────────────────────────────────────────────────────────────────


@dataclass
class RefactorSessionConfig:
    """Configuration for a refactoring session.

    Attributes:
        root: Project root directory.
        engagement_slug: Slug identifying this engagement.
        context_tier: Context bundle tier (1-3).
        auto_confirm_boundaries: If True, skip user confirmation for
            automatically detected boundaries.
        max_verification_loops: Maximum number of times to loop back
            from verification to intent discovery.
    """
    root: Path
    engagement_slug: str
    context_tier: int = 2
    auto_confirm_boundaries: bool = False
    max_verification_loops: int = 3


# ── State ──────────────────────────────────────────────────────────────────


@dataclass
class RefactorSessionState:
    """Mutable state tracked through a refactoring engagement.

    Tracks which phases have been completed, what artifacts have been
    accumulated, and verification loop count.
    """
    current_phase: RefactorPhase = RefactorPhase.INTENT_DISCOVERY
    completed_phases: Set[RefactorPhase] = field(default_factory=set)
    artifacts: Dict[str, str] = field(default_factory=dict)
    verification_loop_count: int = 0
    start_time: float = 0.0

    def mark_completed(self, phase: RefactorPhase) -> None:
        """Record *phase* as completed."""
        self.completed_phases.add(phase)

    def record_artifact(self, phase: RefactorPhase, content: str) -> None:
        """Save the output artifact for a phase."""
        self.artifacts[phase.value] = content

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since the session started."""
        if self.start_time == 0.0:
            return 0.0
        return time.time() - self.start_time


# ── Result ─────────────────────────────────────────────────────────────────


@dataclass
class RefactorSessionResult:
    """Result of a completed refactoring session.

    Attributes:
        success: True if all phases completed without failure.
        completed_phases: Names of phases that were completed.
        boundary_test_count: Number of boundary tests generated.
        verification_passed: True if the verification pass succeeded.
        loop_count: Number of verification→intent-discovery loops.
        elapsed_seconds: Total wall-clock time.
        errors: Any error messages captured during execution.
        summary: The final summary content (if summary phase ran).
    """
    success: bool = False
    completed_phases: List[str] = field(default_factory=list)
    boundary_test_count: int = 0
    verification_passed: bool = False
    loop_count: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    summary: str = ""


# ── Phase prompts ──────────────────────────────────────────────────────────


PHASE_PROMPTS: Dict[RefactorPhase, str] = {
    RefactorPhase.INTENT_DISCOVERY: (
        "You are in the INTENT DISCOVERY phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Understand the project's purpose and current structure\n"
        "- Ask the user clarifying questions to validate your understanding\n"
        "- Document the current state of the project (architecture, key "
        "components, data flow)\n"
        "- Identify the user's refactoring goals: what do they want to improve?\n\n"
        "YOUR BOUNDARIES:\n"
        "- Do NOT propose specific architecture changes yet\n"
        "- Do NOT write any code\n"
        "- Focus on understanding, not designing\n\n"
        "OUTPUT:\n"
        "Write a current-state analysis to the engagement directory "
        "using the RepoTool."
    ),
    RefactorPhase.ARCHITECTURE_PROPOSAL: (
        "You are in the ARCHITECTURE PROPOSAL phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Based on the intent discovery output, design an ideal target architecture\n"
        "- Follow hexagonal/clean architecture principles\n"
        "- Identify anti-corruption layers between bounded contexts\n"
        "- Design adapter interfaces that isolate domain from infrastructure\n"
        "- Include migration states: current → intermediate → target\n\n"
        "YOUR BOUNDARIES:\n"
        "- Do NOT implement code\n"
        "- Do NOT assess migration effort (that's the next phase)\n\n"
        "OUTPUT:\n"
        "Write architecture proposal documents using the RepoTool."
    ),
    RefactorPhase.MIGRATION_ASSESSMENT: (
        "You are in the MIGRATION ASSESSMENT phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Evaluate the effort required to move from current to target architecture\n"
        "- Decompose the work into waves (independently buildable chunks)\n"
        "- Estimate effort per wave\n"
        "- Identify high-risk waves that benefit from early boundary tests\n"
        "- Flag dependencies and sequencing constraints\n"
        "- Get user feedback on scope and priorities\n\n"
        "YOUR BOUNDARIES:\n"
        "- Do NOT implement code\n"
        "- Do NOT start any work — assess first\n\n"
        "OUTPUT:\n"
        "Write a migration plan document using the RepoTool."
    ),
    RefactorPhase.BOUNDARY_TEST_GENERATION: (
        "You are in the BOUNDARY TEST GENERATION phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Review the identified application boundaries\n"
        "- Confirm each boundary with the user\n"
        "- Generate IMMUTABLE behaviour-capturing tests at each boundary\n"
        "- These tests will act as guard rails for the refactoring\n"
        "- Register boundaries in the project configuration\n\n"
        "YOUR BOUNDARIES:\n"
        "- Do NOT implement any refactoring code\n"
        "- Do NOT modify existing tests\n"
        "- Boundary tests must be marked IMMUTABLE\n\n"
        "OUTPUT:\n"
        "Use the RepoTool to write boundary test files to tests/boundaries/."
    ),
    RefactorPhase.WAVE_EXECUTION: (
        "You are in the WAVE EXECUTION phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Execute each wave from the migration plan\n"
        "- For each wave: understand intent → implement → run boundary tests\n"
        "- If a boundary test fails, the implementation changed behaviour — revert\n"
        "- Keep changes focused: one wave at a time\n"
        "- Commit after each wave with descriptive messages\n\n"
        "YOUR BOUNDARIES:\n"
        "- Do NOT modify boundary test files (they are IMMUTABLE)\n"
        "- Do NOT merge waves — they are sequential\n"
        "- If a wave can't pass boundary tests, flag it, don't force it\n\n"
        "OUTPUT:\n"
        "Implement each wave using the RepoTool. Write progress to the "
        "engagement directory."
    ),
    RefactorPhase.VERIFICATION: (
        "You are in the VERIFICATION phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Run the full test suite\n"
        "- Verify boundary test integrity (not modified during refactoring)\n"
        "- Scan for architecture compliance against the target\n"
        "- Compare debt levels before and after refactoring\n"
        "- If issues found, prepare feedback to restart intent discovery\n\n"
        "Your assessment determines whether the session continues or wraps up.\n\n"
        "OUTPUT:\n"
        "Write a verification report using the RepoTool."
    ),
    RefactorPhase.SUMMARY: (
        "You are in the SUMMARY phase of a refactoring engagement.\n\n"
        "YOUR JOB:\n"
        "- Summarise what was accomplished across all phases\n"
        "- List new boundary tests and their integrity status\n"
        "- Document any architecture debt that remains\n"
        "- Suggest next steps (future refactoring engagements, cleanup)\n"
        "- Celebrate what went well\n\n"
        "OUTPUT:\n"
        "Write a final engagement summary using the RepoTool."
    ),
}


# ── RefactorSessionLoop ────────────────────────────────────────────────────


class RefactorSessionLoop:
    """Top-level orchestrator for refactoring sessions.

    Manages the phase sequence from intent discovery through summary,
    including optional feedback loops when verification finds issues.

    Usage::

        config = RefactorSessionConfig(root=root, engagement_slug="my-eng")
        loop = RefactorSessionLoop(config)
        result = await loop.run()
    """

    def __init__(self, config: RefactorSessionConfig) -> None:
        self.config = config
        self.state = RefactorSessionState(start_time=time.time())

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def current_phase(self) -> RefactorPhase:
        """The currently active phase."""
        return self.state.current_phase

    @current_phase.setter
    def current_phase(self, phase: RefactorPhase) -> None:
        self.state.current_phase = phase

    def get_phase_prompt(self, phase: Optional[RefactorPhase] = None) -> str:
        """Get the system prompt for *phase* (or the current phase).

        Returns the prompt text, or a fallback if the phase has no
        specialised prompt.
        """
        target = phase or self.state.current_phase
        return PHASE_PROMPTS.get(
            target,
            f"You are in the {target.value} phase of a refactoring engagement.",
        )

    def get_next_phase(self) -> Optional[RefactorPhase]:
        """Get the next phase in the standard sequence.

        Returns None if the current phase is the terminal SUMMARY phase.
        """
        current_idx = REFACTOR_PHASE_ORDER.index(self.state.current_phase)
        if current_idx + 1 >= len(REFACTOR_PHASE_ORDER):
            return None
        return REFACTOR_PHASE_ORDER[current_idx + 1]

    def can_advance(self) -> bool:
        """Check if we can advance from the current phase."""
        next_phase = self.get_next_phase()
        if next_phase is None:
            return False
        return validate_transition(self.state.current_phase, next_phase)

    def advance(self) -> Optional[RefactorPhase]:
        """Advance to the next phase in the standard sequence.

        Marks the current phase as completed, then moves to the next.

        Returns the new phase, or None if already at the final phase.
        """
        self.state.mark_completed(self.state.current_phase)
        next_phase = self.get_next_phase()
        if next_phase is None:
            return None
        self.state.current_phase = next_phase
        return next_phase

    def loop_back_to_intent(self) -> bool:
        """Loop back from verification to intent discovery.

        Returns True if the loop was performed, False if max loops
        exceeded.
        """
        if self.state.current_phase != RefactorPhase.VERIFICATION:
            return False
        if self.state.verification_loop_count >= self.config.max_verification_loops:
            return False

        self.state.verification_loop_count += 1
        self.state.current_phase = RefactorPhase.INTENT_DISCOVERY
        return True

    def record_artifact(self, content: str) -> None:
        """Save the output of the current phase as an artifact."""
        self.state.record_artifact(self.state.current_phase, content)

    def get_artifact(self, phase: RefactorPhase) -> str:
        """Get the saved artifact for *phase*.

        Returns empty string if no artifact was recorded.
        """
        return self.state.artifacts.get(phase.value, "")

    def build_result(
        self,
        success: bool = True,
        boundary_test_count: int = 0,
        verification_passed: bool = False,
        errors: Optional[List[str]] = None,
        summary: str = "",
    ) -> RefactorSessionResult:
        """Construct a ``RefactorSessionResult`` from current state."""
        return RefactorSessionResult(
            success=success,
            completed_phases=[p.value for p in sorted(self.state.completed_phases, key=lambda x: x.value)],
            boundary_test_count=boundary_test_count,
            verification_passed=verification_passed,
            loop_count=self.state.verification_loop_count,
            elapsed_seconds=self.state.elapsed_seconds,
            errors=errors or [],
            summary=summary,
        )

    # ── Phase sequence helpers ─────────────────────────────────────────

    def phases_remaining(self) -> List[RefactorPhase]:
        """Return the list of phases not yet completed, in order."""
        return [
            p for p in REFACTOR_PHASE_ORDER
            if p not in self.state.completed_phases
        ]

    def phase_progress(self) -> str:
        """Return a human-readable progress report."""
        total = len(REFACTOR_PHASE_ORDER)
        done = len(self.state.completed_phases)
        pct = (done / total) * 100 if total > 0 else 0

        lines = [f"Refactoring session: {done}/{total} phases complete ({pct:.0f}%)"]
        lines.append(f"  Current: {self.state.current_phase.value}")
        lines.append(f"  Loop count: {self.state.verification_loop_count}")
        lines.append(f"  Elapsed: {self.state.elapsed_seconds:.1f}s")
        return "\n".join(lines)
