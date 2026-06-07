"""Auto mode loop for phase-specific agents.

Implements the creator → critics → convergence → validator loop with
manual override (interrupt/resume) support.

Architecture:
- PhaseAutoRunner orchestrates the loop
- AutoModeState tracks iteration progress
- ManualOverride handles Ctrl+C, /stop, review, /resume

Each phase agent in auto mode:
1. Creates initial artifacts (the "creator" step)
2. Runs critic reviews on those artifacts
3. Checks for convergence (no new issues, design approved, etc.)
4. Validates the final output
5. Stores artifacts and hands control to user or next phase
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import click

from harness.agents.agent_registry import get_phase_agent, ConvergenceConfig

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────

DEFAULT_MAX_ITERATIONS = 5

CONVERGENCE_KEYWORDS = [
    "no issues found",
    "no new issues",
    "converged",
    "convergence",
    "design approved",
    "approved",
    "all checks passed",
]


# ── Enums ─────────────────────────────────────────────────────────────────


class AutoModeStatus(str, Enum):
    """Status of the auto mode loop."""

    IDLE = "idle"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    CONVERGED = "converged"
    MAX_ITERATIONS = "max-iterations"
    ERROR = "error"
    COMPLETED = "completed"


class LoopPhase(str, Enum):
    """Phase within the auto mode loop iteration."""

    CREATOR = "creator"
    CRITIC = "critic"
    CONVERGENCE_CHECK = "convergence_check"
    VALIDATOR = "validator"
    ARTIFACT_STORE = "artifact_store"
    COMPLETE = "complete"


# ── State models ──────────────────────────────────────────────────────────


@dataclass
class AutoModeIteration:
    """Snapshot of a single auto mode iteration.

    Each iteration runs: creator → critics → convergence check → validator.
    """

    iteration: int
    creator_artifacts: dict[str, str] = field(default_factory=dict)
    """Artifacts produced by the creator in this iteration."""

    critic_feedback: list[dict[str, Any]] = field(default_factory=list)
    """Feedback from critics in this iteration."""

    convergence_result: bool = False
    """Whether convergence was reached in this iteration."""

    convergence_reason: str = ""
    """Human-readable reason for convergence or non-convergence."""

    validator_result: dict[str, Any] = field(default_factory=dict)
    """Result from the validator step."""

    artifacts_saved: list[str] = field(default_factory=list)
    """Paths to artifacts saved during this iteration."""


@dataclass
class AutoModeState:
    """Full state of an auto mode run, persistable for interrupt/resume."""

    engagement_slug: str
    phase_name: str
    agent_role: str
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    current_iteration: int = 0
    status: AutoModeStatus = AutoModeStatus.IDLE
    current_loop_phase: LoopPhase = LoopPhase.CREATOR
    iterations: list[AutoModeIteration] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    interrupted_phase: str = ""
    interrupted_iteration: int = 0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        result = asdict(self)
        result["status"] = self.status.value
        result["current_loop_phase"] = self.current_loop_phase.value
        result["iterations"] = [
            asdict(it) for it in self.iterations
        ]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutoModeState":
        """Deserialize from dict."""
        iters = []
        for it_data in data.get("iterations", []):
            it = AutoModeIteration(
                iteration=it_data["iteration"],
                creator_artifacts=it_data.get("creator_artifacts", {}),
                critic_feedback=it_data.get("critic_feedback", []),
                convergence_result=it_data.get("convergence_result", False),
                convergence_reason=it_data.get("convergence_reason", ""),
                validator_result=it_data.get("validator_result", {}),
                artifacts_saved=it_data.get("artifacts_saved", []),
            )
            iters.append(it)
        state = cls(
            engagement_slug=data.get("engagement_slug", ""),
            phase_name=data.get("phase_name", ""),
            agent_role=data.get("agent_role", ""),
            max_iterations=data.get("max_iterations", DEFAULT_MAX_ITERATIONS),
            current_iteration=data.get("current_iteration", 0),
            status=AutoModeStatus(data.get("status", "idle")),
            current_loop_phase=LoopPhase(data.get("current_loop_phase", "creator")),
            iterations=iters,
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            interrupted_phase=data.get("interrupted_phase", ""),
            interrupted_iteration=data.get("interrupted_iteration", 0),
            error_message=data.get("error_message", ""),
        )
        return state


# ── Manual override handler ──────────────────────────────────────────────


class ManualOverride:
    """Handles user interrupt and resume for auto mode loops.

    Usage:
        override = ManualOverride()
        with override.override_context() as ctx:
            for iteration in range(max_iterations):
                if ctx.was_interrupted():
                    # Save state and return
                    return
                # Do work...

    Features:
    - Catches Ctrl+C and registers interrupt
    - Saves checkpoint state on interrupt
    - Supports /stop command via stop() method
    - Can be polled via was_interrupted() / was_resumed()
    """

    def __init__(self) -> None:
        self._interrupted = threading.Event()
        self._resumed = threading.Event()
        self._saved_state: AutoModeState | None = None
        self._original_handler: Any = None

    def interrupt(self, signum: Any = None, frame: Any = None) -> None:
        """Called on Ctrl+C or /stop."""
        if not self._interrupted.is_set():
            self._interrupted.set()
            click.echo()
            click.echo("\n⏸ Auto mode interrupted by user.")
            click.echo("  Use /resume to continue, or /exit to quit.")
            click.echo("  Work done so far is saved.")

    def resume(self) -> None:
        """Called on /resume."""
        self._resumed.set()

    def was_interrupted(self) -> bool:
        """Check if the loop was interrupted."""
        return self._interrupted.is_set()

    def was_resumed(self) -> bool:
        """Check if the loop was resumed after interrupt."""
        return self._resumed.is_set()

    def is_paused(self) -> bool:
        """Check if the loop is currently paused (interrupted, not resumed)."""
        return self._interrupted.is_set() and not self._resumed.is_set()

    def save_state(self, state: AutoModeState) -> None:
        """Save the current auto mode state for resume."""
        self._saved_state = state

    def get_saved_state(self) -> AutoModeState | None:
        """Get the saved state for resume."""
        return self._saved_state

    def clear(self) -> None:
        """Clear all flags and saved state."""
        self._interrupted.clear()
        self._resumed.clear()
        self._saved_state = None

    def install_signal_handler(self) -> None:
        """Install the SIGINT handler for Ctrl+C."""
        self._original_handler = signal.signal(signal.SIGINT, self.interrupt)

    def restore_signal_handler(self) -> None:
        """Restore the original SIGINT handler."""
        if self._original_handler is not None:
            signal.signal(signal.SIGINT, self._original_handler)
            self._original_handler = None


# ── Auto mode state persistence ──────────────────────────────────────────


def save_auto_mode_state(
    root: Path,
    state: AutoModeState,
) -> Path:
    """Persist auto mode state to a checkpoint file.

    The state is saved to:
        .harness/engagements/<slug>/auto-mode/<phase>_state.json
    """
    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, state.engagement_slug)
    auto_mode_dir = eng_dir / "auto-mode"
    auto_mode_dir.mkdir(parents=True, exist_ok=True)
    state_path = auto_mode_dir / f"{state.phase_name}_state.json"
    state_path.write_text(json.dumps(state.to_dict(), indent=2))
    return state_path


def load_auto_mode_state(
    root: Path,
    engagement_slug: str,
    phase_name: str,
) -> AutoModeState | None:
    """Load persisted auto mode state from checkpoint."""
    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, engagement_slug)
    state_path = eng_dir / "auto-mode" / f"{phase_name}_state.json"
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text())
        return AutoModeState.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Failed to load auto mode state: %s", exc)
        return None


def clear_auto_mode_state(
    root: Path,
    engagement_slug: str,
    phase_name: str,
) -> None:
    """Remove the auto mode state checkpoint for a phase."""
    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, engagement_slug)
    state_path = eng_dir / "auto-mode" / f"{phase_name}_state.json"
    if state_path.is_file():
        state_path.unlink()


# ── Convergence checker ────────────────────────────────────────────────


def check_convergence(
    critic_feedback: list[dict[str, Any]],
    convergence_config: ConvergenceConfig | None = None,
) -> tuple[bool, str]:
    """Check whether the critic feedback indicates convergence.

    Convergence is reached when:
    1. No issues found (all feedback is positive/approving)
    2. Only minor/suggestion severity items remain
    3. Explicit convergence keywords detected in feedback

    Args:
        critic_feedback: List of critic feedback dicts.
            Each dict should have "severity" and "judgment" keys.
        convergence_config: ConvergenceConfig with keywords etc.

    Returns:
        Tuple of (converged: bool, reason: str).
    """
    keywords = convergence_config.convergence_keywords if convergence_config else CONVERGENCE_KEYWORDS
    # Use module-level default if none provided
    if not keywords:
        keywords = CONVERGENCE_KEYWORDS

    if not critic_feedback:
        return True, "No critic feedback — assuming convergence."

    # Check for explicit convergence keywords in any feedback
    for fb in critic_feedback:
        judgment = fb.get("judgment", "")
        if any(kw in judgment.lower() for kw in keywords):
            return True, f"Convergence keyword found: {judgment[:100]}"

    # Check severity levels
    blocker_or_major = [
        fb for fb in critic_feedback
        if fb.get("severity", "").lower() in ("blocker", "major")
    ]

    if not blocker_or_major:
        return True, "No blocker or major issues — convergence assumed."

    return (
        False,
        f"{len(blocker_or_major)} blocker/major issue(s) remain.",
    )


# ── Artifact persistence ────────────────────────────────────────────────


def _save_phase_artifact(
    root: Path,
    engagement_slug: str,
    phase_name: str,
    iteration: int,
    content: str,
    artifact_name: str,
) -> Path:
    """Save an artifact to the engagement directory.

    Path: .harness/engagements/<slug>/<phase>/auto/<iteration>_<name>
    """
    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, engagement_slug)
    auto_dir = eng_dir / phase_name / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)
    path = auto_dir / f"{iteration:03d}_{artifact_name}"
    path.write_text(content)
    return path


# ── Auto mode runner ────────────────────────────────────────────────────


class PhaseAutoRunner:
    """Runs the auto mode loop for a phase-specific agent.

    The loop:
        1. CREATOR: Creates initial artifacts using the phase agent
        2. CRITIC: Reviews artifacts and provides feedback
        3. CONVERGENCE_CHECK: Checks if feedback indicates convergence
        4. VALIDATOR: Runs final validation on converged output
        5. ARTIFACT_STORE: Saves all artifacts

    Supports:
    - Manual override (Ctrl+C, /stop, /resume)
    - State persistence for resume
    - Max iterations cap
    """

    def __init__(
        self,
        root: Path,
        engagement_slug: str,
        phase_name: str,
        agent_role: str,
        convergence_config: ConvergenceConfig | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        override: ManualOverride | None = None,
    ):
        self.root = root
        self.engagement_slug = engagement_slug
        self.phase_name = phase_name
        self.agent_role = agent_role
        self.convergence_config = convergence_config
        self.max_iterations = max_iterations
        self.override = override or ManualOverride()
        self.state = AutoModeState(
            engagement_slug=engagement_slug,
            phase_name=phase_name,
            agent_role=agent_role,
            max_iterations=max_iterations,
            start_time=datetime.now(timezone.utc).isoformat(),
        )

    # ── Loop execution ─────────────────────────────────────────────────

    async def run(self) -> AutoModeState:
        """Run the auto mode loop.

        Returns the final state (converged, max-iterations, or error).
        """
        self.state.status = AutoModeStatus.RUNNING
        self.override.install_signal_handler()

        try:
            for iteration in range(self.max_iterations):
                self.state.current_iteration = iteration

                # ── Creator step ──
                self.state.current_loop_phase = LoopPhase.CREATOR
                click.echo(f"\n  Iteration {iteration + 1}/{self.max_iterations}: Creator...")
                iteration_state = AutoModeIteration(iteration=iteration)

                creator_artifacts = await self._run_creator(iteration)
                iteration_state.creator_artifacts = creator_artifacts

                if self.override.was_interrupted():
                    break

                # ── Critic step ──
                self.state.current_loop_phase = LoopPhase.CRITIC
                click.echo(f"  Iteration {iteration + 1}/{self.max_iterations}: Critics...")
                critic_feedback = await self._run_critics(iteration, creator_artifacts)
                iteration_state.critic_feedback = critic_feedback

                if self.override.was_interrupted():
                    break

                # ── Convergence check ──
                self.state.current_loop_phase = LoopPhase.CONVERGENCE_CHECK
                converged, reason = check_convergence(
                    critic_feedback, self.convergence_config
                )
                iteration_state.convergence_result = converged
                iteration_state.convergence_reason = reason

                if converged:
                    click.echo(f"  ✓ Converged: {reason}")
                    self.state.status = AutoModeStatus.CONVERGED
                    self.state.iterations.append(iteration_state)

                    # ── Validator step ──
                    self.state.current_loop_phase = LoopPhase.VALIDATOR
                    validator_result = await self._run_validator(
                        iteration, creator_artifacts, critic_feedback
                    )
                    iteration_state.validator_result = validator_result
                    click.echo("  ✓ Validation complete.")

                    # ── Store artifacts ──
                    self.state.current_loop_phase = LoopPhase.ARTIFACT_STORE
                    saved = self._save_iteration_artifacts(iteration, iteration_state)
                    iteration_state.artifacts_saved = saved
                    click.echo(f"  ✓ Artifacts saved ({len(saved)} files).")
                    break
                else:
                    click.echo(f"  ↺ Not converged: {reason}")
                    self.state.iterations.append(iteration_state)

            else:
                # Loop completed without break = max iterations
                self.state.status = AutoModeStatus.MAX_ITERATIONS
                click.echo(
                    f"\n  ⚠ Max iterations ({self.max_iterations}) reached."
                )
                # Save whatever we have
                if self.state.iterations:
                    last = self.state.iterations[-1]
                    self._save_iteration_artifacts(
                        self.state.current_iteration, last
                    )

        except Exception as exc:
            self.state.status = AutoModeStatus.ERROR
            self.state.error_message = str(exc)
            logger.exception("Auto mode error: %s", exc)
            click.echo(f"\n  ✗ Auto mode error: {exc}", err=True)

        finally:
            self.override.restore_signal_handler()
            self.state.end_time = datetime.now(timezone.utc).isoformat()

            # Save final state
            save_auto_mode_state(self.root, self.state)

        return self.state

    # ── Internal steps ─────────────────────────────────────────────────

    async def _run_creator(self, iteration: int) -> dict[str, str]:
        """Run the creator step — produce initial artifacts.

        In auto mode, this uses the SessionClient to generate
        phase-appropriate artifacts without user interaction.

        Returns dict of {artifact_name: content}.
        """
        from harness.session.client import SessionClient, resolve_provider
        from harness.session.helpers import get_phase_definition

        provider = resolve_provider(self.root)
        phase_def = get_phase_definition(self.phase_name, self.root) or {}

        agent = get_phase_agent(self.phase_name)
        agent_title = agent.name if agent else self.agent_role.replace("-", " ").title()

        prompt = (
            f"You are a **{agent_title}** running in AUTO MODE "
            f"(iteration {iteration + 1}).\n\n"
            f"Your task: produce the best possible output for the "
            f"{self.phase_name.upper()} phase.\n\n"
            f"Generate complete, well-structured artifacts. Write files "
            f"using ## File: path headings so they are captured.\n\n"
        )

        if iteration > 0 and self.state.iterations:
            prev = self.state.iterations[-1]
            if prev.critic_feedback:
                prompt += (
                    "\n\nPREVIOUS ITERATION FEEDBACK:\n"
                )
                for fb in prev.critic_feedback:
                    prompt += f"- [{fb.get('severity', 'info')}] {fb.get('judgment', '')}\n"
                prompt += (
                    "\n\nAddress this feedback in your new output. "
                    "If there are no remaining blocker/major issues, "
                    "explicitly say 'converged' at the end.\n"
                )

        client = SessionClient(
            root=self.root,
            engagement_slug=self.engagement_slug,
            phase_def=phase_def,
            system_prompt=prompt,
        )

        click.echo("    Generating artifacts...")
        output_parts: list[str] = []
        async for chunk in client.stream(
            "Produce your phase artifacts now."
        ):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
            output_parts.append(chunk)
        click.echo()

        response = "".join(output_parts)

        return {
            f"iteration_{iteration:03d}_output.md": response,
        }

    async def _run_critics(
        self,
        iteration: int,
        creator_artifacts: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Run the critic step — review artifacts and provide feedback.

        Reviews the creator's output and identifies issues.

        Returns list of feedback dicts with severity and judgment.
        """
        from harness.session.client import SessionClient, resolve_provider
        from harness.session.helpers import get_phase_definition

        provider = resolve_provider(self.root)
        phase_def = get_phase_definition(self.phase_name, self.root) or {}

        combined_artifacts = "\n\n".join(creator_artifacts.values())

        critic_prompt = (
            "You are a **Critical Reviewer** running in AUTO MODE.\n\n"
            "Your task: review the following phase artifacts critically.\n"
            "Identify issues by severity: BLOCKER, MAJOR, MINOR, SUGGESTION.\n\n"
            "Be thorough. Check for:\n"
            "- Completeness: are all necessary elements present?\n"
            "- Consistency: does the output contradict itself?\n"
            "- Quality: are there gaps, vagueness, or errors?\n"
            "- Standards: does it follow best practices?\n\n"
            "If you find NO issues at all, say 'no issues found' to signal convergence.\n"
            "Format your response as a structured review.\n\n"
            "ARTIFACTS TO REVIEW:\n" + combined_artifacts
        )

        client = SessionClient(
            root=self.root,
            engagement_slug=self.engagement_slug,
            phase_def=phase_def,
            system_prompt=critic_prompt,
        )

        click.echo("    Reviewing artifacts...")
        output_parts: list[str] = []
        async for chunk in client.stream("Review the artifacts now."):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
            output_parts.append(chunk)
        click.echo()

        response = "".join(output_parts)

        # Parse the critic response into structured feedback
        feedback = self._parse_critic_response(response)
        return feedback

    async def _run_validator(
        self,
        iteration: int,
        creator_artifacts: dict[str, str],
        critic_feedback: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run the validator step — validate converged output."""
        from harness.session.client import SessionClient, resolve_provider
        from harness.session.helpers import get_phase_definition

        provider = resolve_provider(self.root)
        phase_def = get_phase_definition(self.phase_name, self.root) or {}

        combined = "\n\n".join(creator_artifacts.values())
        feedback_summary = "\n".join(
            f"- [{fb.get('severity', 'info')}] {fb.get('judgment', '')}"
            for fb in critic_feedback
        )

        validator_prompt = (
            "You are a **Validator** running in AUTO MODE.\n\n"
            "Your task: validate the following phase artifacts.\n"
            "Check:\n"
            "1. Output completeness — does it cover the phase's purpose?\n"
            "2. All issues addressed — were critic findings resolved?\n"
            "3. Ready for next phase — is this output actionable?\n\n"
            "ARTIFACTS:\n" + combined + "\n\n"
            "CRITIC FEEDBACK:\n" + feedback_summary + "\n\n"
            "Produce a structured validation report."
        )

        client = SessionClient(
            root=self.root,
            engagement_slug=self.engagement_slug,
            phase_def=phase_def,
            system_prompt=validator_prompt,
        )

        click.echo("    Validating...")
        output_parts: list[str] = []
        async for chunk in client.stream("Validate the output now."):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
            output_parts.append(chunk)
        click.echo()

        return {
            "validator_output": "".join(output_parts),
            "status": "validated",
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _parse_critic_response(
        self, response: str
    ) -> list[dict[str, Any]]:
        """Parse the critic's response into structured feedback items.

        Looks for severity markers and extracts the judgment.
        """
        feedback: list[dict[str, Any]] = []

        severity_patterns = [
            ("blocker", "BLOCKER"),
            ("major", "MAJOR"),
            ("minor", "MINOR"),
            ("suggestion", "SUGGESTION"),
        ]

        lines = response.split("\n")
        current_severity = "info"
        current_parts: list[str] = []

        for line in lines:
            lowered = line.strip().upper()
            for severity, marker in severity_patterns:
                if marker in lowered and len(line.strip()) < 80:
                    # Save previous item if any
                    if current_parts:
                        feedback.append({
                            "severity": current_severity,
                            "judgment": " ".join(current_parts).strip(),
                        })
                    current_severity = severity
                    current_parts = [line.strip()]
                    break
            else:
                if line.strip() and current_parts:
                    current_parts.append(line.strip())
                elif not line.strip() and current_parts:
                    feedback.append({
                        "severity": current_severity,
                        "judgment": " ".join(current_parts).strip(),
                    })
                    current_parts = []

        # Flush remaining
        if current_parts:
            feedback.append({
                "severity": current_severity,
                "judgment": " ".join(current_parts).strip(),
            })

        # If no structured feedback found, create a single entry
        if not feedback:
            feedback.append({
                "severity": "info",
                "judgment": response.strip()[:200] if response.strip() else "No feedback provided.",
            })

        return feedback

    def _save_iteration_artifacts(
        self,
        iteration: int,
        iteration_state: AutoModeIteration,
    ) -> list[str]:
        """Save artifacts from an iteration to disk."""
        saved: list[str] = []
        for name, content in iteration_state.creator_artifacts.items():
            path = _save_phase_artifact(
                self.root, self.engagement_slug, self.phase_name,
                iteration, content, name,
            )
            saved.append(str(path))

        # Save convergence summary
        summary = (
            f"# Auto Mode Iteration {iteration}\n\n"
            f"**Converged:** {iteration_state.convergence_result}\n"
            f"**Reason:** {iteration_state.convergence_reason}\n\n"
            f"## Critic Feedback\n\n"
        )
        for fb in iteration_state.critic_feedback:
            summary += f"- [{fb.get('severity', 'info')}] {fb.get('judgment', '')}\n"
        if iteration_state.validator_result:
            summary += f"\n## Validator Result\n\n{iteration_state.validator_result.get('validator_output', '')}\n"

        summary_path = _save_phase_artifact(
            self.root, self.engagement_slug, self.phase_name,
            iteration, summary, "convergence_summary.md",
        )
        saved.append(str(summary_path))

        return saved


# ── Auto-mode integration helpers ────────────────────────────────────────


def prompt_auto_mode() -> bool:
    """Prompt the user: run in auto mode or interactive mode?

    Returns True for auto mode, False for interactive.
    """
    try:
        choice = click.prompt(
            "Run in auto mode?",
            type=click.Choice(["auto", "interactive"], case_sensitive=False),
            default="auto",
            show_choices=False,
        )
        return choice.lower() == "auto"
    except (EOFError, KeyboardInterrupt):
        return False
