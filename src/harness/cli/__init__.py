"""CLI-to-CommandBus mapping layer.

Provides factory functions and a dispatch helper that translate
Click CLI argument patterns into CommandBus commands.

See V7 §12 Wave 8 for the design rationale.
"""

from harness.cli.commands import (
    abort_engagement_command,
    create_engagement_command,
    dispatch_cli_command,
    enter_phase_command,
    next_command,
    query_status_command,
    query_whats_next_command,
)

# Re-export the Click main group from the new cli/main.py module
# (legacy monolithic cli.py has been fully replaced — no importlib hack)
from harness.cli.main import main

__all__ = [
    "abort_engagement_command",
    "create_engagement_command",
    "dispatch_cli_command",
    "enter_phase_command",
    "next_command",
    "query_status_command",
    "query_whats_next_command",
    "main",
]
