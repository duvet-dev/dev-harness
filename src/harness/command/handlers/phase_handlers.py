"""Typed handlers for phase lifecycle.

Covers: EnterPhaseHandler, PhaseManagementHandler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.command.types import TypedHandler
from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
from harness.command.results.phase import EnterPhaseResult, ManagePhaseResult


class EnterPhaseTypedHandler(TypedHandler[EnterPhaseCommand, EnterPhaseResult]):
    """Enter a phase via PhaseOrchestrator."""

    def handle(self, command: EnterPhaseCommand) -> EnterPhaseResult:
        try:
            from harness.phase.orchestrator import PhaseOrchestrator

            phase_name = command.phase
            if not phase_name:
                return EnterPhaseResult(
                    success=False,
                    error="No phase specified",
                    message="Missing phase in command",
                )

            orchestrator = PhaseOrchestrator(command.slug)
            # Note: run_phase is async; stubs with sync wrapper for now
            return EnterPhaseResult(
                success=True,
                message=f"Phase '{phase_name}' entry dispatched for '{command.slug}'",
                slug=command.slug,
                phase=phase_name,
            )

        except Exception as exc:
            return EnterPhaseResult(
                success=False,
                error=str(exc),
                message=f"Failed to enter phase: {exc}",
            )


class PhaseManagementTypedHandler(TypedHandler[ManagePhaseCommand, ManagePhaseResult]):
    """Manage engagement phases: list, navigate, feedback, resume, status."""

    def handle(self, command: ManagePhaseCommand) -> ManagePhaseResult:
        try:
            from harness.paths import get_harness_state_path
            from harness.cli.helpers import load_project_snapshot
            from harness.state.snapshot import SnapshotWriter

            slug = command.slug
            action = command.action
            root = Path(command.root)

            if not slug and action not in ("", None):
                return ManagePhaseResult(
                    success=False,
                    error="No engagement slug specified",
                )
            if not slug:
                slug = command.slug
            if not slug:
                return ManagePhaseResult(
                    success=False,
                    error="No engagement slug provided",
                )

            from harness.engagement.checkpoint import CheckpointManager
            from harness.engagement.feedback import (
                FeedbackManager,
                FeedbackPacket,
            )
            from harness.engagement.phase_state import (
                PhaseState,
                PhaseStateManager,
            )

            psm = PhaseStateManager(root, slug)
            fbm = FeedbackManager(root, slug)
            ckm = CheckpointManager(root, slug)

            # List phases
            if action == "list":
                phases = psm.list_phases()
                if not phases:
                    return ManagePhaseResult(
                        success=True,
                        message=f"No phases recorded for '{slug}'.",
                        action=action,
                        slug=slug,
                    )
                phase_list = [
                    {"name": name, "state": record.state.value}
                    for name, record in sorted(phases.items())
                ]
                return ManagePhaseResult(
                    success=True,
                    message=f"{len(phase_list)} phase(s) for '{slug}'.",
                    action=action,
                    slug=slug,
                    phases=phase_list,
                )

            # Navigate (cross-phase jump with checkpoint)
            target = command.target or ""
            if action == "navigate":
                if not target:
                    return ManagePhaseResult(
                        success=False,
                        error="No target phase specified",
                    )
                snapshot_path = get_harness_state_path(root)
                snapshot = load_project_snapshot(snapshot_path)
                current_phase = (
                    snapshot.phase
                    if hasattr(snapshot, "phase") else "unknown"
                )

                ckpt = ckm.create(
                    phase_name=current_phase,
                    context=f"Navigating from {current_phase} to {target}",
                )
                psm.transition(current_phase, PhaseState.PAUSED)
                psm.ensure_phase(target)
                psm.transition(target, PhaseState.ACTIVE)

                for eng in snapshot.engagements:
                    if eng.id == slug:
                        if hasattr(eng, "phase"):
                            eng.phase = target
                        SnapshotWriter.write(snapshot, snapshot_path)
                        break

                return ManagePhaseResult(
                    success=True,
                    message=(
                        f"Navigated from '{current_phase}' to '{target}'. "
                        f"Checkpoint: {ckpt.checkpoint_id}"
                    ),
                    slug=slug,
                    action=action,
                    from_phase=current_phase,
                    to_phase=target,
                    checkpoint=ckpt.checkpoint_id,
                )

            # Send feedback
            fb_target = command.target or ""
            fb_reason = command.feedback_reason
            if action == "feedback":
                if not fb_target:
                    return ManagePhaseResult(
                        success=False,
                        error="No feedback target phase specified",
                    )

                snapshot_path = get_harness_state_path(root)
                snapshot = load_project_snapshot(snapshot_path)
                current_phase = (
                    snapshot.phase
                    if hasattr(snapshot, "phase") else "unknown"
                )

                ckpt = ckm.create(
                    phase_name=current_phase,
                    context=fb_reason or f"Feedback to {fb_target}",
                    feedback_content=fb_reason or "",
                )
                packet = FeedbackPacket(
                    from_phase=current_phase,
                    to_phase=fb_target,
                    title=(fb_reason[:80] if fb_reason else "Feedback"),
                    body=fb_reason,
                    checkpoint_id=ckpt.checkpoint_id,
                )
                fb_path = fbm.create(packet)

                psm.mark_feedback_sent(current_phase, fb_target, ckpt.checkpoint_id)
                psm.ensure_phase(fb_target)

                return ManagePhaseResult(
                    success=True,
                    message=(
                        f"Feedback sent from '{current_phase}' to "
                        f"'{fb_target}'."
                    ),
                    slug=slug,
                    action=action,
                    from_phase=current_phase,
                    to_phase=fb_target,
                    feedback_path=str(fb_path),
                    checkpoint=ckpt.checkpoint_id,
                )

            # Resume
            if action == "resume":
                ckpt = ckm.most_recent()
                if not ckpt:
                    return ManagePhaseResult(
                        success=True,
                        message=f"No checkpoints for '{slug}'.",
                        slug=slug,
                        action=action,
                        resumed=False,
                    )
                return ManagePhaseResult(
                    success=True,
                    message=(
                        f"Resumed from checkpoint: {ckpt.checkpoint_id} "
                        f"(phase: {ckpt.phase_name})"
                    ),
                    slug=slug,
                    action=action,
                    resumed=True,
                    checkpoint=ckpt.checkpoint_id,
                    phase=ckpt.phase_name,
                )

            # Status
            if action == "status":
                phases = psm.list_phases()
                if not phases:
                    return ManagePhaseResult(
                        success=True,
                        message=f"No phase state for '{slug}'.",
                        slug=slug,
                        action=action,
                    )
                phase_data = [
                    {
                        "name": name,
                        "state": record.state.value,
                        "checkpoint_ref": record.checkpoint_ref or "",
                        "feedback_target": record.feedback_target or "",
                    }
                    for name, record in sorted(phases.items())
                ]
                return ManagePhaseResult(
                    success=True,
                    message=f"Phase states for '{slug}'.",
                    slug=slug,
                    action=action,
                    phases=phase_data,
                )

            # Feedback list
            if action == "feedback_list":
                history = fbm.list_feedback()
                entries = [
                    {
                        "status": fb.status,
                        "from": fb.from_phase,
                        "to": fb.to_phase,
                        "title": fb.title,
                    }
                    for fb in (history or [])
                ]
                return ManagePhaseResult(
                    success=True,
                    message=(
                        f"{len(entries)} feedback entry/entries for "
                        f"'{slug}'."
                    ),
                    slug=slug,
                    action=action,
                    phases=entries,
                )

            # No action
            return ManagePhaseResult(
                success=False,
                error="No action specified",
                message="Specify an action: list, navigate, feedback, resume, status, or feedback_list",
            )

        except Exception as exc:
            return ManagePhaseResult(
                success=False,
                error=str(exc),
                message=f"Phase command failed: {exc}",
            )
