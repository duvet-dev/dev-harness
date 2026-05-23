"""Mapper — transforms OpenClaw concepts to harness template format.

The mapping is a simple format conversion: strip OpenClaw-specific
sections and reflow into harness format. It does not perform deep
analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.sync.openclaw_extractor import ExtractionResult
from harness.templates.agent_templates import (
    IDENTITY_MD_TEMPLATE,
    PROCEDURES_MD_TEMPLATE,
    COMMUNITY_STANDARDS_MD_TEMPLATE,
    TOOLS_MD_TEMPLATE,
    AGENT_ROLES,
)


@dataclass
class AgentTemplates:
    """Template pair for a single agent role."""

    identity: str
    """identity.md content for this agent role."""

    procedures: str
    """procedures.md content for this agent role."""


@dataclass
class MappedTemplates:
    """Result of mapping OpenClaw extraction to harness template format."""

    agents: dict[str, AgentTemplates] = field(default_factory=dict)
    """Role name → pair of identity + procedures templates."""

    community_standards: str | None = None
    """Community standards template content."""

    tools: str | None = None
    """Tools template content."""

    agent_registry: list[dict] = field(default_factory=list)
    """Mapped agent definitions for constitution.yaml agents section."""

    changes_from_previous: dict[str, str] = field(default_factory=dict)
    """What changed vs previous release, keyed by agent role."""


class SyncMapper:
    """Maps OpenClaw extraction results to harness template format."""

    def map(self, extraction: ExtractionResult) -> MappedTemplates:
        """Transform an ExtractionResult into MappedTemplates."""
        templates = MappedTemplates()

        for agent_name, identity_source in extraction.identities.items():
            # Derive role from agent name (workspace directory name)
            role = self._derive_role(agent_name)

            identity = self.map_identity(identity_source, role)
            procedures_source = extraction.procedures.get(agent_name)
            procedures = self.map_procedures(procedures_source or "", role)

            templates.agents[role] = AgentTemplates(
                identity=identity,
                procedures=procedures,
            )

        templates.community_standards = (
            self.map_community_standards(extraction.community_standards)
            if extraction.community_standards
            else COMMUNITY_STANDARDS_MD_TEMPLATE
        )

        templates.tools = (
            self.map_tools(extraction.tools)
            if extraction.tools
            else TOOLS_MD_TEMPLATE
        )

        templates.agent_registry = self.build_agent_registry(
            extraction.agent_definitions
        )

        templates.changes_from_previous = self._detect_changes(
            extraction
        )

        return templates

    # ------------------------------------------------------------------
    # Individual mappers
    # ------------------------------------------------------------------

    def map_identity(self, source: str, role: str) -> str:
        """Convert SOUL.md content to identity.md format.

        Strips OpenClaw-specific sections (AUTO_CUES, RESPOND_AS,
        MODEL_CONTROL), keeps values/boundaries/communication style.
        Falls back to built-in template if source is empty.
        """
        if not source or not source.strip():
            role_label = AGENT_ROLES.get(role, role.replace("-", " ").title())
            return IDENTITY_MD_TEMPLATE.format(agent_name=role_label)

        lines = source.splitlines()
        filtered = [
            line
            for line in lines
            if not any(
                keyword in line
                for keyword in [
                    "AUTO_CUES",
                    "RESPOND_AS",
                    "MODEL_CONTROL",
                    "CIRCUIT_BREAK",
                    "<!-- OPENCLAW_CACHE_BOUNDARY",
                ]
            )
        ]
        return "\n".join(filtered).strip()

    def map_procedures(self, source: str, role: str) -> str:
        """Convert AGENTS.md content to procedures.md format.

        Strips OpenClaw metadata (header tags, CNS directives).
        Falls back to built-in template if source is empty.
        """
        if not source or not source.strip():
            role_label = AGENT_ROLES.get(role, role.replace("-", " ").title())
            return PROCEDURES_MD_TEMPLATE.format(agent_name=role_label)

        lines = source.splitlines()
        filtered = [
            line
            for line in lines
            if not any(
                keyword in line
                for keyword in [
                    "OPENCLAW",
                    "CNS_OPT_OUT",
                    "compaction_checkpoint",
                    "<!--",
                    "-->",
                    "set-private-session",
                ]
            )
        ]
        return "\n".join(filtered).strip()

    def map_community_standards(self, source: str) -> str:
        """Convert community standards to harness format."""
        if not source or not source.strip():
            return COMMUNITY_STANDARDS_MD_TEMPLATE
        return source.strip()

    def map_tools(self, source: str) -> str:
        """Convert TOOLS.md to template format.

        Keeps the structure (sections, headings, code blocks) but
        strips infrastructure-specific values (SSH hosts, API keys,
        camera names) for the template.
        """
        if not source or not source.strip():
            return TOOLS_MD_TEMPLATE

        lines = source.splitlines()
        filtered = [
            line
            for line in lines
            if not any(
                keyword in line.lower()
                for keyword in [
                    "ssh",
                    "api_key",
                    "api key",
                    "password",
                    "secret",
                    "token",
                    "host ",
                ]
            )
        ]
        return "\n".join(filtered).strip()

    def build_agent_registry(
        self, agent_defs: list[dict]
    ) -> list[dict]:
        """Map agent definitions to constitution.yaml agents format.

        Each agent definition becomes an entry with name, role, purpose,
        and capabilities derived from the source content.
        """
        registry = []
        for definition in agent_defs:
            entry = {
                "name": definition.get("agent_name", "unknown"),
                "role": "agent",
                "source": definition.get("source", ""),
                "type": definition.get("type", ""),
            }
            registry.append(entry)
        return registry

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_role(agent_name: str) -> str:
        """Derive a harness role name from an agent workspace name.

        Converts directory names like 'andy-personal' to 'personal'
        and handles known OpenClaw names.
        """
        role_map = {
            "andy-personal": "default",
            "andy-researcher": "researcher",
        }
        return role_map.get(agent_name, agent_name)

    @staticmethod
    def _detect_changes(
        extraction: ExtractionResult,
    ) -> dict[str, str]:
        """Build a changes dictionary from extraction results.

        Compares current extraction to a best-effort snapshot.
        For now, simply reports which agents were found.
        """
        changes: dict[str, str] = {}
        for name in extraction.identities:
            changes[name] = "identity extracted"
        for name in extraction.procedures:
            changes[name] = f"{changes.get(name, '')} + procedures"
        return changes
