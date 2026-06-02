"""Plugin infrastructure — backend registry and discovery.

Provides the PluginRegistry for managing and discovering agent
backends. Part of the infrastructure layer, consumed by the
application layer.
"""

from harness.infrastructure.plugins.registry import PluginRegistry

__all__ = ["PluginRegistry"]
