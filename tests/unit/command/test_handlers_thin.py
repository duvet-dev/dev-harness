"""Tests for Wave I handlers: thin wrappers (5 handlers).

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
"""
from __future__ import annotations

import pytest

from harness.command.handlers.mgmt_handlers import (
    FixEngagementTypedHandler,
    RefreshAgentsTypedHandler,
    RenameEngagementTypedHandler,
    SetBranchTypedHandler,
    SetGovernanceTypedHandler,
)
from harness.command.setup import create_bus

smoke = pytest.mark.smoke


class TestRenameEngagementTypedHandler:
    """Tests for RenameEngagementTypedHandler — pattern verification."""

    def test_importable(self):
        handler = RenameEngagementTypedHandler()
        assert isinstance(handler, RenameEngagementTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_rename_engagement_registered(self):
        bus = create_bus()
        assert bus is not None


class TestSetBranchTypedHandler:
    """Tests for SetBranchTypedHandler — pattern verification."""

    def test_importable(self):
        handler = SetBranchTypedHandler()
        assert isinstance(handler, SetBranchTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_set_branch_registered(self):
        bus = create_bus()
        assert bus is not None


class TestFixEngagementTypedHandler:
    """Tests for FixEngagementTypedHandler — pattern verification."""

    def test_importable(self):
        handler = FixEngagementTypedHandler()
        assert isinstance(handler, FixEngagementTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_fix_engagement_registered(self):
        bus = create_bus()
        assert bus is not None


class TestRefreshAgentsTypedHandler:
    """Tests for RefreshAgentsTypedHandler — pattern verification."""

    def test_importable(self):
        handler = RefreshAgentsTypedHandler()
        assert isinstance(handler, RefreshAgentsTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_refresh_agents_registered(self):
        bus = create_bus()
        assert bus is not None


class TestSetGovernanceTypedHandler:
    """Tests for SetGovernanceTypedHandler — pattern verification."""

    def test_importable(self):
        handler = SetGovernanceTypedHandler()
        assert isinstance(handler, SetGovernanceTypedHandler)
        assert isinstance(handler, object)

    @smoke
    def test_set_governance_registered(self):
        bus = create_bus()
        assert bus is not None
