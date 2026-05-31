"""Tests for infrastructure.plugins.registry — backend plugin registry.

Tests initialization, registration, lookup, and discovery using
the instance-based PluginRegistry.
"""

from __future__ import annotations

import pytest

from harness.agents.backends.base import AbstractBackend, BackendResult, Invocation
from harness.agents.context import ContextPacket
from harness.infrastructure.plugins.registry import PluginRegistry


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
    """Tests for instance-based PluginRegistry."""

    def setup_method(self):
        self.registry = PluginRegistry()

    def test_initialize_registers_builtins(self):
        """initialize() registers api, cli, editor backends."""
        self.registry.initialize()
        assert self.registry.has_backend("api")
        assert self.registry.has_backend("cli")
        assert self.registry.has_backend("editor")

    def test_initialize_is_idempotent(self):
        """Calling initialize multiple times is safe."""
        self.registry.initialize()
        self.registry.initialize()
        assert self.registry.has_backend("api")

    def test_reset_clears(self):
        """reset() clears all backends."""
        self.registry.initialize()
        self.registry.reset()
        assert not self.registry.has_backend("api")

    def test_register_backend(self):
        """register() adds a backend."""
        backend = MockBackend("custom")
        self.registry.register(backend)
        assert self.registry.has_backend("custom")

    def test_register_requires_abstract_backend(self):
        """register() raises TypeError for non-AbstractBackend."""
        with pytest.raises(TypeError, match="AbstractBackend"):
            self.registry.register("not-a-backend")

    def test_get_backend(self):
        """get() returns a registered backend."""
        self.registry.initialize()
        backend = self.registry.get("api")
        assert backend.name == "api"

    def test_get_missing_backend_raises(self):
        """get() raises KeyError for unregistered backends."""
        with pytest.raises(KeyError, match="No backend registered"):
            self.registry.get("nonexistent")

    def test_list_backends(self):
        """list_backends() returns all backends."""
        self.registry.initialize()
        backends = self.registry.list_backends()
        names = [b.name for b in backends]
        assert "api" in names
        assert "cli" in names

    def test_overwrite_backend(self):
        """register() overwrites an existing backend with the same name."""
        self.registry.initialize()
        b1 = self.registry.get("api")
        b2 = MockBackend("api")
        self.registry.register(b2)
        assert self.registry.get("api") is b2
        assert self.registry.get("api") is not b1

    def test_has_backend_false(self):
        """has_backend() returns False for unregistered names."""
        assert self.registry.has_backend("nonexistent") is False

    @pytest.mark.asyncio
    async def test_registered_backends_functional(self):
        """Registered backends can prepare and run."""
        self.registry.initialize()
        backend = self.registry.get("editor")

        packet = ContextPacket(
            engagement_id="test",
            phase_name="test",
            task_id="t1",
            spec_content="test",
        )

        invocation = await backend.prepare(packet)
        assert invocation is not None

    def test_multiple_registries_isolated(self):
        """Multiple PluginRegistry instances are independent."""
        r1 = PluginRegistry()
        r2 = PluginRegistry()
        r1.register(MockBackend("alpha"))
        r2.register(MockBackend("beta"))
        assert r1.has_backend("alpha")
        assert not r1.has_backend("beta")
        assert r2.has_backend("beta")
        assert not r2.has_backend("alpha")


class TestPluginRegistryInitialBackends:
    """Tests for PluginRegistry with initial backends."""

    def test_initial_backends_supplied(self):
        """PluginRegistry accepts initial backends dict."""
        backend = MockBackend("preloaded")
        registry = PluginRegistry(backends={"preloaded": backend})
        assert registry.has_backend("preloaded")
        assert registry.get("preloaded") is backend

    def test_initial_backends_empty(self):
        """PluginRegistry with empty initial backends."""
        registry = PluginRegistry(backends={})
        assert not registry.has_backend("api")
        assert not registry.has_backend("cli")

    def test_initial_backends_skip_builtins(self):
        """PluginRegistry with initial backends skips auto-discovery."""
        backend = MockBackend("api")
        registry = PluginRegistry(backends={"api": backend})
        # initialize() won't overwrite existing backends
        registry.initialize()
        assert registry.get("api") is backend
