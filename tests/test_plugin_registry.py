"""Tests for harness.agents.plugin_registry — backend plugin registry.

Tests initialization, registration, lookup, and discovery.
"""

from __future__ import annotations

import pytest

from harness.agents.backends.base import AbstractBackend, BackendResult, Invocation
from harness.agents.context import ContextPacket
from harness.agents.plugin_registry import PluginRegistry


class MockBackend(AbstractBackend):
    """Test backend implementation."""

    def __init__(self, name="mock-backend"):
        super().__init__()
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "Mock backend for testing"

    async def prepare(self, packet: ContextPacket) -> Invocation:
        return Invocation(
            command="mock", model="test", available_tools=[], input_packet=packet,
        )

    def validate_config(self) -> list[str]:
        return []

    async def run(self, packet: ContextPacket) -> BackendResult:
        return BackendResult(status="success", artifacts={"output": "mock"})


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def setup_method(self):
        PluginRegistry.reset()

    def test_initialize_registers_builtins(self):
        """initialize() registers api, cli, editor backends."""
        PluginRegistry.initialize()
        assert PluginRegistry.has_backend("api")
        assert PluginRegistry.has_backend("cli")
        assert PluginRegistry.has_backend("editor")

    def test_initialize_is_idempotent(self):
        """Calling initialize multiple times is safe."""
        PluginRegistry.initialize()
        PluginRegistry.initialize()
        assert PluginRegistry.has_backend("api")

    def test_reset_clears(self):
        """reset() clears all backends."""
        PluginRegistry.initialize()
        PluginRegistry.reset()
        assert not PluginRegistry._initialized
        assert PluginRegistry._backends == {}

    def test_register_backend(self):
        """register() adds a backend."""
        backend = MockBackend("custom")
        PluginRegistry.register(backend)
        assert PluginRegistry.has_backend("custom")

    def test_register_requires_abstract_backend(self):
        """register() raises TypeError for non-AbstractBackend."""
        with pytest.raises(TypeError, match="AbstractBackend"):
            PluginRegistry.register("not-a-backend")

    def test_get_backend(self):
        """get() returns a registered backend."""
        PluginRegistry.initialize()
        backend = PluginRegistry.get("api")
        assert backend.name == "api"

    def test_get_missing_backend_raises(self):
        """get() raises KeyError for unregistered backends."""
        PluginRegistry.reset()
        with pytest.raises(KeyError, match="No backend registered"):
            PluginRegistry.get("nonexistent")

    def test_list_backends(self):
        """list_backends() returns all backends."""
        PluginRegistry.initialize()
        backends = PluginRegistry.list_backends()
        names = [b.name for b in backends]
        assert "api" in names
        assert "cli" in names

    def test_overwrite_backend(self):
        """register() overwrites an existing backend with the same name."""
        PluginRegistry.reset()
        PluginRegistry.initialize()
        b1 = PluginRegistry.get("api")
        b2 = MockBackend("api")
        PluginRegistry.register(b2)
        assert PluginRegistry.get("api") is b2
        assert PluginRegistry.get("api") is not b1

    def test_has_backend_false(self):
        """has_backend() returns False for unregistered names."""
        PluginRegistry.reset()
        assert PluginRegistry.has_backend("nonexistent") is False

    @pytest.mark.asyncio
    async def test_registered_backends_functional(self):
        """Registered backends can prepare and run."""
        PluginRegistry.reset()
        PluginRegistry.initialize()
        backend = PluginRegistry.get("editor")

        packet = ContextPacket(
            engagement_id="test",
            phase_name="test",
            task_id="t1",
            spec_content="test",
        )

        invocation = await backend.prepare(packet)
        assert invocation is not None
