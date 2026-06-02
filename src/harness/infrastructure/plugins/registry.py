"""Agent plugin registry — discovers and manages agent backends.

Instance-based registry for discovering and managing agent backends.
Replaces the old singleton-based approach. Every consumer is
responsible for creating or receiving an injected PluginRegistry
instance.

Built-in backends (api, cli, editor) are registered automatically
if their configuration is provided. Custom backends can be
registered programmatically or discovered from a directory.

Architecture §3 — Agent System.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from harness.agents.backends.base import AbstractBackend

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Instance-based registry for managing agent backends.

    Unlike the old singleton-based approach, this class requires
    an explicit instance. Each consumer receives an injected
    PluginRegistry rather than calling class methods.

    Args:
        backends: Optional initial backends dict. If None, built-in
            backends will be discovered from config.
    """

    _preloaded: bool = False
    """Internal flag: True if backends were supplied at construction."""

    def __init__(
        self, backends: dict[str, AbstractBackend] | None = None
    ) -> None:
        """Initialize the registry.

        Args:
            backends: Optional initial backends dict. If provided,
                these are used directly without auto-discovery.
                If None, the registry starts empty and must be
                populated via initialize() or register().
        """
        self._backends: dict[str, AbstractBackend] = (
            dict(backends) if backends else {}
        )
        self._preloaded = backends is not None

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize with built-in backends discovered from config.

        If preloaded backends were provided at construction, this is
        a no-op.

        Safe to call multiple times — subsequent calls are no-ops
        unless a backend name isn't already registered.

        Args:
            config: Optional configuration dict with keys:
                - ``api``: API backend config
                - ``cli``: CLI backend config
                - ``editor``: Editor backend config
                - ``scan_dirs``: List of directories to scan for
                  custom backends
        """
        if self._preloaded:
            return
        config = config or {}

        # Register built-in backends
        self._register_builtins(config)

        # Discover custom backends from scan paths
        scan_dirs = config.get("scan_dirs", [])
        if not scan_dirs:
            harness_dir = Path(__file__).parent.parent.parent / "agents"
            agents_dir = harness_dir / "backends"
            if agents_dir.exists():
                scan_dirs.append(str(agents_dir))

        for scan_dir in scan_dirs:
            self._discover_from_directory(scan_dir)

    def reset(self) -> None:
        """Clear all registered backends (for testing)."""
        self._backends.clear()

    def register(self, backend: AbstractBackend) -> None:
        """Register a backend instance.

        Overrides any existing backend with the same name.

        Args:
            backend: An AbstractBackend instance.

        Raises:
            TypeError: If backend is not an AbstractBackend instance.
        """
        if not isinstance(backend, AbstractBackend):
            raise TypeError(
                f"Expected AbstractBackend instance, got {type(backend)}"
            )
        self._backends[backend.name] = backend
        logger.debug("Registered backend: %s", backend.name)

    def get(self, name: str) -> AbstractBackend:
        """Look up a backend by name.

        Args:
            name: Backend name (e.g. 'api', 'cli', 'editor').

        Returns:
            The registered backend instance.

        Raises:
            KeyError: If no backend is registered with that name.
        """
        if name not in self._backends:
            raise KeyError(
                f"No backend registered as '{name}'. "
                f"Available: {', '.join(self._backends)}"
            )
        return self._backends[name]

    def list_backends(self) -> list[AbstractBackend]:
        """List all registered backends."""
        return list(self._backends.values())

    def has_backend(self, name: str) -> bool:
        """Check if a backend is registered.

        Args:
            name: Backend name to check.

        Returns:
            True if a backend with that name is registered.
        """
        return name in self._backends

    def _register_builtins(self, config: dict) -> None:
        """Register the built-in backends if they're not already present."""
        try:
            if "api" not in self._backends:
                from harness.agents.backends.api_backend import ApiBackend
                self.register(ApiBackend(config.get("api", {})))
        except ImportError as exc:
            logger.warning("API backend not available: %s", exc)

        try:
            if "cli" not in self._backends:
                from harness.agents.backends.cli_backend import CliBackend
                self.register(CliBackend(config.get("cli", {})))
        except ImportError as exc:
            logger.warning("CLI backend not available: %s", exc)

        try:
            if "editor" not in self._backends:
                from harness.agents.backends.editor_backend import EditorBackend
                self.register(EditorBackend(config.get("editor", {})))
        except ImportError as exc:
            logger.warning("Editor backend not available: %s", exc)

    def _discover_from_directory(self, directory: str) -> None:
        """Scan a directory for backend implementations.

        Looks for modules that contain classes implementing
        AbstractBackend.
        """
        scan_path = Path(directory)
        if not scan_path.exists() or not scan_path.is_dir():
            return

        parent = str(scan_path.parent)
        import sys
        if parent not in sys.path:
            sys.path.insert(0, parent)

        for item in scan_path.iterdir():
            if item.suffix != ".py" or item.name.startswith("_"):
                continue
            if item.name == "__init__.py":
                continue

            module_name = item.stem
            try:
                module = importlib.import_module(
                    f"harness.agents.backends.{module_name}"
                )
                self._scan_module(module)
            except ImportError as exc:
                logger.warning("Could not import %s: %s", module_name, exc)

    def _scan_module(self, module) -> None:
        """Scan a module for AbstractBackend implementations."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                name != "AbstractBackend"
                and issubclass(obj, AbstractBackend)
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    self.register(instance)
                except Exception as exc:
                    logger.warning(
                        "Could not instantiate backend %s: %s", name, exc
                    )
