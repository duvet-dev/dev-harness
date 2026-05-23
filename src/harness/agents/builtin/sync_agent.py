"""Sync Agent — agent spec and SOP for the sync/release pipeline."""

from harness.agents.agent_registry import AgentRole, AgentSpec

SYNC_AGENT = AgentSpec(
    role=AgentRole.SYNC,
    name="Sync Agent",
    description=(
        "Reads current OpenClaw agent configurations and generates "
        "harness release templates. Runs at release time only — not "
        "a developer workflow."
    ),
    sop_summary=[
        "Discover OpenClaw source files (SOUL.md, AGENTS.md, etc.)",
        "Extract identity, procedures, and standards from source",
        "Map OpenClaw concepts to harness template format",
        "Generate template files in target directory",
        "Report changes from previous release",
    ],
    tags=["release", "sync", "infrastructure"],
)
