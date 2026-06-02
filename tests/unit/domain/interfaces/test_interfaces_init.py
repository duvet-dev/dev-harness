"""Tests for domain/interfaces/__init__.py."""

from harness.domain.interfaces import (
    EngagementRepository,
    PlanRepository,
    SnapshotRepository,
)


class TestDomainInterfacesInit:
    def test_engagement_repository_exported(self):
        assert EngagementRepository is not None

    def test_plan_repository_exported(self):
        assert PlanRepository is not None

    def test_snapshot_repository_exported(self):
        assert SnapshotRepository is not None
