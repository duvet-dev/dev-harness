"""Artifact dataclass and repository — V7 §9, §5.6.

Defines the Artifact dataclass for typed step inputs/outputs and the
ArtifactRepository for filesystem persistence.

See V7 §9 for the artifact type system and §5.6 for context pruning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.artifact.types import ArtifactType
from harness.tracing import TraceLogger

logger = TraceLogger("harness.artifact.repository")


@dataclass
class Artifact:
    """A typed artifact produced or consumed by a step.

    Attributes:
        type: The ArtifactType of this artifact.
        content: The full artifact content as a string.
        summary: Optional summary for context pruning (truncation
            heuristic in Wave 3; LLM-powered deferred — D28).
        path: Filesystem path where this artifact is stored.
        metadata: Optional key-value metadata for traceability.
    """

    type: ArtifactType
    content: str
    summary: str | None = None
    path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ArtifactRepository:
    """Filesystem-backed repository for Artifact objects.

    Handles saving and loading artifacts to/from filesystem paths.
    Supports the .pending.md → .md / .failed.md naming convention
    (see V7 §2.2).
    """

    def __init__(self, base_path: str | Path = "") -> None:
        self._base_path = Path(base_path) if base_path else Path.cwd()

    def save(self, artifact: Artifact, output_dir: str | None = None) -> str:
        """Write an artifact to the filesystem.

        Args:
            artifact: The Artifact to persist.
            output_dir: Optional override directory. Defaults to
                base_path / artifact.type.value.

        Returns:
            The absolute path to the written file.
        """
        if output_dir:
            dest = Path(output_dir)
        else:
            dest = self._base_path / artifact.type.value
        dest.mkdir(parents=True, exist_ok=True)

        filepath = dest / Path(artifact.path).name
        if not filepath.suffix:
            filepath = filepath.with_suffix(".md")

        filepath.write_text(artifact.content, encoding="utf-8")
        logger.debug(
            "ArtifactRepository.save",
            extra={
                "path": str(filepath),
                "type": artifact.type.value,
            },
        )
        return str(filepath.resolve())

    def load(self, path: str | Path) -> Artifact | None:
        """Load an artifact from the filesystem.

        Args:
            path: Path to the artifact file.

        Returns:
            The loaded Artifact, or None if the file does not exist
            or cannot be read.
        """
        filepath = Path(path)
        if not filepath.exists() or not filepath.is_file():
            logger.debug(
                "ArtifactRepository.load — not found",
                extra={"path": str(filepath)},
            )
            return None

        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(
                "ArtifactRepository.load — read error",
                extra={"path": str(filepath), "error": str(e)},
            )
            return None

        # Attempt to infer ArtifactType from the directory name
        inferred_type = ArtifactType.SUMMARY
        parent_dir = filepath.parent.name
        for at in ArtifactType:
            if at.value == parent_dir:
                inferred_type = at
                break

        return Artifact(
            type=inferred_type,
            content=content,
            path=str(filepath),
        )

    def save_pending(self, artifact: Artifact, output_dir: str | None = None) -> str:
        """Save an artifact as .pending.md (in-progress state).

        See V7 §2.2 for naming convention.

        Args:
            artifact: The Artifact to persist as pending.
            output_dir: Optional override directory.

        Returns:
            The absolute path to the written file.
        """
        base_path = Path(artifact.path) if artifact.path else Path(artifact.type.value)
        pending_name = base_path.stem + ".pending" + base_path.suffix
        pending_artifact = Artifact(
            type=artifact.type,
            content=artifact.content,
            summary=artifact.summary,
            path=pending_name,
            metadata=artifact.metadata,
        )
        return self.save(pending_artifact, output_dir)

    def save_failed(self, artifact: Artifact, output_dir: str | None = None) -> str:
        """Save an artifact as .failed.md (terminal error state).

        See V7 §2.2 for naming convention.

        Args:
            artifact: The Artifact to persist as failed.
            output_dir: Optional override directory.

        Returns:
            The absolute path to the written file.
        """
        base_path = Path(artifact.path) if artifact.path else Path(artifact.type.value)
        failed_name = base_path.stem + ".failed" + base_path.suffix
        failed_artifact = Artifact(
            type=artifact.type,
            content=artifact.content,
            summary=artifact.summary,
            path=failed_name,
            metadata=artifact.metadata,
        )
        return self.save(failed_artifact, output_dir)

    def list_artifacts(self, artifact_type: ArtifactType | None = None) -> list[Artifact]:
        """List all saved artifacts, optionally filtered by type.

        Args:
            artifact_type: Optional filter. If None, returns all.

        Returns:
            List of Artifact objects found in the repository.
        """
        if artifact_type:
            search_dir = self._base_path / artifact_type.value
            if not search_dir.exists():
                return []
            return self._list_in_dir(search_dir)

        artifacts: list[Artifact] = []
        for at in ArtifactType:
            dir_path = self._base_path / at.value
            if dir_path.exists():
                artifacts.extend(self._list_in_dir(dir_path))
        return artifacts

    def _list_in_dir(self, directory: Path) -> list[Artifact]:
        """List all markdown artifacts in a directory."""
        results: list[Artifact] = []
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix in (".md", ".pending.md", ".failed.md"):
                    artifact = self.load(f)
                    if artifact is not None:
                        results.append(artifact)
        except OSError:
            pass
        return results

    def delete(self, path: str | Path) -> bool:
        """Delete an artifact file.

        Args:
            path: Path to the artifact file.

        Returns:
            True if deleted, False if not found.
        """
        filepath = Path(path)
        if filepath.exists() and filepath.is_file():
            filepath.unlink()
            logger.debug(
                "ArtifactRepository.delete",
                extra={"path": str(filepath)},
            )
            return True
        return False
