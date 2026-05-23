"""Agent plugin registry — discovers and manages agent backends.

Scans configured directories for modules implementing AbstractBackend.
Supports programmatic registration for built-in backends and filesystem
discovery for custom agent plugins.

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
    """Registry for discovering and managing agent backends.

    Built-in backends (api, cli, editor) are registered automatically.
    Custom backends can be registered programmatically or discovered
    from a directory.
    """

    _backends: dict[str, AbstractBackend] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls, config: dict[str, Any] | None = None) -> None:
        """Initialize the registry with built-in backends.

        Called once at module load or programmatically. Safe to call
        multiple times — subsequent calls are no-ops unless
        force=True.
        """
        if cls._initialized:
            return

        config = config or {}

        # Register built-in backends
        cls._register_builtins(config)

        # Discover custom backends from scan paths
        scan_dirs = config.get("scan_dirs", [])
        if not scan_dirs:
            # Default: scan agents/ subdirectories
            harness_dir = Path(__file__).parent
            agents_dir = harness_dir / "backends"
            if agents_dir.exists():
                scan_dirs.append(str(agents_dir))

        for scan_dir in scan_dirs:
            cls._discover_from_directory(scan_dir)

        cls._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (for testing)."""
        cls._backends = {}
        cls._initialized = False

    @classmethod
    def register(cls, backend: AbstractBackend) -> None:
        """Register a backend instance.

        Overrides any existing backend with the same name.
        """
        if not isinstance(backend, AbstractBackend):
            raise TypeError(
                f"Expected AbstractBackend instance, got {type(backend)}"
            )
        cls._backends[backend.name] = backend
        logger.debug("Registered backend: %s", backend.name)

    @classmethod
    def get(cls, name: str) -> AbstractBackend:
        """Look up a backend by name.

        Args:
            name: Backend name (e.g. 'api', 'cli', 'editor').

        Returns:
            The registered backend instance.

        Raises:
            KeyError: If no backend is registered with that name.
        """
        if not cls._initialized:
            cls.initialize()
        if name not in cls._backends:
            raise KeyError(
                f"No backend registered as '{name}'. "
                f"Available: {', '.join(cls._backends)}"
            )
        return cls._backends[name]

    @classmethod
    def list_backends(cls) -> list[AbstractBackend]:
        """List all registered backends."""
        if not cls._initialized:
            cls.initialize()
        return list(cls._backends.values())

    @classmethod
    def has_backend(cls, name: str) -> bool:
        """Check if a backend is registered."""
        return name in cls._backends

    @classmethod
    def _register_builtins(cls, config: dict) -> None:
        """Register the built-in backends."""
        try:
            from harness.agents.backends.api_backend import ApiBackend
            cls.register(
                ApiBackend(config.get("api", {}))
            )
        except ImportError as exc:
            logger.warning("API backend not available: %s", exc)

        try:
            from harness.agents.backends.cli_backend import CliBackend
            cls.register(
                CliBackend(config.get("cli", {}))
            )
        except ImportError as exc:
            logger.warning("CLI backend not available: %s", exc)

        try:
            from harness.agents.backends.editor_backend import EditorBackend
            cls.register(
                EditorBackend(config.get("editor", {}))
            )
        except ImportError as exc:
            logger.warning("Editor backend not available: %s", exc)

    @classmethod
    def _discover_from_directory(cls, directory: str) -> None:
        """Scan a directory for backend implementations.

        Looks for modules that contain classes implementing
        AbstractBackend.
        """
        scan_path = Path(directory)
        if not scan_path.exists() or not scan_path.is_dir():
            return

        # Add parent to sys.path if not already
        parent = str(scan_path.parent)
        if parent not in __import__("sys").path:
            __import__("sys").path.insert(0, parent)

        # Import all .py files in the directory
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
                cls._scan_module(module)
            except ImportError as exc:
                logger.warning("Could not import %s: %s", module_name, exc)

    @classmethod
    def _scan_module(cls, module) -> None:
        """Scan a module for AbstractBackend implementations."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                name != "AbstractBackend"
                and issubclass(obj, AbstractBackend)
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    cls.register(instance)
                except Exception as exc:
                    logger.warning(
                        "Could not instantiate backend %s: %s", name, exc
                    )
