"""Tests for artifact/writer.py: ArtifactWriter live artifact persistence.

Tests cover:
- Basic artifact writing (Markdown and YAML)
- Atomic write safety (temp file → rename)
- Metadata correctness (phase, agent_role, timestamp)
- Versioning across iterations
- Path resolution utilities
- Listing and existence checks
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.artifact.writer import ArtifactWriter


class TestArtifactWriterInit:
    """ArtifactWriter initialisation tests."""

    def test_creates_artifacts_dir(self, tmp_path: Path) -> None:
        """Init should create the artifacts directory structure."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        expected = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts"
        # Dir should be created on first write, not on init
        assert not expected.exists()
        # But the path should be set correctly
        assert writer._artifacts_dir == expected

    def test_resolves_root(self, tmp_path: Path) -> None:
        """Root path should be resolved to absolute."""
        relative_path = Path(".")
        writer = ArtifactWriter(relative_path, "test-eng")
        assert writer._root.is_absolute()


class TestArtifactWriterWriteMarkdown:
    """Tests for ArtifactWriter.write_artifact() — Markdown output."""

    def test_writes_basic_artifact(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="architecture-overview",
            content="## Architecture Overview\n\nThis is the design.",
            agent_role="architect",
        )
        assert path.exists()
        text = path.read_text()
        assert text.startswith("---")
        assert "phase: design" in text
        assert "agent_role: architect" in text
        assert "timestamp:" in text
        assert "## Architecture Overview" in text

    def test_writes_to_correct_directory(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="adr-001",
            content="ADR content",
        )
        expected_parent = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design"
        assert path.parent == expected_parent
        assert path.name == "adr-001.md"

    def test_writes_without_agent_role(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="build",
            name="implementation",
            content="Code artifact",
        )
        text = path.read_text()
        assert "agent_role" not in text
        assert "Code artifact" in text

    def test_includes_iteration_metadata(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="design-doc",
            content="v2 content",
            iteration=2,
        )
        text = path.read_text()
        assert "iteration: 2" in text
        assert "v2 content" in text

    def test_includes_custom_metadata(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="review",
            name="review-report",
            content="Review findings",
            metadata={"severity": "high", "finding_count": 3},
        )
        text = path.read_text()
        assert "metadata:" in text
        assert "severity: high" in text
        assert "finding_count: 3" in text


class TestArtifactWriterWriteStructured:
    """Tests for ArtifactWriter.write_structured() — YAML output."""

    def test_writes_yaml_artifact(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        content = {"decision": "Use PostgreSQL", "status": "accepted", "alternatives": ["MySQL", "MongoDB"]}
        path = writer.write_structured(
            phase="design",
            name="adr-002",
            content=content,
            agent_role="architect",
        )
        assert path.exists()
        assert path.suffix == ".yaml"
        text = path.read_text()
        assert text.startswith("---")
        assert "phase: design" in text
        assert "agent_role: architect" in text
        assert "decision: Use PostgreSQL" in text
        assert "status: accepted" in text

    def test_yaml_frontmatter_plus_body(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        content = {"rationale": "Existing expertise", "risk": "Low"}
        path = writer.write_structured(
            phase="design",
            name="adr-003",
            content=content,
        )
        text = path.read_text()
        # Should have YAML frontmatter (--- ... ---) then YAML body
        sections = text.split("---\n")
        assert len(sections) >= 2
        # The frontmatter section contains phase and timestamp
        assert "phase: design" in sections[1] if len(sections) > 1 else True


class TestArtifactWriterWriteBlock:
    """Tests for ArtifactWriter.write_block() — raw content."""

    def test_writes_raw_content(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        content = "# Raw content\nNo headers added."
        path = writer.write_block(
            phase="build",
            name="raw-file",
            content=content,
        )
        assert path.read_text() == content

    def test_block_with_agent_role(self, tmp_path: Path) -> None:
        """agent_role is not added by write_block; it's raw."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_block(
            phase="build",
            name="raw-with-role",
            content="Just content",
            agent_role="coder",
        )
        assert path.read_text() == "Just content"


class TestArtifactWriterAtomicity:
    """Tests for atomic write safety."""

    def test_file_is_fully_written(self, tmp_path: Path) -> None:
        """Written file should contain the full expected content."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        long_content = "x\n" * 1000
        path = writer.write_artifact(
            phase="test",
            name="long-file",
            content=long_content,
        )
        text = path.read_text()
        # Should contain all 1000 x-char-lines after the frontmatter
        x_count = text.count("x")
        assert x_count == 1000, f"Expected 1000 x chars, got {x_count}"

    def test_no_temp_files_left_after_write(self, tmp_path: Path) -> None:
        """No .tmp_ files should remain after a successful write."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(
            phase="design",
            name="clean-write",
            content="Clean content",
        )
        design_dir = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design"
        temp_files = [f for f in design_dir.iterdir() if f.name.startswith(".tmp_")]
        assert len(temp_files) == 0

    def test_overwrite_same_name(self, tmp_path: Path) -> None:
        """Writing with the same phase/name should overwrite the file."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        path1 = writer.write_artifact(
            phase="design",
            name="overwrite-test",
            content="Version 1",
        )
        path2 = writer.write_artifact(
            phase="design",
            name="overwrite-test",
            content="Version 2",
        )
        assert path1 == path2
        assert "Version 2" in path2.read_text()
        assert "Version 1" not in path2.read_text()


class TestArtifactWriterIterationVersioning:
    """Tests for iteration number in filenames."""

    def test_version_0_no_suffix(self, tmp_path: Path) -> None:
        """Iteration 0 should not add version suffix to filename."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="design-doc",
            content="v0",
            iteration=0,
        )
        assert path.name == "design-doc.md"

    def test_version_1_adds_suffix(self, tmp_path: Path) -> None:
        """Iteration > 0 should add -vN suffix."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="design-doc",
            content="v1 content",
            iteration=1,
        )
        assert "v1" in path.name, f"Expected -v1 in filename, got {path.name}"

    def test_version_3_adds_v3_suffix(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.write_artifact(
            phase="design",
            name="design-doc",
            content="v3 content",
            iteration=3,
        )
        assert "v3" in path.name, f"Expected -v3 in filename, got {path.name}"

    def test_iteration_file_not_overwritten_without_iteration(self, tmp_path: Path) -> None:
        """A non-versioned write should not overwrite a versioned one."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(
            phase="design",
            name="doc",
            content="v1",
            iteration=1,
        )
        writer.write_artifact(
            phase="design",
            name="doc",
            content="v0 (base)",
            iteration=0,
        )
        # Both files should coexist
        design_dir = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design"
        files = sorted(f.name for f in design_dir.iterdir() if f.is_file())
        assert "doc-v1.md" in files
        assert "doc.md" in files


class TestArtifactWriterPathResolution:
    """Tests for resolve_path() and list_artifacts()."""

    def test_resolve_path_no_iteration(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.resolve_path("design", "my-doc")
        expected = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design" / "my-doc.md"
        assert path == expected

    def test_resolve_path_with_iteration(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.resolve_path("design", "my-doc", iteration=2)
        expected = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design" / "my-doc-v2.md"
        assert path == expected

    def test_resolve_path_custom_ext(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        path = writer.resolve_path("design", "data", ext=".yaml")
        expected = tmp_path / ".harness" / "engagements" / "test-eng" / "artifacts" / "design" / "data.yaml"
        assert path == expected

    def test_list_artifacts_by_phase(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(phase="design", name="doc-a", content="A")
        writer.write_artifact(phase="design", name="doc-b", content="B")
        writer.write_artifact(phase="build", name="impl", content="C")

        design_files = writer.list_artifacts("design")
        assert len(design_files) == 2

        build_files = writer.list_artifacts("build")
        assert len(build_files) == 1

    def test_list_artifacts_all(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(phase="design", name="doc", content="A")
        writer.write_artifact(phase="build", name="impl", content="B")

        all_files = writer.list_artifacts()
        assert len(all_files) == 2

    def test_list_artifacts_empty_phase(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        assert writer.list_artifacts("nonexistent") == []

    def test_list_artifacts_no_artifacts_yet(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        assert writer.list_artifacts() == []

    def test_artifact_exists(self, tmp_path: Path) -> None:
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(phase="design", name="doc", content="Hello")
        assert writer.artifact_exists("design", "doc") is True
        assert writer.artifact_exists("design", "nonexistent") is False
        assert writer.artifact_exists("build", "doc") is False


class TestArtifactWriterRealWorld:
    """Real-world scenarios that mirror how ArtifactWriter is used."""

    def test_write_and_read_back_full_artifact(self, tmp_path: Path) -> None:
        """Simulate a phase writing an artifact and then reading it."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        content = "## Design Document\n\nFull design description here."
        path = writer.write_artifact(
            phase="design",
            name="design-doc",
            content=content,
            agent_role="architect",
            metadata={"phase_index": 1, "cycle_id": "abc-123"},
        )
        # Read it back
        text = path.read_text()
        assert "phase: design" in text
        assert "agent_role: architect" in text
        assert "timestamp:" in text
        assert "phase_index: 1" in text
        assert "cycle_id: abc-123" in text
        assert "Full design description" in text
        # Content after frontmatter should be preserved
        assert text.strip().endswith("Full design description here.")

    def test_multiple_phases_writing_artifacts(self, tmp_path: Path) -> None:
        """Multiple phases each write their own artifacts."""
        writer = ArtifactWriter(tmp_path, "test-eng")
        writer.write_artifact(phase="discover", name="requirements", content="Requirements")
        writer.write_artifact(phase="design", name="architecture", content="Architecture")
        writer.write_artifact(phase="build", name="implementation", content="Implementation")

        all_files = writer.list_artifacts()
        assert len(all_files) == 3

        # Verify isolation between phase directories
        discover_files = writer.list_artifacts("discover")
        assert len(discover_files) == 1

        design_files = writer.list_artifacts("design")
        assert len(design_files) == 1

    def test_structued_artifact_round_trip(self, tmp_path: Path) -> None:
        """Write a structured YAML artifact and verify YAML parsing."""
        import yaml

        writer = ArtifactWriter(tmp_path, "test-eng")
        content = {"alerts": [], "status": "converged", "findings": 0}
        path = writer.write_structured(
            phase="review",
            name="convergence",
            content=content,
            agent_role="critical-analyser",
        )
        text = path.read_text()
        # Parse the YAML body (everything after the frontmatter block)
        body_start = text.find("---\n", text.find("---\n") + 4)
        if body_start == -1:
            body_start = len(text)
        yaml_body = text[body_start:].strip()
        parsed = yaml.safe_load(yaml_body)
        assert parsed["status"] == "converged"
        assert parsed["findings"] == 0
        assert parsed["alerts"] == []
