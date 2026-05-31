"""Tests for harness.domain.engagement.feedback."""

from pathlib import Path

import pytest
import yaml

from harness.domain.engagement.feedback import (
    FeedbackManager,
    FeedbackPacket,
    OPEN_DIR,
    RESOLVED_DIR,
    SUPERSEDED_DIR,
)


class TestFeedbackPacket:
    def test_default_timestamp_set(self):
        p = FeedbackPacket(from_phase="design", to_phase="build")
        assert p.timestamp != ""

    def test_filename_generation(self):
        p = FeedbackPacket(
            from_phase="design",
            to_phase="build",
            timestamp="2026-05-23T12:00:00+00:00",
        )
        name = p.filename
        assert p.from_phase in name
        assert name.endswith(".md")

    def test_to_frontmatter(self):
        p = FeedbackPacket(
            from_phase="design", to_phase="build",
            title="Test Packet",
            checkpoint_id="cp-01",
        )
        fm = p.to_frontmatter()
        assert fm["type"] == "feedback"
        assert fm["from_phase"] == "design"
        assert fm["to_phase"] == "build"
        assert fm["checkpoint_id"] == "cp-01"
        assert fm["status"] == "open"

    def test_to_file_content_contains_frontmatter_and_body(self):
        p = FeedbackPacket(
            from_phase="design",
            to_phase="build",
            title="Review Needed",
            body="Please review the API contract.",
        )
        content = p.to_file_content()
        assert "---" in content
        assert "type: feedback" in content
        assert "# Review Needed" in content
        assert "Please review the API contract." in content

    def test_roundtrip_from_file_content(self, tmp_path):
        p = FeedbackPacket(
            from_phase="design",
            to_phase="build",
            title="Round-trip",
            body="Test body content.",
            checkpoint_id="cp-01",
            iteration=2,
        )
        content = p.to_file_content()
        parsed = FeedbackPacket.from_file_content(content)
        assert parsed.from_phase == "design"
        assert parsed.to_phase == "build"
        assert parsed.title == "Round-trip"
        assert parsed.body == "Test body content."
        assert parsed.checkpoint_id == "cp-01"
        assert parsed.iteration == 2

    def test_from_file_content_no_frontmatter(self):
        p = FeedbackPacket.from_file_content("Just some text\n")
        assert p.from_phase == "unknown"
        # The source preserves the raw content verbatim (including trailing newline)
        assert p.body == "Just some text\n"

    def test_from_file_content_malformed_yaml(self):
        content = "---\n- invalid: [\n---\nbody"
        p = FeedbackPacket.from_file_content(content)
        # Should not crash; returns minimal packet
        assert p is not None


class TestFeedbackManager:
    def test_create_writes_file(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="design", to_phase="build")
        path = mgr.create(p)
        assert path.exists()
        assert path.parent.name == OPEN_DIR

    def test_create_packet_without_suffix(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="design", to_phase="build")
        # filename is a read-only computed property that always returns a name ending in .md
        path = mgr.create(p)
        assert path.suffix == ".md"

    def test_resolve_moves_to_resolved(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="design", to_phase="build")
        path = mgr.create(p)
        filename = path.name
        resolved = mgr.resolve(filename)
        assert resolved is not None
        assert resolved.parent.name == RESOLVED_DIR
        assert not (mgr.open_dir / filename).exists()

    def test_resolve_returns_none_for_missing(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        assert mgr.resolve("nonexistent.md") is None

    def test_supersede_moves_from_resolved_to_superseded(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="design", to_phase="build")
        path = mgr.create(p)
        mgr.resolve(path.name)
        superseded = mgr.supersede(path.name)
        assert superseded is not None
        assert superseded.parent.name == SUPERSEDED_DIR

    def test_supersede_returns_none_for_missing(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        assert mgr.supersede("nonexistent.md") is None

    def test_list_open_returns_packets(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        mgr.create(FeedbackPacket(from_phase="a", to_phase="b", title="P1"))
        mgr.create(FeedbackPacket(from_phase="c", to_phase="d", title="P2"))
        open_list = mgr.list_open()
        assert len(open_list) == 2

    def test_list_resolved(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="a", to_phase="b")
        path = mgr.create(p)
        mgr.resolve(path.name)
        resolved = mgr.list_resolved()
        assert len(resolved) == 1

    def test_list_superseded(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="a", to_phase="b")
        path = mgr.create(p)
        mgr.resolve(path.name)
        mgr.supersede(path.name)
        assert len(mgr.list_superseded()) == 1

    def test_list_all_groups_by_status(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="a", to_phase="b")
        path = mgr.create(p)
        mgr.resolve(path.name)
        all_packets = mgr.list_all()
        assert set(all_packets.keys()) == {"open", "resolved", "superseded"}

    def test_get_searches_all_dirs(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        p = FeedbackPacket(from_phase="design", to_phase="build", title="Search Me")
        path = mgr.create(p)
        found = mgr.get(path.name)
        assert found is not None
        assert found.title == "Search Me"

    def test_get_returns_none_for_missing(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        assert mgr.get("nope.md") is None

    def test_base_dir_property(self, tmp_path):
        mgr = FeedbackManager(tmp_path, "test-eng")
        # base_dir property returns the path; directory is created on first use
        assert mgr.base_dir.name == "feedback"
        # Verify that accessing open_dir (which is lazily created) makes base_dir exist
        _ = mgr.open_dir
        assert mgr.base_dir.exists()
