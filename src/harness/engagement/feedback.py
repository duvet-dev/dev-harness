"""Feedback packet protocol for cross-phase navigation.

Creates, manages, and resolves feedback packets that carry discoveries
from one phase to another. Packets live in:
``.harness/engagements/<slug>/feedback/{open,resolved,superseded}/``
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from harness.domain.enums import FeedbackStatus

from harness.engagement.lifecycle import ENGAGEMENTS_DIR

# ── Feedback directories ───────────────────────────────────────────────────

OPEN_DIR = "open"
RESOLVED_DIR = "resolved"
SUPERSEDED_DIR = "superseded"

_FEEDBACK_SUBDIRS = {OPEN_DIR, RESOLVED_DIR, SUPERSEDED_DIR}


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass
class FeedbackPacket:
    """A structured feedback document for cross-phase navigation.

    Serialized as YAML frontmatter + Markdown body to
    ``feedback/<status>/<timestamp>-<from_phase>.md``.
    """

    from_phase: str
    to_phase: str
    timestamp: str = ""
    title: str = ""
    body: str = ""
    status: FeedbackStatus = FeedbackStatus.OPEN
    iteration: int = 1
    max_iterations: int = 5
    checkpoint_id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def filename(self) -> str:
        """Generate a deterministic filename from the packet metadata."""
        ts_compact = self.timestamp.replace(":", "").replace("-", "").split(".")[0]
        return f"{ts_compact}-{self.from_phase}.md"

    def to_frontmatter(self) -> dict:
        """Return the YAML frontmatter dictionary."""
        return {
            "type": "feedback",
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "timestamp": self.timestamp,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "checkpoint_id": self.checkpoint_id,
            "status": self.status.value,
        }

    def to_file_content(self) -> str:
        """Render the full feedback document (frontmatter + body)."""
        frontmatter = yaml.safe_dump(
            self.to_frontmatter(), default_flow_style=False, sort_keys=False
        )
        parts = ["---", frontmatter.strip(), "---", ""]
        if self.title:
            parts.append(f"# {self.title}")
            parts.append("")
        if self.body:
            parts.append(self.body)
            parts.append("")
        return "\n".join(parts)

    @classmethod
    def from_file_content(cls, content: str) -> FeedbackPacket:
        """Parse a feedback document with YAML frontmatter + body.

        Handles standard frontmatter (``--- ... ---``) format.
        """
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            # No frontmatter — minimal packet
            return cls(
                from_phase="unknown",
                to_phase="unknown",
                title="",
                body=content,
            )

        # Find closing ---
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            return cls(from_phase="unknown", to_phase="unknown", body=content)

        frontmatter_raw = "\n".join(lines[1:end_idx])
        body = "\n".join(lines[end_idx + 1:]).strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_raw) or {}
        except yaml.YAMLError:
            frontmatter = {}

        title = ""
        # Try to extract title from body (# Title)
        body_lines = body.splitlines()
        if body_lines and body_lines[0].startswith("# "):
            title = body_lines[0][2:].strip()
            body = "\n".join(body_lines[1:]).strip()

        return cls(
            from_phase=frontmatter.get("from_phase", "unknown"),
            to_phase=frontmatter.get("to_phase", "unknown"),
            timestamp=frontmatter.get("timestamp", ""),
            title=title,
            body=body,
            status=FeedbackStatus(frontmatter.get("status", "open")),
            iteration=frontmatter.get("iteration", 1),
            max_iterations=frontmatter.get("max_iterations", 5),
            checkpoint_id=frontmatter.get("checkpoint_id", ""),
        )


# ── Feedback manager ───────────────────────────────────────────────────────


class FeedbackManager:
    """Manages feedback packets for an engagement.

    Creates, resolves, and lists feedback packets across their
    lifecycle (open → resolved → superseded).
    """

    def __init__(self, root: Path, slug: str) -> None:
        self._root = root
        self._slug = slug
        self._base_dir = root / ENGAGEMENTS_DIR / slug / "feedback"

    # ── Path helpers ────────────────────────────────────────────────────────

    def _dir(self, subdir: str) -> Path:
        p = self._base_dir / subdir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def open_dir(self) -> Path:
        return self._dir(OPEN_DIR)

    @property
    def resolved_dir(self) -> Path:
        return self._dir(RESOLVED_DIR)

    @property
    def superseded_dir(self) -> Path:
        return self._dir(SUPERSEDED_DIR)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create(self, packet: FeedbackPacket) -> Path:
        """Write a feedback packet as open.

        Returns the path to the created file.
        """
        path = self.open_dir / packet.filename
        if not path.suffix:
            path = path.with_suffix(".md")
        path.write_text(packet.to_file_content())
        return path

    def resolve(self, filename: str) -> Optional[Path]:
        """Move a feedback packet from open to resolved.

        Returns the new path, or None if the file wasn't found.
        """
        return self._move_file(filename, OPEN_DIR, RESOLVED_DIR)

    def supersede(self, filename: str) -> Optional[Path]:
        """Move a feedback packet from resolved to superseded.

        Returns the new path, or None if the file wasn't found.
        """
        return self._move_file(filename, RESOLVED_DIR, SUPERSEDED_DIR)

    def list_open(self) -> list[FeedbackPacket]:
        """List all open feedback packets."""
        return self._list_dir(OPEN_DIR)

    def list_resolved(self) -> list[FeedbackPacket]:
        """List all resolved feedback packets."""
        return self._list_dir(RESOLVED_DIR)

    def list_superseded(self) -> list[FeedbackPacket]:
        """List all superseded feedback packets."""
        return self._list_dir(SUPERSEDED_DIR)

    def list_all(self) -> dict[str, list[FeedbackPacket]]:
        """Return all feedback packets grouped by status."""
        return {
            "open": self.list_open(),
            "resolved": self.list_resolved(),
            "superseded": self.list_superseded(),
        }

    def get(self, filename: str) -> Optional[FeedbackPacket]:
        """Read a feedback packet by filename, searching all dirs."""
        for subdir in _FEEDBACK_SUBDIRS:
            path = self._base_dir / subdir / filename
            if path.is_file():
                return FeedbackPacket.from_file_content(path.read_text())
        return None

    # ── Internals ───────────────────────────────────────────────────────────

    def _list_dir(self, subdir: str) -> list[FeedbackPacket]:
        """List all feedback packets in a directory."""
        d = self._base_dir / subdir
        if not d.is_dir():
            return []
        packets: list[FeedbackPacket] = []
        for path in sorted(d.iterdir()):
            if path.suffix == ".md":
                try:
                    packets.append(
                        FeedbackPacket.from_file_content(path.read_text())
                    )
                except Exception:
                    pass
        return packets

    def _move_file(
        self, filename: str, src_subdir: str, dst_subdir: str
    ) -> Optional[Path]:
        """Move a feedback file between status directories."""
        src = self._base_dir / src_subdir / filename
        if not src.is_file():
            return None
        dst = self._base_dir / dst_subdir / filename
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return dst
