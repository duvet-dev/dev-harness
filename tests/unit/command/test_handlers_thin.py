"""Tests for Wave I handlers: thin wrappers (5 handlers).

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
"""
from __future__ import annotations

import pytest

from harness.command.legacy_handlers import (
    FixEngagementHandler,
    RefreshAgentsHandler,
    RenameEngagementHandler,
    SetBranchHandler,
    SetGovernanceHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import CommandHandler

smoke = pytest.mark.smoke


class TestRenameEngagementHandler:
    """Tests for RenameEngagementHandler — pattern verification."""

    def test_importable(self):
        handler = RenameEngagementHandler()
        assert isinstance(handler, RenameEngagementHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_rename_engagement_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "rename_engagement" in registry.list_registered()


class TestSetBranchHandler:
    """Tests for SetBranchHandler — pattern verification."""

    def test_importable(self):
        handler = SetBranchHandler()
        assert isinstance(handler, SetBranchHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_set_branch_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "set_branch" in registry.list_registered()


class TestFixEngagementHandler:
    """Tests for FixEngagementHandler — pattern verification."""

    def test_importable(self):
        handler = FixEngagementHandler()
        assert isinstance(handler, FixEngagementHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_fix_engagement_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "fix_engagement" in registry.list_registered()


class TestRefreshAgentsHandler:
    """Tests for RefreshAgentsHandler — pattern verification."""

    def test_importable(self):
        handler = RefreshAgentsHandler()
        assert isinstance(handler, RefreshAgentsHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_refresh_agents_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "refresh_agents" in registry.list_registered()


class TestSetGovernanceHandler:
    """Tests for SetGovernanceHandler — pattern verification."""

    def test_importable(self):
        handler = SetGovernanceHandler()
        assert isinstance(handler, SetGovernanceHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_set_governance_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "set_governance" in registry.list_registered()
