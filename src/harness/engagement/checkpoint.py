"""Checkpoint mechanism for cross-phase navigation.

A checkpoint is a lightweight snapshot that records what was happening
when a phase was paused — file hashes, context description, and the
feedback packet that triggered the pause.

Checkpoints live at::
    .harness/engagements/<slug>/checkpoints/<checkpoint_id>/
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from harness.engagement.lifecycle import ENGAGEMENTS_DIR


CHECKPOINT_EXPIRY_HOURS = 24


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass
class Checkpoint:
    """A snapshot of phase state when a cross-phase jump occurred.

    Does NOT copy files — only records file hashes so we can detect
    changes upon resume.
    """

    checkpoint_id: str
    phase_name: str
    engagement_slug: str
    timestamp: str = ""
    context: str = ""
    feedback_packet_path: str = ""
    file_hashes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def is_stale(self) -> bool:
        """Check if the checkpoint is older than CHECKPOINT_EXPIRY_HOURS."""
        try:
            ts = datetime.fromisoformat(self.timestamp)
            age = datetime.now(timezone.utc) - ts
            return age.total_seconds() > CHECKPOINT_EXPIRY_HOURS * 3600
        except (ValueError, TypeError):
            return True


# ── Checkpoint Manager ──────────────────────────────────────────────────────


def _hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _gather_hashes(directory: Path, max_files: int = 500) -> dict[str, str]:
    """Gather SHA-256 hashes for all files under *directory*.

    Only includes regular files (not symlinks or special files).
    Limits recursion to *max_files* to avoid expensive scans of
    large trees (e.g. ``node_modules``).
    """
    hashes: dict[str, str] = {}
    if not directory.is_dir():
        return hashes

    for i, path in enumerate(sorted(directory.rglob("*"))):
        if i >= max_files:
            break
        if path.is_file() and not path.is_symlink():
            relative = str(path.relative_to(directory))
            try:
                hashes[relative] = _hash_file(path)
            except (OSError, PermissionError):
                pass

    return hashes


class CheckpointManager:
    """Manages checkpoints for an engagement.

    Checkpoints are stored at:
    ``.harness/engagements/<slug>/checkpoints/<checkpoint_id>/``
    """

    def __init__(self, root: Path, slug: str) -> None:
        self._root = root
        self._slug = slug
        self._base_dir = root / ENGAGEMENTS_DIR / slug / "checkpoints"

    # ── Path helpers ────────────────────────────────────────────────────────

    def _checkpoint_dir(self, checkpoint_id: str) -> Path:
        return self._base_dir / checkpoint_id

    def _snapshot_path(self, checkpoint_id: str) -> Path:
        return self._checkpoint_dir(checkpoint_id) / "snapshot.json"

    def _context_path(self, checkpoint_id: str) -> Path:
        return self._checkpoint_dir(checkpoint_id) / "context.txt"

    def _feedback_path(self, checkpoint_id: str) -> Path:
        return self._checkpoint_dir(checkpoint_id) / "feedback.md"

    # ── Checkpoint creation ─────────────────────────────────────────────────

    def create(
        self,
        phase_name: str,
        context: str = "",
        feedback_content: str = "",
        snapshot_dir: Optional[Path] = None,
    ) -> Checkpoint:
        """Create a new checkpoint for the given phase.

        Args:
            phase_name: The phase being paused.
            context: Brief description of what was happening.
            feedback_content: The feedback packet content (Markdown).
            snapshot_dir: Directory to hash for snapshot. If None,
                uses the project root.

        Returns:
            The created Checkpoint.
        """
        checkpoint_id = self._next_id()
        ckpt = Checkpoint(
            checkpoint_id=checkpoint_id,
            phase_name=phase_name,
            engagement_slug=self._slug,
            context=context,
        )

        # Create checkpoint directory
        ckpt_dir = self._checkpoint_dir(checkpoint_id)
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        # Write context
        if context:
            path = self._context_path(checkpoint_id)
            path.write_text(context)

        # Write feedback
        if feedback_content:
            path = self._feedback_path(checkpoint_id)
            path.write_text(feedback_content)

        # Gather file hashes
        target_dir = snapshot_dir or self._root
        ckpt.file_hashes = _gather_hashes(target_dir)

        # Write snapshot
        snapshot = {
            "checkpoint_id": checkpoint_id,
            "phase_name": phase_name,
            "engagement_slug": self._slug,
            "timestamp": ckpt.timestamp,
            "context": context,
            "feedback_packet_path": str(self._feedback_path(checkpoint_id))
            if feedback_content
            else "",
            "file_hashes": ckpt.file_hashes,
        }
        self._snapshot_path(checkpoint_id).write_text(
            json.dumps(snapshot, indent=2, sort_keys=True)
        )

        return ckpt

    # ── Checkpoint retrieval ────────────────────────────────────────────────

    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint by ID.

        Returns None if the checkpoint doesn't exist.
        """
        snapshot_path = self._snapshot_path(checkpoint_id)
        if not snapshot_path.is_file():
            return None

        try:
            data = json.loads(snapshot_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        context = ""
        context_path = self._context_path(checkpoint_id)
        if context_path.is_file():
            context = context_path.read_text()

        feedback_path = ""
        fb_path = self._feedback_path(checkpoint_id)
        if fb_path.is_file():
            feedback_path = str(fb_path)

        return Checkpoint(
            checkpoint_id=data.get("checkpoint_id", checkpoint_id),
            phase_name=data.get("phase_name", ""),
            engagement_slug=data.get("engagement_slug", self._slug),
            timestamp=data.get("timestamp", ""),
            context=context,
            feedback_packet_path=feedback_path,
            file_hashes=data.get("file_hashes", {}),
        )

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints for this engagement, newest first."""
        if not self._base_dir.is_dir():
            return []

        checkpoints: list[Checkpoint] = []
        for entry in sorted(self._base_dir.iterdir(), reverse=True):
            if entry.is_dir():
                ckpt = self.load(entry.name)
                if ckpt:
                    checkpoints.append(ckpt)
        return checkpoints

    def get_latest(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint, or None."""
        checkpoints = self.list_checkpoints()
        return checkpoints[0] if checkpoints else None

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint directory.

        Returns True if deleted, False if not found.
        """
        ckpt_dir = self._checkpoint_dir(checkpoint_id)
        if not ckpt_dir.is_dir():
            return False
        import shutil
        shutil.rmtree(ckpt_dir)
        return True

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """Generate the next checkpoint ID in sequence."""
        existing = []
        if self._base_dir.is_dir():
            for entry in self._base_dir.iterdir():
                if entry.is_dir() and entry.name.startswith("checkpoint-"):
                    try:
                        num = int(entry.name.split("-")[1])
                        existing.append(num)
                    except (IndexError, ValueError):
                        pass
        next_num = max(existing) + 1 if existing else 1
        return f"checkpoint-{next_num:02d}"
