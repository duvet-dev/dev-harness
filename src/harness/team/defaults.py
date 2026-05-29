"""7 built-in teams — V7 §10.1.

These teams are shipped with the harness and provide sensible defaults
for architecture, coding, testing, review, planning, discovery, and
validation responsibilities.

Built-in teams are the lowest priority in the merge hierarchy:
built-in < project < user (D38).
"""

from __future__ import annotations

from harness.team.model import AgentTeam


def get_builtin_teams() -> list[AgentTeam]:
    """Return the 7 built-in AgentTeam definitions.

    These teams serve as defaults that can be overridden by project
    or user config via the merge semantics in TeamRegistry.
    """
    return [
        AgentTeam(
            name="architecture",
            description="Architecture design and review",
            agents=[
                "architect",
                "architecture-critic",
                "code-critic",
                "security-critic",
            ],
            guidelines=(
                "## Architecture Team Guidelines\n"
                "- All architectural designs must consider security, "
                "scalability, and maintainability.\n"
                "- Critics should evaluate against SOLID principles "
                "and domain-driven design.\n"
                "- When conflicts arise, safety-first: any critic "
                "flagging an issue = issue with side note."
            ),
        ),
        AgentTeam(
            name="coding",
            description="Code implementation and testing",
            agents=[
                "coding-agent",
                "testing-agent",
            ],
            guidelines=(
                "## Coding Team Guidelines\n"
                "- Write tests before implementation (unless overridden "
                "by session type).\n"
                "- Follow the project's language-specific style guide.\n"
                "- Ensure all new code has at least 80% test coverage."
            ),
        ),
        AgentTeam(
            name="testing",
            description="Software testing and quality assurance",
            agents=[
                "testing-agent",
                "test-coverage-analyser",
            ],
            guidelines=(
                "## Testing Team Guidelines\n"
                "- Run full test suite before reporting completion.\n"
                "- Flag any regressions immediately."
            ),
        ),
        AgentTeam(
            name="review",
            description="Code and design review",
            agents=[
                "design-reviewer",
                "critical-analyser",
                "security-auditor",
            ],
            guidelines=None,
        ),
        AgentTeam(
            name="planning",
            description="Planning and task breakdown",
            agents=[
                "planning-agent",
                "dependency-analyser",
            ],
            guidelines=None,
        ),
        AgentTeam(
            name="discovery",
            description="Research and discovery",
            agents=[
                "discovery-agent",
                "research-agent",
            ],
            guidelines=None,
        ),
        AgentTeam(
            name="validation",
            description="Validation and requirements conformance",
            agents=[
                "validation-agent",
                "example-scenarios-agent",
            ],
            guidelines=None,
        ),
    ]
