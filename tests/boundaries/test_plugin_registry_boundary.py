"""Boundary tests for PluginRegistry — instance-based interface.

Tests the contract at the boundary: instance isolation, factory
pattern, and error contracts.
"""

from __future__ import annotations

import pytest

from harness.infrastructure.plugins.registry import PluginRegistry
from harness.agents.backends.base import AbstractBackend, BackendResult, Invocation
from harness.agents.context import ContextPacket


class _TestBackend(AbstractBackend):
    """Minimal test backend for boundary testing."""

    def __init__(self, name="test-backend"):
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "Test backend"

    async def prepare(self, packet: ContextPacket) -> Invocation:
        return Invocation(command="test", model="test")

    async def run(self, invocation: Invocation) -> BackendResult:
        return BackendResult()

    def validate_config(self, config: dict) -> list[str]:
        return []


class TestPluginRegistryBoundary:
    """Boundary tests for PluginRegistry instance-based interface."""

    def test_two_instances_are_independent(self):
        """Two PluginRegistry instances should not share state."""
        r1 = PluginRegistry()
        r2 = PluginRegistry()
        b1 = _TestBackend("alpha")
        b2 = _TestBackend("beta")
        r1.register(b1)
        r2.register(b2)
        assert r1.has_backend("alpha")
        assert not r1.has_backend("beta")
        assert r2.has_backend("beta")
        assert not r2.has_backend("alpha")

    def test_preloaded_backends_skip_initialize(self):
        """When preloaded, initialize() is a no-op."""
        b = _TestBackend("custom")
        reg = PluginRegistry(backends={"custom": b})
        reg.initialize({"api": {}, "cli": {}, "editor": {}})
        assert reg.get("custom") is b
        assert reg.has_backend("custom")

    def test_register_overwrite_is_allowed(self):
        """Registering a backend with same name should overwrite."""
        reg = PluginRegistry()
        reg.register(_TestBackend("dup"))
        b2 = _TestBackend("dup")
        reg.register(b2)
        assert reg.get("dup") is b2

    def test_get_unknown_raises_keyerror(self):
        """Getting an unregistered backend should raise KeyError."""
        reg = PluginRegistry()
        with pytest.raises(KeyError, match="No backend registered"):
            reg.get("nonexistent")

    def test_list_backends_empty(self):
        """Empty registry should list nothing."""
        reg = PluginRegistry()
        assert reg.list_backends() == []

    def test_reset_clears_all(self):
        """Reset should clear all backends."""
        reg = PluginRegistry()
        reg.register(_TestBackend("temp"))
        reg.reset()
        assert not reg.has_backend("temp")

    def test_register_non_backend_raises(self):
        """Registering a non-AbstractBackend should raise TypeError."""
        reg = PluginRegistry()
        with pytest.raises(TypeError, match="AbstractBackend"):
            reg.register("not-a-backend")  # type: ignore
