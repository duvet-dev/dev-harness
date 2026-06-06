"""CLI-to-CommandBus mapping layer.

Provides factory functions and a dispatch helper that translate
Click CLI argument patterns into CommandBus commands.
"""

from harness.cli.commands import (
    agent_list_command,
    annotate_changelog_command,
    assess_command,
    consult_command,
    create_wave_from_finding_command,
    create_waves_from_assessment_command,
    dispatch_cli_command,
    fix_engagement_command,
    team_list_command,
    generate_docs_command,
    inspect_command,
    list_waves_command,
    refresh_agents_command,
    rename_engagement_command,
    set_branch_command,
    set_governance_command,
    summary_command,
    wave_status_command,
)

# Re-export the Click main group
from harness.cli.main import main

__all__ = [
    "agent_list_command",
    "annotate_changelog_command",
    "assess_command",
    "consult_command",
    "create_wave_from_finding_command",
    "create_waves_from_assessment_command",
    "dispatch_cli_command",
    "fix_engagement_command",
    "team_list_command",
    "generate_docs_command",
    "inspect_command",
    "list_waves_command",
    "refresh_agents_command",
    "rename_engagement_command",
    "set_branch_command",
    "set_governance_command",
    "summary_command",
    "wave_status_command",
    "main",
]
