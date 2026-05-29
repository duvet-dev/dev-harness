"""In-memory data structures for a project constitution.

The constitution defines everything about how a project should be built —
philosophy, coding backends, quality gates, analysis triggers, and agent
phases.  All models are pure stdlib dataclasses with no runtime deps beyond
``typing``.
"""

from __future__ import annotations

import types as _types
import typing as _typing
from dataclasses import MISSING, dataclass, field, fields
from typing import Any


class ConstitutionError(Exception):
    """Raised when a constitution document fails to load or validate."""


# ──────────────────────────────────────────────
# Leaf types
# ──────────────────────────────────────────────


@dataclass
class ProjectInfo:
    """Top-level project identity."""

    name: str
    template: str
    description: str = ""


@dataclass
class PhilosophyConfig:
    """Architectural / philosophical constraints."""

    requires_ddd: bool = False
    requires_clean_architecture: bool = True
    requires_hexagonal: bool = True
    strict_deps: bool = True
    encoding_notes: str = ""


@dataclass
class GateConfig:
    """Quality-gate configuration."""

    default_mode: str = "auto"  # wild | auto | full
    available_modes: tuple[str, ...] = ("wild", "auto", "full")


@dataclass
class BackendDef:
    """A single coding backend (CLI, API, editor)."""

    name: str
    backend_type: str  # cli | api | editor
    command: str = ""
    provider: str = ""
    model: str = ""


@dataclass
class CodingConfig:
    """Which backend(s) the project uses for code generation."""

    default_backend: str = "custom-llm"
    backends: list[BackendDef] = field(default_factory=list)


@dataclass
class AnalysisConfig:
    """Triggers for fast scans and deeper analysis."""

    fast_scan_triggers: list[str] = field(
        default_factory=lambda: ["on_summary", "post_merge"]
    )


@dataclass
class BackendRef:
    """Reference to a provider backend with optional fallback chain."""

    backend_name: str
    """The provider name (e.g. ``deepseek``, ``openai``)."""

    model_key: str = "default"
    """Model key within that provider (e.g. ``default``, ``pro``)."""

    fallbacks: list[dict] = field(default_factory=list)
    """Optional fallback backends: each is ``{backend, model}``."""


@dataclass
class AgentDef:
    """Agent definition entry — name, phase, type, and backend selection."""

    name: str
    phase: str
    agent_type: str = "built-in"
    backend: str = ""
    """Provider name to use (e.g. ``deepseek``, ``openai``). If empty,
    the runner's default backend is used."""

    model: str = ""
    """Model key within the provider (e.g. ``default``, ``pro``,
    or a full model name). If empty, the provider's default model is used."""

    fallbacks: list[dict] = field(default_factory=list)
    """Optional fallback chain. Each entry is ``{backend: str, model: str}``.
    If the primary provider fails, fallbacks are tried in order."""


# ──────────────────────────────────────────────
# Session type + boundary enforcement models
# ──────────────────────────────────────────────


@dataclass
class SessionTypeConfig:
    """Configuration for a single session type.

    Attributes:
        enforce_boundary_tests:
            Whether to enforce boundary tests for this session type.
            If ``None``, inherits from the global
            ``boundary_test_enforcement_default``.
        guidance:
            Guidance text injected into planning agent prompts for
            this session type.
    """

    enforce_boundary_tests: bool | None = None
    guidance: str = ""


@dataclass
class BoundaryConfig:
    """Boundary test enforcement configuration (R20).

    Attributes:
        enforcement_default:
            Global default for boundary test enforcement (maps to
            ``boundary_test_enforcement_default`` in YAML).
            Per-session-type ``enforce_boundary_tests`` overrides this.
        session_types:
            Per-session-type configuration. Keys are session type
            names (e.g. ``"greenfield"``, ``"refactoring"``,
            ``"get-well"``).
    """

    enforcement_default: bool = True
    session_types: dict[str, SessionTypeConfig] = field(default_factory=dict)


# ──────────────────────────────────────────────
# Root document
# ──────────────────────────────────────────────


@dataclass
class Constitution:
    """Complete project constitution — the single source of truth."""

    project: ProjectInfo
    philosophy: PhilosophyConfig = field(default_factory=PhilosophyConfig)
    gates: GateConfig = field(default_factory=GateConfig)
    coding: CodingConfig = field(default_factory=CodingConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    agents: list[AgentDef] = field(default_factory=list)
    session_types: dict[str, SessionTypeConfig] = field(default_factory=dict)
    """Per-session-type configuration (backward-compat shortcut).
    Maps to ``session_types`` key in constitution YAML.
    When this is set, its values take priority over
    ``boundary.session_types``.
    """

    boundary: BoundaryConfig = field(default_factory=BoundaryConfig)
    """Boundary test enforcement configuration (R20).
    Maps to ``boundary`` key and top-level
    ``boundary_test_enforcement_default`` in constitution YAML.
    """

    # ── serialisation helpers ─────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain nested dict (suitable for YAML output)."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Constitution:
        """Deserialise from a dict (as loaded from YAML).

        Handles:
        - Top-level ``session_types: {name: {enforce: ..., guidance: ...}}``
        - Top-level ``boundary_test_enforcement_default: bool``
          (mapped to ``boundary.enforcement_default``)
        - New-style ``boundary: {enforcement_default: ..., session_types: ...}``
        """
        # Normalise: read legacy top-level fields into the boundary sub-object
        normalised = dict(data)

        # Extract top-level boundary_test_enforcement_default into boundary
        legacy_default = normalised.pop("boundary_test_enforcement_default", None)
        legacy_session_types = normalised.pop("session_types", None)

        boundary_data: dict[str, Any] = {}
        if "boundary" in normalised:
            b = normalised["boundary"]
            if isinstance(b, dict):
                boundary_data = dict(b)

        # Legacy top-level fields override sub-object fields
        if legacy_default is not None:
            boundary_data["enforcement_default"] = legacy_default
        if legacy_session_types is not None:
            # Merge session types from legacy location
            existing_st = boundary_data.get("session_types", {})
            if isinstance(existing_st, dict):
                merged = dict(existing_st)
            else:
                merged = {}
            if isinstance(legacy_session_types, dict):
                merged.update(legacy_session_types)
            boundary_data["session_types"] = merged

        if boundary_data:
            normalised["boundary"] = boundary_data
        else:
            normalised.pop("boundary", None)

        # Rebuild SessionTypeConfig for each entry
        if "boundary" in normalised and "session_types" in normalised.get("boundary", {}):
            sts = normalised["boundary"]["session_types"]
            if isinstance(sts, dict):
                rebuilt: dict[str, Any] = {}
                for key, val in sts.items():
                    if isinstance(val, dict):
                        rebuilt[key] = SessionTypeConfig(
                            enforce_boundary_tests=val.get("enforce_boundary_tests"),
                            guidance=val.get("guidance", ""),
                        )
                    elif isinstance(val, bool):
                        # Shorthand: ``session_types:
                        #   greenfield: false``
                        rebuilt[key] = SessionTypeConfig(
                            enforce_boundary_tests=val,
                        )
                    else:
                        rebuilt[key] = val
                normalised["boundary"]["session_types"] = rebuilt

        return _from_dict(cls, normalised)


# ──────────────────────────────────────────────
# Public factory
# ──────────────────────────────────────────────


def default_constitution(
    name: str = "my-project",
    template: str = "backend-service",
) -> Constitution:
    """Return a sensible default constitution for a new project."""
    return Constitution(
        project=ProjectInfo(name=name, template=template),
        philosophy=PhilosophyConfig(
            requires_ddd=False,
            requires_clean_architecture=True,
            requires_hexagonal=True,
            strict_deps=True,
            encoding_notes="",
        ),
        gates=GateConfig(
            default_mode="auto",
            available_modes=("wild", "auto", "full"),
        ),
        coding=CodingConfig(
            default_backend="custom-llm",
            backends=[
                BackendDef(
                    name="custom-llm",
                    backend_type="cli",
                    command="./llm/generate.sh",
                    provider="custom",
                    model="llama3",
                ),
            ],
        ),
        analysis=AnalysisConfig(
            fast_scan_triggers=["on_summary", "post_merge"],
        ),
        agents=[
            AgentDef(name="planner", phase="planning", agent_type="built-in"),
            AgentDef(name="coder", phase="implementation", agent_type="built-in"),
            AgentDef(name="reviewer", phase="review", agent_type="built-in"),
        ],
        boundary=BoundaryConfig(
            enforcement_default=True,
            session_types={
                "greenfield": SessionTypeConfig(
                    enforce_boundary_tests=False,
                    guidance="Build new features without backward compatibility constraints.",
                ),
                "refactoring": SessionTypeConfig(
                    enforce_boundary_tests=True,
                    guidance="Preserve existing interfaces. First wave must be boundary tests.",
                ),
                "get-well": SessionTypeConfig(
                    enforce_boundary_tests=True,
                    guidance="Fix broken tests first. Boundaries may be restructured with explicit override.",
                ),
            },
        ),
    )


# ──────────────────────────────────────────────
# Internal serialisation helpers
# ──────────────────────────────────────────────


def _to_dict(obj: Any) -> Any:
    """Recursively convert a dataclass tree to plain dicts / lists."""
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_to_dict(item) for item in obj)
    if hasattr(obj, "__dataclass_fields__"):
        result: dict[str, Any] = {}
        for f in fields(obj):  # type: ignore[arg-type]
            value = getattr(obj, f.name)
            # omit defaults-only fields for cleaner output
            if value == f.default or (
                f.default_factory is not MISSING
                and value == f.default_factory()
            ):
                continue
            result[f.name] = _to_dict(value)
        return result
    return obj


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    """Recursively reconstruct a dataclass tree from a plain dict."""
    # Resolve string annotations (``from __future__ import annotations``)
    hints = _typing.get_type_hints(cls)
    known_fields = {f.name: f for f in fields(cls)}  # type: ignore[arg-type]
    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        if key not in known_fields:
            raise ConstitutionError(f"Unknown field '{key}' for {cls.__name__}")
        resolved_type = hints.get(key, known_fields[key].type)
        kwargs[key] = _rebuild_field(resolved_type, value)

    # Infer missing required / optional fields
    for f in known_fields.values():
        if f.name not in kwargs:
            if f.default is not MISSING:
                kwargs[f.name] = f.default
            elif f.default_factory is not MISSING:
                kwargs[f.name] = f.default_factory()
            else:
                raise ConstitutionError(
                    f"Missing required field '{f.name}' for {cls.__name__}"
                )

    return cls(**kwargs)


def _rebuild_field(field_type: Any, value: Any) -> Any:
    """Rebuild a single field value, recursing into nested dataclasses."""
    origin = _typing.get_origin(field_type)

    if origin is list:
        args = _typing.get_args(field_type)
        inner = args[0] if args else Any
        return [_rebuild_field(inner, item) for item in value]

    if origin is tuple:
        args = _typing.get_args(field_type)
        inner = args[0] if args else Any
        return tuple(_rebuild_field(inner, item) for item in value)

    if origin is _typing.Union:
        # Union/Optional — pass through as-is
        return value

    if hasattr(field_type, "__origin__"):
        # handle UnionType from types module (PEP 604 | syntax)
        origin_t = field_type.__origin__
        _union_type = getattr(_types, 'UnionType', None)
        if origin_t is _typing.Union or (_union_type is not None and origin_t is _union_type):
            return value

    # Plain built-in type
    module = getattr(field_type, "__module__", "")
    if module == "builtins":
        return value

    # Nested dataclass
    if hasattr(field_type, "__dataclass_fields__"):
        return _from_dict(field_type, value)

    return value
