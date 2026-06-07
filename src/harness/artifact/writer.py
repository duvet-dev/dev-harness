"""Live ArtifactWriter — immediate persistence for phase artifacts.

The ArtifactWriter writes phase artifacts to disk immediately as they
are produced, enabling real-time review and preventing context compaction
from losing intermediate work.

Artifacts are stored under:
    .harness/engagements/<slug>/artifacts/
        <phase_name>/
            <artifact_name>.<ext>

Atomic writes (temp file -> rename) prevent partial corruption on crash.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class ArtifactWriter:
    """Live writer for phase artifacts.

    Writes artifacts immediately to the engagement's artifacts directory.
    Supports structured content (YAML) and freeform text (Markdown).
    All writes are atomic: write to temp file, then rename.

    Usage::

        writer = ArtifactWriter(root, "my-engagement")
        writer.write_artifact(
            phase="design",
            name="architecture-overview",
            content="## Architecture Overview\\n...",
            agent_role="architect",
        )
        writer.write_structured(
            phase="design",
            name="adr-001",
            content={"status": "accepted", "decision": "..."},
            agent_role="architect",
        )
    """

    def __init__(
        self,
        root: Path,
        engagement_slug: str,
    ) -> None:
        """Initialise the ArtifactWriter.

        Args:
            root: Project root directory.
            engagement_slug: Engagement slug (directory name under
                ``.harness/engagements/``).
        """
        self._root = Path(root).resolve()
        self._slug = engagement_slug
        self._artifacts_dir = (
            self._root
            / ".harness"
            / "engagements"
            / engagement_slug
            / "artifacts"
        )

    # ── Public API ─────────────────────────────────────────────────────

    def write_artifact(
        self,
        phase: str,
        name: str,
        content: str,
        agent_role: str = "",
        iteration: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Write a freeform text artifact (Markdown).

        Args:
            phase: Phase name (e.g. ``"design"``, ``"build"``).
            name: Artifact name (used as filename stem,
                e.g. ``"architecture-overview"``).
            content: Markdown or plain text content.
            agent_role: Agent role that produced the artifact.
            iteration: Iteration number (0 = first pass).
            metadata: Optional additional metadata.

        Returns:
            The absolute path to the written artifact file.
        """
        header = self._build_header(phase, agent_role, iteration, metadata)
        full_content = header + "\n\n" + content
        iter_val = iteration if iteration and iteration > 0 else None
        return self._atomic_write(phase, name, full_content, ".md", iteration=iter_val)

    def write_structured(
        self,
        phase: str,
        name: str,
        content: dict[str, Any],
        agent_role: str = "",
        iteration: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Write a structured artifact (YAML frontmatter + body).

        The content dict is serialised to YAML. A standard header with
        phase, agent_role, iteration, and timestamp is prepended.

        Args:
            phase: Phase name.
            name: Artifact name (filename stem).
            content: Structured data to serialise.
            agent_role: Agent role that produced the artifact.
            iteration: Iteration number.
            metadata: Optional additional metadata.

        Returns:
            The absolute path to the written artifact file.
        """
        header = self._build_header(phase, agent_role, iteration, metadata)
        body = yaml.dump(content, default_flow_style=False, sort_keys=False)
        full_content = header + "\n\n" + body
        iter_val = iteration if iteration and iteration > 0 else None
        return self._atomic_write(phase, name, full_content, ".yaml", iteration=iter_val)

    def write_block(
        self,
        phase: str,
        name: str,
        content: str,
        agent_role: str = "",
        iteration: int = 0,
    ) -> Path:
        """Write raw content block without header modifications.

        Useful when the caller already controls the full content.
        Still uses atomic write for safety.

        Args:
            phase: Phase name.
            name: Artifact name (filename stem).
            content: Raw content to write.
            agent_role: Agent role (included in content if not empty).
            iteration: Iteration number.

        Returns:
            The absolute path to the written artifact file.
        """
        iter_val = iteration if iteration and iteration > 0 else None
        return self._atomic_write(phase, name, content, ".md", iteration=iter_val)

    def resolve_path(
        self,
        phase: str,
        name: str,
        ext: str = ".md",
        iteration: int | None = None,
    ) -> Path:
        """Resolve the expected path for an artifact without writing.

        Args:
            phase: Phase name.
            name: Artifact name (filename stem).
            ext: File extension (default: ``.md``).
            iteration: If set, includes iteration number in filename.

        Returns:
            The expected path (may not exist yet).
        """
        phase_dir = self._artifacts_dir / phase
        filename = self._build_filename(name, ext, iteration)
        return phase_dir / filename

    def list_artifacts(self, phase: str | None = None) -> list[Path]:
        """List all artifact files, optionally filtered by phase.

        Args:
            phase: If set, only list artifacts for this phase.

        Returns:
            Sorted list of artifact file paths.
        """
        if phase:
            search_dir = self._artifacts_dir / phase
            if not search_dir.is_dir():
                return []
            return sorted(self._iter_files(search_dir))

        results: list[Path] = []
        if not self._artifacts_dir.is_dir():
            return results
        for entry in sorted(self._artifacts_dir.iterdir()):
            if entry.is_dir():
                results.extend(sorted(self._iter_files(entry)))
        return results

    def artifact_exists(self, phase: str, name: str) -> bool:
        """Check if an artifact with the given phase and name exists.

        Args:
            phase: Phase name.
            name: Artifact name (matches filename without extension).

        Returns:
            True if at least one file with the given stem exists.
        """
        phase_dir = self._artifacts_dir / phase
        if not phase_dir.is_dir():
            return False
        for f in phase_dir.iterdir():
            if f.is_file() and f.stem == name:
                return True
        return False

    # ── Internals ──────────────────────────────────────────────────────

    def _artifacts_base(self) -> Path:
        """Return the base artifacts directory, creating it if needed."""
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        return self._artifacts_dir

    def _build_header(
        self,
        phase: str,
        agent_role: str,
        iteration: int,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Build the standard artifact header block."""
        now = datetime.now(timezone.utc).isoformat()
        lines = [
            "---",
            f"phase: {phase}",
            f"timestamp: {now}",
        ]
        if agent_role:
            lines.append(f"agent_role: {agent_role}")
        if iteration > 0:
            lines.append(f"iteration: {iteration}")
        if metadata:
            lines.append("metadata:")
            for k, v in metadata.items():
                lines.append(f"  {k}: {v}")
        lines.append("---")
        return "\n".join(lines)

    def _build_filename(
        self,
        name: str,
        ext: str,
        iteration: int | None = None,
    ) -> str:
        """Build the filename for an artifact.

        When iteration is provided and > 0, includes the iteration
        number: ``<name>-v<iteration><ext>``.
        Otherwise: ``<name><ext>``.
        """
        if iteration and iteration > 0:
            return f"{name}-v{iteration}{ext}"
        return f"{name}{ext}"

    def _atomic_write(
        self,
        phase: str,
        name: str,
        content: str,
        ext: str,
        iteration: int | None = None,
    ) -> Path:
        """Write content atomically via temp file + rename.

        Args:
            phase: Phase directory name.
            name: Artifact name (filename stem).
            content: Full content to write.
            ext: File extension (``.md``, ``.yaml``, etc.).
            iteration: Optional iteration number for versioned naming.

        Returns:
            The final absolute path of the written file.
        """
        phase_dir = self._artifacts_dir / phase
        phase_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_filename(name, ext, iteration)
        final_path = phase_dir / filename

        # Atomic write: write to temp file in the same directory,
        # then rename (atomic on the same filesystem).
        fd, tmp_path = tempfile.mkstemp(
            dir=str(phase_dir),
            prefix=f".tmp_{name}_",
            suffix=ext,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.rename(tmp_path, str(final_path))
        except BaseException:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.debug(
            "ArtifactWriter — wrote %s (phase=%s, agent=%s, iter=%s)",
            final_path,
            phase,
            "",  # agent_role not passed here
            iteration or 0,
        )
        return final_path.resolve()

    def _iter_files(self, directory: Path) -> list[Path]:
        """Iterate over artifact files in a directory, excluding temp files."""
        results: list[Path] = []
        try:
            for f in directory.iterdir():
                if f.is_file() and not f.name.startswith(".tmp_"):
                    results.append(f)
        except OSError:
            pass
        return results
