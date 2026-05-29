"""Tests for StepTemplateRegistry (phase/template_registry.py).

V7 §7, §10.5 — Template registration, resolution, expansion with team
cross-reference validation.
"""

from __future__ import annotations

import pytest

from harness.errors import UnknownTemplateError, UnknownTeamError
from harness.artifact.types import ArtifactType
from harness.phase.model import Step
from harness.phase.template import StepTemplate
from harness.phase.template_registry import StepTemplateRegistry
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def team_registry() -> TeamRegistry:
    return TeamRegistry(
        builtin=[
            AgentTeam(name="architecture", agents=["architect"]),
            AgentTeam(name="coding", agents=["coder"]),
        ],
    )


@pytest.fixture
def empty_registry() -> StepTemplateRegistry:
    return StepTemplateRegistry()


@pytest.fixture
def sample_templates() -> list[StepTemplate]:
    return [
        StepTemplate(
            name="arch-review",
            team="architecture",
            output=[ArtifactType.ARCHITECTURE_DECISION],
            description="Architecture review",
        ),
        StepTemplate(
            name="quick-code-fix",
            agents=["coding-agent"],
            output=[ArtifactType.PLANNING_DOC],
            parallel=False,
            description="Quick code fix",
        ),
    ]


@pytest.fixture
def populated_registry(
    team_registry: TeamRegistry,
    sample_templates: list[StepTemplate],
) -> StepTemplateRegistry:
    return StepTemplateRegistry(
        team_registry=team_registry,
        templates=sample_templates,
    )


# ── Registration ──────────────────────────────────────────────────────────


class TestRegister:
    """Tests for StepTemplateRegistry.register()."""

    def test_register_single_template(self, empty_registry) -> None:
        template = StepTemplate(
            name="test-template",
            agents=["architect"],
        )
        empty_registry.register(template)
        assert empty_registry.count == 1
        assert empty_registry.list_templates() == ["test-template"]

    def test_register_with_team_validation(
        self, team_registry
    ) -> None:
        """Registering a template with a valid team should succeed."""
        registry = StepTemplateRegistry(team_registry=team_registry)
        template = StepTemplate(
            name="arch-review",
            team="architecture",
        )
        registry.register(template)
        assert registry.count == 1

    def test_register_with_invalid_team_raises(
        self, team_registry
    ) -> None:
        """Registering a template with an invalid team should fail."""
        registry = StepTemplateRegistry(team_registry=team_registry)
        template = StepTemplate(
            name="invalid-team-template",
            team="nonexistent-team",
        )
        with pytest.raises(UnknownTeamError) as exc:
            registry.register(template)
        assert "nonexistent-team" in str(exc.value)
        assert registry.count == 0

    def test_register_inherits_empty_team_registry(self) -> None:
        """Registry with no TeamRegistry should not validate teams."""
        registry = StepTemplateRegistry()
        template = StepTemplate(
            name="no-validation-template",
            team="nonexistent",
        )
        # No error because there's no TeamRegistry to validate against
        registry.register(template)
        assert registry.count == 1

    def test_register_duplicate_raises(self, populated_registry) -> None:
        """Registering a duplicate template name should raise."""
        template = StepTemplate(
            name="arch-review",
            agents=["architect"],
        )
        with pytest.raises(UnknownTemplateError) as exc:
            populated_registry.register(template)
        assert "already registered" in str(exc.value)

    def test_register_via_constructor(
        self, team_registry, sample_templates
    ) -> None:
        """Constructor should register all templates."""
        registry = StepTemplateRegistry(
            team_registry=team_registry,
            templates=sample_templates,
        )
        assert registry.count == 2
        assert "arch-review" in registry.list_templates()
        assert "quick-code-fix" in registry.list_templates()


# ── Resolution ────────────────────────────────────────────────────────────


class TestResolve:
    """Tests for StepTemplateRegistry.resolve()."""

    def test_resolve_existing(self, populated_registry) -> None:
        template = populated_registry.resolve("arch-review")
        assert template.name == "arch-review"
        assert template.team == "architecture"

    def test_resolve_nonexistent(self, populated_registry) -> None:
        with pytest.raises(UnknownTemplateError) as exc:
            populated_registry.resolve("nonexistent")
        assert "nonexistent" in str(exc.value)

    def test_resolve_from_empty(self, empty_registry) -> None:
        with pytest.raises(UnknownTemplateError):
            empty_registry.resolve("anything")


# ── Expansion ─────────────────────────────────────────────────────────────


class TestExpand:
    """Tests for StepTemplateRegistry.expand()."""

    def test_expand_agent_template(self, populated_registry) -> None:
        """Expanding an agents: template should produce a Step."""
        step = populated_registry.expand("quick-code-fix")
        assert isinstance(step, Step)
        assert step.agents == ["coding-agent"]
        assert step.team is None
        assert step.loop is None
        assert step.phase is None
        assert step.output == [ArtifactType.PLANNING_DOC]
        assert step.parallel is False

    def test_expand_team_template(self, populated_registry) -> None:
        """Expanding a team: template should produce a Step."""
        step = populated_registry.expand("arch-review")
        assert isinstance(step, Step)
        assert step.team == "architecture"
        assert step.agents is None
        assert step.output == [ArtifactType.ARCHITECTURE_DECISION]

    def test_expand_nonexistent(self, populated_registry) -> None:
        with pytest.raises(UnknownTemplateError):
            populated_registry.expand("nonexistent")

    def test_expand_with_context(self, populated_registry) -> None:
        """Context dict is accepted (reserved for future use)."""
        step = populated_registry.expand(
            "quick-code-fix", {"extra": "data"}
        )
        assert step.agents == ["coding-agent"]

    def test_expand_preserves_all_template_fields(
        self, team_registry
    ) -> None:
        """All template fields should be present in expanded Step."""
        template = StepTemplate(
            name="full-test",
            agents=["agent-a", "agent-b"],
            parallel=True,
            role="reviewer",
            input=[ArtifactType.REQUIREMENTS_SPEC],
            output=[ArtifactType.ARCHITECTURE_DECISION],
            description="Full test",
        )
        registry = StepTemplateRegistry(
            team_registry=team_registry,
            templates=[template],
        )
        step = registry.expand("full-test")
        assert step.agents == ["agent-a", "agent-b"]
        assert step.parallel is True
        assert step.role == "reviewer"
        assert step.input == [ArtifactType.REQUIREMENTS_SPEC]
        assert step.output == [ArtifactType.ARCHITECTURE_DECISION]

    def test_expand_validates_team_still_exists(
        self, team_registry
    ) -> None:
        """Expanding a team template validates the team exists."""
        registry = StepTemplateRegistry(
            team_registry=team_registry,
            templates=[
                StepTemplate(
                    name="test",
                    team="architecture",
                ),
            ],
        )
        step = registry.expand("test")
        assert step.team == "architecture"


# ── Listing ────────────────────────────────────────────────────────────────


class TestListTemplates:
    """Tests for StepTemplateRegistry.list_templates()."""

    def test_list_empty(self, empty_registry) -> None:
        assert empty_registry.list_templates() == []

    def test_list_sorted(self, populated_registry) -> None:
        names = populated_registry.list_templates()
        assert names == ["arch-review", "quick-code-fix"]
        assert names == sorted(names)

    def test_list_after_add(self, empty_registry) -> None:
        empty_registry.register(
            StepTemplate(name="beta", agents=["x"])
        )
        empty_registry.register(
            StepTemplate(name="alpha", agents=["y"])
        )
        assert empty_registry.list_templates() == ["alpha", "beta"]
