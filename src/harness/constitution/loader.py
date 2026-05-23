"""Constitution loader — YAML read/write, scaffolding, and validation.

Public API
----------
- ``load(path)``        — read a YAML file and return a ``Constitution``.
- ``write(constitution, path)`` — serialise a ``Constitution`` to YAML (idempotent).
- ``scaffold(name, project, path, overrides)`` — generate from template + overrides.
- ``validate(constitution)`` — structural validation; returns warning list.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from harness.constitution.models import (
    Constitution,
    ConstitutionError,
)
from harness.constitution.templates.template_registry import (
    get_template,
    merge_overrides,
)

# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _atomic_write(path: Path, content: bytes) -> None:
    """Write *content* to *path* atomically via a temp file + rename."""
    import tempfile

    dirname = path.parent
    dirname.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(dirname),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load(path: Path) -> Constitution:
    """Read a ``constitution.yaml`` file and return a validated ``Constitution``.

    Parameters
    ----------
    path:
        Path to an existing YAML file on disk.

    Returns
    -------
    Constitution

    Raises
    ------
    ConstitutionError
        If the file does not exist, contains malformed YAML, or is missing
        required fields (e.g. ``project.name``).
    """
    if not path.exists():
        raise ConstitutionError(f"Constitution file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] | None = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConstitutionError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConstitutionError(
            f"Expected a YAML mapping at root of {path}, got {type(raw).__name__}"
        )

    return Constitution.from_dict(raw)


def write(constitution: Constitution, path: Path, *, atomic: bool = True) -> None:
    """Serialise *constitution* to YAML on disk.  Idempotent.

    The output mirrors ``constitution.to_dict()`` — default-valued fields are
    omitted for a clean, minimal YAML file.

    Parameters
    ----------
    constitution:
        The ``Constitution`` instance to serialise.
    path:
        Destination file path (parent directory must exist).
    atomic:
        If ``True`` (default), write to a temporary file then rename —
        prevents partial writes.
    """
    data = constitution.to_dict()
    yaml_bytes = yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        encoding="utf-8",
    )

    if atomic:
        _atomic_write(path, yaml_bytes)
    else:
        path.write_bytes(yaml_bytes)


def scaffold(
    template_name: str,
    project_name: str,
    path: Path,
    overrides: dict[str, Any] | None = None,
) -> Constitution:
    """Generate a new constitution from a template and write it to *path*.

    Steps:
    1. Load the named template from the registry.
    2. Set ``project.name`` to *project_name*.
    3. Deep-merge any *overrides* on top.
    4. Construct a ``Constitution`` from the merged data.
    5. Write the result to *path* (YAML, idempotent).
    6. Return the ``Constitution``.

    Parameters
    ----------
    template_name:
        Name of a registered template (e.g. ``"backend-service"``).
    project_name:
        Value for ``project.name`` — overrides the template default.
    path:
        Destination file path for the generated YAML.
    overrides:
        Optional nested dict of values to deep-merge into the template.
        Example: ``{"project": {"description": "My custom thing"}}``.

    Returns
    -------
    Constitution

    Raises
    ------
    KeyError
        If *template_name* is not registered.
    ConstitutionError
        If the merged data is structurally invalid.
    """
    data = get_template(template_name)
    data["project"]["name"] = project_name

    if overrides:
        merge_overrides(data, overrides)

    constitution = Constitution.from_dict(data)
    write(constitution, path)
    return constitution


def validate(constitution: Constitution) -> list[str]:
    """Structural validation of a ``Constitution``.

    Checks performed:

    - ``project.name`` is non-empty.
    - ``project.template`` is non-empty.
    - ``gates.default_mode`` is one of ``"wild"``, ``"auto"``, ``"full"``.
    - ``agents`` have unique names.
    - ``agents`` phases are non-empty.
    - ``coding.backends`` have non-empty names.

    Returns a list of warning/error strings.  An empty list means *valid*.
    """
    warnings: list[str] = []

    # -- project ---------------------------------------------------------------
    if not constitution.project.name:
        warnings.append("project.name is empty")
    if not constitution.project.template:
        warnings.append("project.template is empty")

    # -- gates -----------------------------------------------------------------
    valid_modes = {"wild", "auto", "full"}
    if constitution.gates.default_mode not in valid_modes:
        warnings.append(
            f"gates.default_mode is {constitution.gates.default_mode!r}; "
            f"expected one of {valid_modes}"
        )

    # -- agents ----------------------------------------------------------------
    seen_names: set[str] = set()
    for agent in constitution.agents:
        if not agent.name:
            warnings.append("agent entry has empty name")
        if agent.name in seen_names:
            warnings.append(f"duplicate agent name: {agent.name!r}")
        seen_names.add(agent.name)

        if not agent.phase:
            warnings.append(f"agent {agent.name!r} has empty phase")

    # -- coding backends -------------------------------------------------------
    seen_backends: set[str] = set()
    for backend in constitution.coding.backends:
        if not backend.name:
            warnings.append("backend entry has empty name")
        if backend.name in seen_backends:
            warnings.append(f"duplicate backend name: {backend.name!r}")
        seen_backends.add(backend.name)

    return warnings
