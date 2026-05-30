"""Tests for artifact/repository.py: Artifact dataclass + ArtifactRepository.

Tests cover Artifact creation, ArtifactRepository save/load/pending/failed
naming conventions, type inference, and directory listing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from harness.artifact.repository import Artifact, ArtifactRepository
from harness.artifact.types import ArtifactType


class TestArtifact:
    """Artifact dataclass tests."""

    def test_minimal_artifact(self) -> None:
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="Test content",
        )
        assert artifact.type == ArtifactType.SUMMARY
        assert artifact.content == "Test content"
        assert artifact.summary is None
        assert artifact.path == ""
        assert artifact.metadata == {}

    def test_full_artifact(self) -> None:
        artifact = Artifact(
            type=ArtifactType.ARCHITECTURE_DECISION,
            content="Full ADR content",
            summary="ADR summary",
            path="adrs/001-decision.md",
            metadata={"author": "architect", "version": 1},
        )
        assert artifact.type == ArtifactType.ARCHITECTURE_DECISION
        assert artifact.content == "Full ADR content"
        assert artifact.summary == "ADR summary"
        assert artifact.path == "adrs/001-decision.md"
        assert artifact.metadata["author"] == "architect"
        assert artifact.metadata["version"] == 1

    def test_artifact_default_metadata(self) -> None:
        """metadata should default to empty dict, not None."""
        a1 = Artifact(type=ArtifactType.PLAN, content="plan")
        assert a1.metadata == {}

    def test_18_artifact_types_exist(self) -> None:
        """Wave 2 requires 18 ArtifactType members (V7 §9)."""
        members = list(ArtifactType)
        assert len(members) == 18
        names = [m.value for m in members]
        assert "planning_doc" in names
        assert "requirements_spec" in names
        assert "architecture_decision" in names
        assert "architectural_overview" in names
        assert "consolidated_review" in names
        assert "code_diff" in names
        assert "implementation" in names
        assert "test_results" in names
        assert "coverage_report" in names
        assert "review_report" in names
        assert "security_report" in names
        assert "dependency_report" in names
        assert "validation_report" in names
        assert "boundary_test" in names
        assert "plan" in names
        assert "assessment" in names
        assert "feedback" in names
        assert "summary" in names


class TestArtifactRepository:
    """ArtifactRepository filesystem tests."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="Hello, world!",
            path="hello.md",
        )
        saved_path = repo.save(artifact)
        loaded = repo.load(saved_path)
        assert loaded is not None
        assert loaded.content == "Hello, world!"
        assert loaded.type == ArtifactType.SUMMARY

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.PLAN,
            content="Plan content",
            path="plan.md",
        )
        saved = repo.save(artifact)
        assert Path(saved).exists()
        assert (tmp_path / "plan" / "plan.md").exists()

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        loaded = repo.load(tmp_path / "nonexistent.md")
        assert loaded is None

    def test_save_pending_naming(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.REVIEW_REPORT,
            content="In progress",
            path="review.md",
        )
        pending_path = repo.save_pending(artifact)
        assert pending_path.endswith(".pending.md")
        assert Path(pending_path).exists()

    def test_save_failed_naming(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.REVIEW_REPORT,
            content="Failed",
            path="review.md",
        )
        failed_path = repo.save_failed(artifact)
        assert failed_path.endswith(".failed.md")
        assert Path(failed_path).exists()

    def test_pending_failed_completed_sequence(self, tmp_path: Path) -> None:
        """Simulate the .pending.md → .md convention."""
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.REVIEW_REPORT,
            content="Starting review...",
            path="review.md",
        )
        # Start as pending
        repo.save_pending(artifact)
        pending = tmp_path / "review_report" / "review.pending.md"
        assert pending.exists()

        # Complete it
        completed = Artifact(
            type=ArtifactType.REVIEW_REPORT,
            content="Review complete",
            path="review.md",
        )
        repo.save(completed)
        completed_path = tmp_path / "review_report" / "review.md"
        assert completed_path.exists()
        assert completed_path.read_text() == "Review complete"

        # Or fail it
        repo.save_failed(artifact)
        failed = tmp_path / "review_report" / "review.failed.md"
        assert failed.exists()

    def test_list_artifacts_by_type(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        repo.save(Artifact(
            type=ArtifactType.SUMMARY,
            content="Summary 1",
            path="s1.md",
        ))
        repo.save(Artifact(
            type=ArtifactType.SUMMARY,
            content="Summary 2",
            path="s2.md",
        ))
        repo.save(Artifact(
            type=ArtifactType.PLAN,
            content="Plan",
            path="p1.md",
        ))

        summaries = repo.list_artifacts(ArtifactType.SUMMARY)
        assert len(summaries) == 2

        plans = repo.list_artifacts(ArtifactType.PLAN)
        assert len(plans) == 1

    def test_list_all_artifacts(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        repo.save(Artifact(
            type=ArtifactType.SUMMARY,
            content="Summary",
            path="s.md",
        ))
        repo.save(Artifact(
            type=ArtifactType.PLAN,
            content="Plan",
            path="p.md",
        ))

        all_artifacts = repo.list_artifacts()
        assert len(all_artifacts) == 2

    def test_list_artifacts_no_results(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        assert repo.list_artifacts(ArtifactType.SUMMARY) == []

    def test_delete(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        saved = repo.save(Artifact(
            type=ArtifactType.SUMMARY,
            content="To delete",
            path="delete_me.md",
        ))
        assert Path(saved).exists()
        deleted = repo.delete(saved)
        assert deleted is True
        assert not Path(saved).exists()

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        deleted = repo.delete(tmp_path / "nonexistent.md")
        assert deleted is False

    def test_save_with_output_dir_override(self, tmp_path: Path) -> None:
        repo = ArtifactRepository(base_path=tmp_path)
        output_dir = tmp_path / "custom_output"
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="Output override",
            path="out.md",
        )
        saved = repo.save(artifact, output_dir=str(output_dir))
        assert (output_dir / "out.md").exists()
        assert str(output_dir) in saved

    def test_load_with_type_inference(self, tmp_path: Path) -> None:
        """Loading should infer ArtifactType from parent directory name."""
        repo = ArtifactRepository(base_path=tmp_path)
        artifact = Artifact(
            type=ArtifactType.SECURITY_REPORT,
            content="Security findings",
            path="audit.md",
        )
        repo.save(artifact)
        loaded = repo.load(tmp_path / "security_report" / "audit.md")
        assert loaded is not None
        assert loaded.type == ArtifactType.SECURITY_REPORT

    def test_default_base_path(self) -> None:
        """Default base_path should be cwd."""
        repo = ArtifactRepository()
        assert str(repo._base_path) == str(Path.cwd())
