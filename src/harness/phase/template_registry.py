"""StepTemplateRegistry — V7 §7, §10.5.

Manages StepTemplate definitions loaded from config
(``.harness/step_templates.yaml``). Supports registration, resolution
by name, expansion into concrete Step instances (with team reference
resolution via TeamRegistry), and listing available templates.

Templates that reference a team (``team:`` field) are validated against
the TeamRegistry at registration time to ensure the team exists.
"""

from __future__ import annotations

from harness.errors import UnknownTemplateError
from harness.phase.model import Step, LoopConfig
from harness.phase.template import StepTemplate
from harness.team.registry import TeamRegistry


class StepTemplateRegistry:
    """Registry of StepTemplate definitions.

    Templates are registered by name and can be resolved into concrete
    :class:`Step` instances via :meth:`expand`, which handles team
    reference expansion through the provided TeamRegistry.

    Args:
        team_registry: The TeamRegistry to use for validating team
            references in templates.
        templates: Optional initial list of templates to register.

    Usage::

        registry = StepTemplateRegistry(team_registry=team_registry)
        registry.register(template)
        step = registry.expand("comprehensive-arch-review", {"output": [...]})
    """

    def __init__(
        self,
        team_registry: TeamRegistry | None = None,
        templates: list[StepTemplate] | None = None,
    ) -> None:
        self._team_registry = team_registry
        self._templates: dict[str, StepTemplate] = {}
        if templates:
            for template in templates:
                self.register(template)

    def register(self, template: StepTemplate) -> None:
        """Register a template.

        Validates that if the template references a team (``team:``
        field), the team exists in the TeamRegistry.

        Args:
            template: The StepTemplate to register.

        Raises:
            UnknownTemplateError: If a template with the same name is
                already registered.
            UnknownTeamError: If the template references a team that
                does not exist in the TeamRegistry.
        """
        name = template.name
        if name in self._templates:
            raise UnknownTemplateError(
                f"Template '{name}' is already registered"
            )

        # Validate team reference at registration time
        if template.team is not None and self._team_registry is not None:
            self._team_registry.resolve(template.team)

        self._templates[name] = template

    def resolve(self, name: str) -> StepTemplate:
        """Get a template by name.

        Args:
            name: The template name to look up.

        Returns:
            The matching StepTemplate.

        Raises:
            UnknownTemplateError: If no template with the given name
                is registered.
        """
        if name not in self._templates:
            raise UnknownTemplateError(
                f"Template '{name}' not found in registry"
            )
        return self._templates[name]

    def expand(
        self,
        template_name: str,
        context: dict | None = None,
    ) -> Step:
        """Expand a template into a concrete Step instance.

        Resolves the template, validates that any team reference exists
        in the TeamRegistry, and produces a :class:`Step` with the
        template's configuration.

        Args:
            template_name: Name of the template to expand.
            context: Optional dict with context values (currently
                unused, reserved for future dynamic injection).

        Returns:
            A concrete :class:`Step` instance.

        Raises:
            UnknownTemplateError: If the template is not found.
            UnknownTeamError: If the template references a team that
                does not exist in the TeamRegistry.
        """
        template = self.resolve(template_name)
        context = context or {}

        # If team-based, validate the team still exists
        if template.team is not None and self._team_registry is not None:
            self._team_registry.resolve(template.team)

        return Step(
            agents=template.agents,
            team=template.team,
            loop=None,
            phase=None,
            parallel=template.parallel,
            lead=None,
            serial_lead=None,
            input=template.input,
            output=template.output,
            role=template.role,
            action=None,
            auto=None,
        )

    def list_templates(self) -> list[str]:
        """List all registered template names.

        Returns:
            Sorted list of template names.
        """
        return sorted(self._templates.keys())

    @property
    def count(self) -> int:
        """Return the number of registered templates."""
        return len(self._templates)
