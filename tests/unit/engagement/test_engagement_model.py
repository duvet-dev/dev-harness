"""Tests for engagement/model.py: Engagement, EngagementStatus, HealthWarning."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from harness.engagement.model import (
    Engagement,
    EngagementStatus,
    HealthWarning,
)


class TestEngagementStatus:
    """EngagementStatus enum tests."""

    def test_values(self) -> None:
        assert EngagementStatus.CREATED.value == "created"
        assert EngagementStatus.ACTIVE.value == "active"
        assert EngagementStatus.PAUSED.value == "paused"
        assert EngagementStatus.ABORTED.value == "aborted"
        assert EngagementStatus.COMPLETED.value == "completed"

    def test_is_str_enum(self) -> None:
        """Should be comparable to strings."""
        assert EngagementStatus.CREATED == "created"
        assert str(EngagementStatus.ACTIVE) == "EngagementStatus.ACTIVE"

    def test_all_members_present(self) -> None:
        expected = {
            "CREATED",
            "ACTIVE",
            "PAUSED",
            "ABORTED",
            "COMPLETED",
        }
        actual = {m.name for m in EngagementStatus}
        assert actual == expected


class TestHealthWarning:
    """HealthWarning dataclass tests."""

    def test_minimal(self) -> None:
        hw = HealthWarning(
            type="dirty_repo",
            message="Repository has uncommitted changes",
        )
        assert hw.type == "dirty_repo"
        assert hw.message == "Repository has uncommitted changes"
        assert isinstance(hw.timestamp, datetime)

    def test_different_timestamps(self) -> None:
        hw1 = HealthWarning(
            type="branch_missing",
            message="Target branch missing",
        )
        hw2 = HealthWarning(
            type="stale_engagement",
            message="Engagement is stale",
        )
        # Timestamps should be very close (same call)
        diff = abs(hw1.timestamp - hw2.timestamp)
        assert diff < timedelta(seconds=1)


class TestEngagement:
    """Engagement dataclass tests."""

    def test_minimal(self) -> None:
        eng = Engagement(slug="test-001")
        assert eng.slug == "test-001"
        assert eng.workflow_name == "standard"
        assert eng.session_type == "greenfield"
        assert eng.current_phase is None
        assert eng.status == EngagementStatus.CREATED
        assert isinstance(eng.created_at, datetime)
        assert isinstance(eng.last_active, datetime)
        assert eng.target_branch == ""
        assert eng.warnings == []

    def test_full_engagement(self) -> None:
        warnings = [
            HealthWarning(
                type="dirty_repo",
                message="Uncommitted changes",
            ),
        ]
        eng = Engagement(
            slug="feature-x",
            workflow_name="standard",
            session_type="refactoring",
            current_phase="design",
            status=EngagementStatus.ACTIVE,
            target_branch="feature/x",
            warnings=warnings,
        )
        assert eng.slug == "feature-x"
        assert eng.workflow_name == "standard"
        assert eng.session_type == "refactoring"
        assert eng.current_phase == "design"
        assert eng.status == EngagementStatus.ACTIVE
        assert eng.target_branch == "feature/x"
        assert len(eng.warnings) == 1

    def test_status_transitions(self) -> None:
        """Engagement status is mutable and can be reassigned."""
        eng = Engagement(
            slug="test-transition",
            status=EngagementStatus.CREATED,
        )
        assert eng.status == EngagementStatus.CREATED

        eng.status = EngagementStatus.ACTIVE
        assert eng.status == EngagementStatus.ACTIVE

        eng.status = EngagementStatus.PAUSED
        assert eng.status == EngagementStatus.PAUSED

        eng.status = EngagementStatus.ABORTED
        assert eng.status == EngagementStatus.ABORTED

    def test_created_at_set_automatically(self) -> None:
        eng1 = Engagement(slug="a")
        eng2 = Engagement(slug="b")
        diff = abs(eng1.created_at - eng2.created_at)
        assert diff < timedelta(seconds=1)

    def test_immutability_of_warnings(self) -> None:
        """Each engagement should have its own warnings list."""
        eng1 = Engagement(slug="a")
        eng2 = Engagement(slug="b")
        eng1.warnings.append(
            HealthWarning(type="test", message="test")
        )
        assert len(eng2.warnings) == 0
