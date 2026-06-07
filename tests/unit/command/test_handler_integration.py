"""Integration tests for real command handlers through create_bus().

Covers handler dispatch paths for commands that don't require
persistent project state.
"""

from __future__ import annotations

import pytest

from harness.command.setup import create_bus
from harness.command.types import CommandResult


@pytest.fixture
def bus():
    return create_bus()


class TestWaveHandlerIntegration:
    """Tests for wave handler through real create_bus."""

    def test_run_wave_dispatches(self, bus):
        from harness.command.commands.wave import RunWaveCommand
        result = bus.dispatch(RunWaveCommand(slug="test", wave_id="w1"))
        assert isinstance(result, CommandResult)





class TestBatchHandlerIntegration:
    """Tests for batch handlers through real create_bus."""

    def test_list_waves(self, bus):
        from harness.command.commands.batch import ListWavesCommand
        result = bus.dispatch(ListWavesCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_wave_status(self, bus):
        from harness.command.commands.batch import WaveStatusCommand
        result = bus.dispatch(WaveStatusCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_annotate_changelog(self, bus):
        from harness.command.commands.batch import AnnotateChangelogCommand
        result = bus.dispatch(AnnotateChangelogCommand(slug="", wave="w1", text="n"))
        assert isinstance(result, CommandResult)


class TestEngagementHandlerIntegration:
    """Tests for engagement handlers (deferred/nonexistent)."""

    def test_abort_nonexistent(self, bus):
        from harness.command.commands.engagement import AbortEngagementCommand
        result = bus.dispatch(AbortEngagementCommand(slug="nonexistent"))
        assert isinstance(result, CommandResult)


class TestMgmtHandlerIntegration:
    """Tests for mgmt handlers (targeted tests)."""

    def test_fix_nonexistent(self, bus):
        from harness.command.commands.mgmt import FixEngagementCommand
        result = bus.dispatch(FixEngagementCommand(slug="nonexistent"))
        assert isinstance(result, CommandResult)

    def test_refresh_agents(self, bus):
        from harness.command.commands.mgmt import RefreshAgentsCommand
        result = bus.dispatch(RefreshAgentsCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_rename_nonexistent(self, bus):
        from harness.command.commands.mgmt import RenameEngagementCommand
        result = bus.dispatch(RenameEngagementCommand(slug="nonexistent", new_slug="new"))
        assert isinstance(result, CommandResult)
