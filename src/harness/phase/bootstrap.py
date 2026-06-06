"""Phase Bootstrap — load phase definitions from config into Phase objects.

Provides ``bootstrap_phases()`` which reads ``.harness/phases.yaml``
(or falls back to an inline default set) and returns a list of
:class:`Phase <harness.phase.model.Phase>` objects ready for
registration on a :class:`PhaseOrchestrator`.

Template references in step definitions are expanded via
:class:`StepTemplateRegistry`.

See V7 §5.4 (PhaseOrchestrator), §7 (Config Schema), and
§10.5 (Step Templates) for the design.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from harness.artifact.types import ArtifactType
from harness.errors import UnknownTemplateError, StepMutualExclusionError
from harness.phase.model import ConvergenceConfig, LoopConfig, Phase, Step
from harness.phase.template_registry import StepTemplateRegistry

logger = logging.getLogger(__name__)

# ── Default phases (fallback when phases.yaml is absent) ──────────────

_DEFAULT_PHASES: list[dict[str, Any]] = [
    {
        "name": "discover",
        "lead_agent": "discovery-agent",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"agents": ["discovery-agent"], "output": "research-notes"},
            {"team": "discovery", "parallel": True, "output": "consolidated-findings"},
        ],
    },
    {
        "name": "design",
        "lead_agent": "design-coordinator",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"agents": ["architect"], "output": "architectural-overview"},
            {
                "team": "architecture",
                "parallel": True,
                "lead": "review-coordinator",
                "output": "consolidated-review",
            },
        ],
    },
    {
        "name": "build",
        "lead_agent": "coding-agent",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"team": "coding", "output": "implementation"},
            {"team": "testing", "input": "implementation", "output": "test-results"},
        ],
    },
    {
        "name": "review",
        "lead_agent": "review-coordinator",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"team": "review", "parallel": True, "output": "review-report"},
            {"team": "architecture", "output": "architectural-conformance"},
        ],
    },
    {
        "name": "validate",
        "lead_agent": "validation-agent",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"team": "validation", "output": "validation-report"},
            {
                "team": "architecture",
                "input": "validation-report",
                "output": "final-conformance",
            },
            {"agents": ["validation-agent"], "output": "sign-off"},
        ],
    },
    {
        "name": "deliver",
        "lead_agent": "coding-agent",
        "chat_agent": "technical-conversationalist",
        "steps": [
            {"agents": ["coding-agent"], "output": "release-notes"},
            {"agents": ["documentation-agent"], "output": "documentation"},
        ],
    },
]


def _convert_template_step(
    step_dict: dict[str, Any],
    template_registry: StepTemplateRegistry | None,
) -> Step:
    """Convert a step dict that uses ``template`` instead of inline fields.

    Expands the template reference via the registry and returns a
    concrete :class:`Step`.

    Args:
        step_dict: Dict with ``template`` key and optional override fields.
        template_registry: Registry to look up the template.

    Returns:
        Expanded :class:`Step` instance.

    Raises:
        UnknownTemplateError: If the template name is not registered.
    """
    template_name = step_dict["template"]
    if template_registry is None:
        raise UnknownTemplateError(
            f"Cannot expand template '{template_name}': "
            f"no StepTemplateRegistry provided"
        )
    return template_registry.expand(template_name, context=step_dict)


def _convert_inline_step(step_dict: dict[str, Any]) -> Step:
    """Convert an inline step dict to a :class:`Step` instance.

    Handles all four mutually exclusive step types:
      - ``agents`` → agent step
      - ``team`` → team step
      - ``loop`` → loop step
      - ``phase`` → phase-jump step

    Args:
        step_dict: Raw step definition from YAML.

    Returns:
        A concrete :class:`Step` instance.

    Raises:
        StepMutualExclusionError: If the step dict sets multiple or
            zero of the mutually exclusive fields.
    """
    # Determine which mutually exclusive field is set
    agents = step_dict.get("agents")
    team = step_dict.get("team")
    loop_raw = step_dict.get("loop")
    phase = step_dict.get("phase")
    template = step_dict.get("template")

    specified = sum(
        [
            agents is not None,
            team is not None,
            loop_raw is not None,
            phase is not None,
            template is not None,
        ]
    )
    if specified != 1:
        raise StepMutualExclusionError(
            f"Exactly one of 'agents', 'team', 'loop', 'phase', or "
            f"'template' must be specified. Found {specified} "
            f"(agents={agents}, team={team}, loop={loop_raw is not None}, "
            f"phase={phase}, template={template})"
        )

    # Parse input field (can be str or list)
    # Input values are free-form strings from config (like "implementation",
    # "test-results") — NOT validated against ArtifactType enum.
    # The v4 model change decoupled output names from ArtifactType;
    # input follows the same convention for config consistency.
    input_raw = step_dict.get("input")
    input_parsed: list[str] | None = None
    if input_raw is not None:
        if isinstance(input_raw, str):
            input_parsed = [input_raw]
        elif isinstance(input_raw, list):
            input_parsed = list(input_raw)

    # Parse output field (can be str or list)
    output = step_dict.get("output")

    # Parse loop config if present
    loop: LoopConfig | None = None
    if loop_raw is not None:
        convergence_raw = loop_raw.get("convergence")
        convergence = None
        if convergence_raw:
            convergence = ConvergenceConfig(
                strategy=convergence_raw.get("strategy", "gate_judgment"),
                max_iterations=convergence_raw.get("max_iterations", 3),
                on_timeout=convergence_raw.get("on_timeout", "best_effort"),
                gate_agent=convergence_raw.get("gate_agent"),
                test_command=convergence_raw.get("test_command", ""),
                convergence_keywords=convergence_raw.get("convergence_keywords"),
                test_output_path=convergence_raw.get(
                    "test_output_path", ".harness/test_output/latest.txt"
                ),
                architect_role=convergence_raw.get("architect_role", "architect"),
                critic_role=convergence_raw.get("critic_role", "critical-analyser"),
                architect_output_subdir=convergence_raw.get(
                    "architect_output_subdir", "design/"
                ),
                critic_output_subdir=convergence_raw.get(
                    "critic_output_subdir", "reviews/"
                ),
            )
        loop = LoopConfig(
            count=loop_raw.get("count", 1),
            convergence=convergence,
            description=loop_raw.get("description", ""),
        )

    return Step(
        agents=agents,
        team=team,
        loop=loop,
        phase=phase,
        parallel=step_dict.get("parallel", False),
        lead=step_dict.get("lead"),
        serial_lead=step_dict.get("serial_lead"),
        input=input_parsed,
        output=output,
        role=step_dict.get("role"),
        action=step_dict.get("action"),
        auto=step_dict.get("auto"),
        max_retries=step_dict.get("max_retries", 1),
    )


def _parse_phases_yaml(
    raw_phases: list[dict[str, Any]],
    template_registry: StepTemplateRegistry | None = None,
) -> list[Phase]:
    """Parse a list of raw phase dicts into :class:`Phase` objects.

    Iterates each phase definition, converting its steps and resolving
    template references.

    Args:
        raw_phases: List of phase dicts from YAML or defaults.
        template_registry: Optional registry for template expansion.

    Returns:
        List of :class:`Phase` instances.
    """
    phases: list[Phase] = []

    for phase_dict in raw_phases:
        name = phase_dict["name"]
        lead_agent = phase_dict.get("lead_agent", "coding-agent")
        chat_agent = phase_dict.get("chat_agent", "technical-conversationalist")
        reentry = phase_dict.get("reentry")

        raw_steps = phase_dict.get("steps", [])
        steps: list[Step] = []

        for step_dict in raw_steps:
            if "template" in step_dict:
                step = _convert_template_step(step_dict, template_registry)
            else:
                step = _convert_inline_step(step_dict)
            steps.append(step)

        phases.append(
            Phase(
                name=name,
                lead_agent=lead_agent,
                chat_agent=chat_agent,
                steps=steps,
                reentry=reentry,
            )
        )

    return phases


def _load_yaml_phases(
    phases_path: Path,
) -> list[dict[str, Any]] | None:
    """Load phase definitions from a YAML file.

    Args:
        phases_path: Path to the YAML file.

    Returns:
        List of raw phase dicts, or None if the file doesn't exist
        or is empty/malformed.
    """
    if not phases_path.exists():
        logger.debug(
            "bootstrap_phases — phases.yaml not found at %s, "
            "falling back to defaults",
            phases_path,
        )
        return None

    try:
        with open(phases_path, "r") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        logger.warning(
            "bootstrap_phases — failed to load phases.yaml: %s, "
            "falling back to defaults",
            exc,
        )
        return None

    if not data or "phases" not in data:
        logger.debug(
            "bootstrap_phases — phases.yaml has no 'phases' key, "
            "falling back to defaults"
        )
        return None

    raw = data["phases"]
    if not isinstance(raw, list) or len(raw) == 0:
        logger.debug(
            "bootstrap_phases — phases.yaml 'phases' is empty, "
            "falling back to defaults"
        )
        return None

    return raw


def _load_templates_yaml(
    templates_path: Path,
    team_registry: Any = None,
) -> list[Any] | None:
    """Load step template definitions from a YAML file.

    Args:
        templates_path: Path to step_templates.yaml.
        team_registry: Optional TeamRegistry for validation.

    Returns:
        List of StepTemplate objects, or None if file doesn't exist.
    """
    if not templates_path.exists():
        return None

    from harness.phase.template import StepTemplate

    try:
        with open(templates_path, "r") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return None

    if not data or "step_templates" not in data:
        return None

    raw = data["step_templates"]
    if not isinstance(raw, list):
        return None

    templates: list[StepTemplate] = []
    for entry in raw:
        loop_raw = entry.get("loop")
        loop = None
        sub_steps = []
        if loop_raw:
            convergence_raw = loop_raw.get("convergence")
            convergence = None
            if convergence_raw:
                convergence = ConvergenceConfig(
                    strategy=convergence_raw.get("strategy", "gate_judgment"),
                    max_iterations=convergence_raw.get("max_iterations", 3),
                    on_timeout=convergence_raw.get("on_timeout", "best_effort"),
                    gate_agent=convergence_raw.get("gate_agent"),
                    test_command=convergence_raw.get("test_command", ""),
                    convergence_keywords=convergence_raw.get("convergence_keywords"),
                    test_output_path=convergence_raw.get(
                        "test_output_path", ".harness/test_output/latest.txt"
                    ),
                )
            loop = LoopConfig(
                count=loop_raw.get("count", 1),
                convergence=convergence,
                description=loop_raw.get("description", ""),
            )
            if loop_raw.get("steps"):
                for s in loop_raw["steps"]:
                    sub_steps.append(_convert_inline_step(s))

        input_raw = entry.get("input")
        input_parsed = None
        if input_raw is not None:
            if isinstance(input_raw, str):
                input_parsed = [input_raw]
            elif isinstance(input_raw, list):
                input_parsed = list(input_raw)

        output_raw = entry.get("output")

        template = StepTemplate(
            name=entry["name"],
            team=entry.get("team"),
            agents=entry.get("agents"),
            output=output_raw,
            parallel=entry.get("parallel", False),
            role=entry.get("role"),
            input=input_parsed,
            description=entry.get("description"),
            loop=loop,
            steps=sub_steps,
        )
        templates.append(template)

    return templates


def bootstrap_phases(
    template_registry: StepTemplateRegistry | None = None,
    phases_path: Path | None = None,
    templates_path: Path | None = None,
) -> list[Phase]:
    """Load phase definitions from config and return :class:`Phase` objects.

    Loads ``.harness/phases.yaml`` if it exists, otherwise falls back
    to a built-in default set of phase definitions.

    If a :class:`StepTemplateRegistry` is provided and any step in a
    phase references a template name (via ``template:`` key), the
    template will be expanded into concrete step fields.

    Args:
        template_registry: Optional registry for template expansion.
            If None, template references in phases will raise
            :class:`UnknownTemplateError`.
        phases_path: Path to ``phases.yaml``. If None, resolves to
            ``.harness/phases.yaml`` in the current working directory.
        templates_path: Path to ``step_templates.yaml``. If provided,
            templates from this file are loaded into the registry
            (if a registry is given) before phases are parsed.

    Returns:
        List of :class:`Phase` objects ready for registration on a
        :class:`PhaseOrchestrator`.

    Raises:
        UnknownTemplateError: If a step references a template that
            is not registered.
        StepMutualExclusionError: If a step definition violates the
            mutual exclusivity rule.
    """
    # Resolve default paths
    if phases_path is None:
        harness_dir = Path.cwd() / ".harness"
        phases_path = harness_dir / "phases.yaml"

    # Load templates into registry if requested
    if templates_path is None and template_registry is not None:
        harness_dir = Path.cwd() / ".harness"
        templates_path = harness_dir / "step_templates.yaml"

    if templates_path is not None and template_registry is not None:
        raw_templates = _load_templates_yaml(templates_path)
        if raw_templates:
            for tpl in raw_templates:
                try:
                    template_registry.register(tpl)
                except Exception:
                    logger.debug(
                        "bootstrap_phases — skipped template '%s' "
                        "(already registered or invalid)",
                        tpl.name,
                    )

    # Load phases
    raw_phases = _load_yaml_phases(phases_path)

    if raw_phases is None:
        # Fall back to inline defaults
        raw_phases = _DEFAULT_PHASES
        logger.debug(
            "bootstrap_phases — using %d built-in default phases",
            len(raw_phases),
        )

    return _parse_phases_yaml(raw_phases, template_registry)


def bootstrap_and_register(
    orchestrator: Any,
    template_registry: StepTemplateRegistry | None = None,
    phases_path: Path | None = None,
    templates_path: Path | None = None,
) -> None:
    """Bootstrap phases and register them on a PhaseOrchestrator.

    Convenience wrapper that calls :func:`bootstrap_phases` and then
    calls ``orchestrator.register_phases()`` with the result.

    This is a synchronous operation — phase objects are data-only
    and registration is purely structural.

    Args:
        orchestrator: A :class:`PhaseOrchestrator` instance with a
            ``register_phases()`` method.
        template_registry: Optional :class:`StepTemplateRegistry`.
        phases_path: Optional path to ``phases.yaml``.
        templates_path: Optional path to ``step_templates.yaml``.
    """
    phases = bootstrap_phases(
        template_registry=template_registry,
        phases_path=phases_path,
        templates_path=templates_path,
    )
    orchestrator.register_phases(phases)
    logger.info(
        "bootstrap_and_register — registered %d phases on orchestrator",
        len(phases),
    )
