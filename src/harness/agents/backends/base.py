"""Abstract backend interface for agent execution.

Defines the contract that all agent backends must implement,
the Invocation data structure, and BackendResult.

Architecture §2.3 — Agent Runner. All backends import and implement this.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from harness.agents.context import ContextPacket
from harness.domain.enums import BackendStatus
from harness.infrastructure.pydantic.resolved_config import ResolvedConfig
from harness.infrastructure.pydantic.resolved_config import ResolvedConfig


@dataclass
class Invocation:
    """A prepared invocation ready for execution.

    Created by a backend's prepare() method. Contains everything needed
    to actually run the agent.
    """

    command: str
    """Shell command or API endpoint URL to invoke."""

    args: list[str] = field(default_factory=list)
    """Command-line arguments or request parameters."""

    env: dict[str, str] = field(default_factory=dict)
    """Environment variables for subprocess execution."""

    work_dir: str = ""
    """Working directory for the execution."""

    input_packet: ContextPacket | None = None
    """The original context packet that produced this invocation."""

    model: str = ""
    """Model override for API backends."""

    resolved_config: ResolvedConfig = field(default_factory=ResolvedConfig)
    """Fully resolved provider configuration passed from the runner.

    Populated by :class:`~harness.agents.runner.AgentRunner` before
    invoking the backend. Contains resolved api_key, base_url, model,
    command, and any other provider-specific fields.
    """

    available_tools: list[dict[str, Any]] = field(default_factory=list)
    """Tool definitions for LLM function-calling (Wave 13).

    Each entry is a provider-agnostic tool spec as produced by
    ``RepoTool.tool_spec()``. The backend converts these to the
    provider-specific format before sending.
    """

    tool_registry: dict[str, Any] = field(default_factory=dict)
    """Map of tool name -> RepoTool-like callable/instance (Wave 13).

    Populated by the runner before invoking the backend. Keys are
    function names (e.g. ``"repo_tool"``), values are objects with
    ``read()``, ``write()``, ``list()``, ``exists()`` methods.
    The backend uses this to execute function calls from the LLM.

    Example::

        {"repo_tool": RepoTool(repo_root, write_prefixes=[...])}
    """

    timeout_seconds: int = 600
    """Per-request timeout in seconds."""


@dataclass
class BackendResult:
    """Result from a backend execution.

    All backends return this from their run() method.
    """

    status: BackendStatus = BackendStatus.FAILURE
    """Execution status."""

    output_dir: str = ""
    """Agent output directory (where produced artifacts live)."""

    artifacts: dict[str, str] = field(default_factory=dict)
    """Produced files: filename -> content."""

    errors: list[str] = field(default_factory=list)
    """Error messages if execution failed."""

    metrics: dict[str, Any] = field(default_factory=dict)
    """Execution metrics: duration_ms, token_count, file_count, etc."""

    def merge(self, other: BackendResult) -> BackendResult:
        """Merge another BackendResult into this one."""
        if other.status == "failure" and self.status == "success":
            self.status = BackendStatus.PARTIAL  # mixed results
        elif other.status != BackendStatus.SUCCESS:
            self.status = other.status
        self.artifacts.update(other.artifacts)
        self.errors.extend(other.errors)
        self.metrics.update(other.metrics)
        return self


class BackendError(Exception):
    """Base exception for backend failures."""


class BackendTimeoutError(BackendError):
    """Raised when a backend execution exceeds its timeout."""


class BackendConfigError(BackendError):
    """Raised when backend configuration is invalid."""


class AbstractBackend(abc.ABC):
    """Interface all agent backends must implement."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique backend identifier (e.g. 'api', 'claude-code')."""

    @abc.abstractmethod
    async def prepare(
        self,
        packet: ContextPacket,
        resolved_config: ResolvedConfig | None = None,
        model: str = "",
    ) -> Invocation:
        """Convert a ContextPacket into a runnable Invocation.

        This is the 'plan' step — validate the packet and decide
        what command/URL to invoke. Should not perform I/O beyond
        configuration lookups.

        Args:
            packet: The context packet describing the agent task.
            resolved_config: Optional resolved provider configuration.
            model: Optional model override string.
        """

    @abc.abstractmethod
    async def run(self, invocation: Invocation) -> BackendResult:
        """Execute a prepared Invocation and return results.

        This is the 'execute' step — may perform significant I/O
        (HTTP requests, subprocess calls). Returns artifacts and metrics.
        """

    @abc.abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """Validate backend configuration from constitution.yaml.

        Returns a list of human-readable error strings. Empty list = valid.
        """
