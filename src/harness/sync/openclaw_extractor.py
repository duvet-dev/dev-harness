"""OpenClaw config file extractor.

Reads agent configuration files from known OpenClaw paths and returns
structured data for the release pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of extracting OpenClaw configuration files."""

    identities: dict[str, str] = field(default_factory=dict)
    """Agent name → identity content (SOUL.md equivalent)."""

    procedures: dict[str, str] = field(default_factory=dict)
    """Agent name → procedures content (AGENTS.md equivalent)."""

    community_standards: str | None = None
    """Community standards content, if found."""

    tools: str | None = None
    """Tools content (TOOLS.md), if found."""

    agent_definitions: list[dict] = field(default_factory=list)
    """Agent definitions extracted from vault/entity-index and agent sources."""

    sources_read: list[str] = field(default_factory=list)
    """Paths of files actually read during extraction."""


class OpenClawExtractor:
    """Reads OpenClaw config files from known paths.

    Discovers agent configuration by scanning workspaces for SOUL.md,
    AGENTS.md, TOOLS.md, and community standards files.
    """

    def __init__(
        self,
        openclaw_dir: str | None = None,
        skills_dir: str | None = None,
        vault_dir: str | None = None,
    ):
        self.openclaw_dir = Path(
            openclaw_dir or "~/.openclaw/workspaces/andy-personal/"
        ).expanduser()
        self.skills_dir = Path(
            skills_dir or "~/homebrew/lib/node_modules/openclaw/skills/"
        ).expanduser()
        self.vault_dir = Path(
            vault_dir or "~/Obsidian/AgentAndy/AgentBrain/"
        ).expanduser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_all(self) -> ExtractionResult:
        """Read all OpenClaw source files and return structured data."""
        result = ExtractionResult()

        # Extract identity (SOUL.md) and procedures (AGENTS.md) per agent
        # Scan workspace directories
        workspaces_dir = self.openclaw_dir
        if workspaces_dir.is_dir():
            for subdir in workspaces_dir.iterdir():
                if not subdir.is_dir():
                    continue
                agent_name = subdir.name

                soul_path = subdir / "SOUL.md"
                identity = self._read_file(soul_path)
                if identity is not None:
                    result.identities[agent_name] = identity
                    result.sources_read.append(str(soul_path))

                agents_path = subdir / "AGENTS.md"
                procedures = self._read_file(agents_path)
                if procedures is not None:
                    result.procedures[agent_name] = procedures
                    result.sources_read.append(str(agents_path))

        # Extract community standards
        standards = self.extract_community_standards()
        if standards is not None:
            result.community_standards = standards

        # Extract tools
        tools = self.extract_tools()
        if tools is not None:
            result.tools = tools

        # Extract agent registry
        result.agent_definitions = self.extract_agent_registry()

        return result

    def extract_identity(self, agent_name: str) -> str | None:
        """Read SOUL.md equivalent for a named agent workspace."""
        soul_path = self.openclaw_dir / agent_name / "SOUL.md"
        return self._read_file(soul_path)

    def extract_procedures(self, agent_name: str) -> str | None:
        """Read AGENTS.md equivalent for a named agent workspace."""
        agents_path = self.openclaw_dir / agent_name / "AGENTS.md"
        return self._read_file(agents_path)

    def extract_community_standards(self) -> str | None:
        """Read community standards from skills directory."""
        paths_to_try = [
            self.skills_dir / "community-standards.md",
        ]
        for path in paths_to_try:
            content = self._read_file(path)
            if content is not None:
                return content
        return None

    def extract_tools(self) -> str | None:
        """Read TOOLS.md from the primary workspace."""
        path = self.openclaw_dir / "TOOLS.md"
        return self._read_file(path)

    def extract_agent_registry(self) -> list[dict]:
        """Extract agent definitions from vault entity-index and sources.

        Scans the vault for entity-index.md and agent source directories
        to build a list of agent definitions.
        """
        definitions: list[dict] = []

        # Try vault entity-index
        entity_index_path = (
            self.vault_dir / "agent-entity-index.md"
        )
        content = self._read_file(entity_index_path)
        if content is not None:
            definitions.append({
                "source": str(entity_index_path),
                "type": "entity-index",
                "content": content,
            })

        # Scan agent workspaces for definitions
        if self.openclaw_dir.is_dir():
            for subdir in self.openclaw_dir.iterdir():
                if not subdir.is_dir():
                    continue
                agent_name = subdir.name
                user_md = subdir / "USER.md"
                content = self._read_file(user_md)
                if content is not None:
                    definitions.append({
                        "source": str(user_md),
                        "type": "agent-definition",
                        "agent_name": agent_name,
                        "content": content,
                    })

        return definitions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(path: Path) -> str | None:
        """Read a file, returning None if missing."""
        try:
            if path.is_file():
                with open(path, encoding="utf-8") as f:
                    return f.read()
            return None
        except OSError as exc:
            logger.debug("Could not read %s: %s", path, exc)
            return None
