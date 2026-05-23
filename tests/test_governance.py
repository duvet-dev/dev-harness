"""Tests for harness.agents.governance — governance level configuration.

Tests get_project_governance, set_project_governance, get_engagement_governance,
get_active_agents_for_project, and helper functions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.fleet import GovernanceLevel
from harness.agents.governance import (
    get_project_governance,
    set_project_governance,
    get_engagement_governance,
    set_engagement_governance,
    get_active_agents_for_project,
    get_active_agents_for_engagement,
    _parse_level,
)


class TestParseLevel:
    """Tests for _parse_level()."""

    def test_valid_levels(self):
        assert _parse_level("exploration") == GovernanceLevel.EXPLORATION
        assert _parse_level("standard") == GovernanceLevel.STANDARD
        assert _parse_level("strict") == GovernanceLevel.STRICT
        assert _parse_level("  STANDARD  ") == GovernanceLevel.STANDARD

    def test_invalid_level_falls_back(self):
        assert _parse_level("invalid", GovernanceLevel.EXPLORATION) == GovernanceLevel.EXPLORATION


class TestGetProjectGovernance:
    """Tests for get_project_governance()."""

    def test_default_when_no_config(self, tmp_path):
        level = get_project_governance(tmp_path)
        assert level == GovernanceLevel.STANDARD

    def test_reads_from_config(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        config_path = harness_dir / "config.yaml"
        config_path.write_text("governance:\n  level: exploration\n")
        level = get_project_governance(tmp_path)
        assert level == GovernanceLevel.EXPLORATION

    def test_reads_legacy_string_gov(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        config_path = harness_dir / "config.yaml"
        config_path.write_text("governance: strict\n")
        level = get_project_governance(tmp_path)
        assert level == GovernanceLevel.STRICT

    def test_custom_default(self, tmp_path):
        level = get_project_governance(tmp_path, default=GovernanceLevel.EXPLORATION)
        assert level == GovernanceLevel.EXPLORATION


class TestSetProjectGovernance:
    """Tests for set_project_governance()."""

    def test_writes_to_config(self, tmp_path):
        set_project_governance(tmp_path, GovernanceLevel.STRICT)
        # Read it back
        level = get_project_governance(tmp_path)
        assert level == GovernanceLevel.STRICT

    def test_preserves_existing_keys(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        config_path = harness_dir / "config.yaml"
        config_path.write_text("project_name: test\n")
        set_project_governance(tmp_path, GovernanceLevel.EXPLORATION)
        content = config_path.read_text()
        assert "project_name" in content
        assert "exploration" in content


class TestGetEngagementGovernance:
    """Tests for get_engagement_governance()."""

    def test_falls_back_to_project(self, tmp_path):
        level = get_engagement_governance(tmp_path, "test-eng")
        assert level == GovernanceLevel.STANDARD

    def test_reads_from_engagement_config(self, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("governance:\n  level: strict\n")

        level = get_engagement_governance(tmp_path, "test-eng")
        assert level == GovernanceLevel.STRICT

    def test_engagement_overrides_project(self, tmp_path):
        # Set project level to exploration
        set_project_governance(tmp_path, GovernanceLevel.EXPLORATION)

        # Set engagement level to strict
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("governance:\n  level: strict\n")

        level = get_engagement_governance(tmp_path, "test-eng")
        assert level == GovernanceLevel.STRICT

    def test_engagement_legacy_string(self, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("governance: strict\n")

        level = get_engagement_governance(tmp_path, "test-eng")
        assert level == GovernanceLevel.STRICT


class TestSetEngagementGovernance:
    """Tests for set_engagement_governance()."""

    def test_writes_engagement_config(self, tmp_path):
        set_engagement_governance(tmp_path, "test-eng", GovernanceLevel.STRICT)
        level = get_engagement_governance(tmp_path, "test-eng")
        assert level == GovernanceLevel.STRICT

    def test_preserves_existing_keys(self, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement.yaml").write_text("title: Test Engagement\n")

        set_engagement_governance(tmp_path, "test-eng", GovernanceLevel.EXPLORATION)
        content = (eng_dir / "engagement.yaml").read_text()
        assert "title" in content
        assert "exploration" in content


class TestGetActiveAgents:
    """Tests for get_active_agents_for_project and get_active_agents_for_engagement."""

    def test_project_level(self, tmp_path):
        agents = get_active_agents_for_project(tmp_path, "architecture")
        assert isinstance(agents, list)
        assert "architect" in agents

    def test_engagement_level(self, tmp_path):
        agents = get_active_agents_for_engagement(tmp_path, "architecture", "test-eng")
        assert isinstance(agents, list)
        assert len(agents) >= 1

    def test_nonexistent_fleet(self, tmp_path):
        agents = get_active_agents_for_project(tmp_path, "nonexistent")
        assert agents == []
