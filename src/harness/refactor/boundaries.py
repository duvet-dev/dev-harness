"""Boundary identification — structural scanning and user confirmation.

Provides:
- ``BoundaryCandidate`` — an identified application boundary
- ``scan_boundary_candidates(root)`` — scan a project for boundaries
- ``present_and_confirm_boundaries(candidates)`` — interactive confirmation
- ``register_boundaries(boundaries, target_dir)`` — persist to YAML
- ``read_boundary_registration(target_dir)`` — load from YAML
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class BoundaryCandidate:
    """A single application boundary identified during scanning.

    Attributes:
        name: Short label for the boundary (e.g. "auth-api").
        path: Relative path to the boundary file/directory.
        boundary_type: One of "module", "api", "cli", "http", "package",
            "interface", "protocol".
        description: Human-readable explanation.
    """
    name: str
    path: str
    boundary_type: str
    description: str = ""


# ── Known boundary marker patterns ─────────────────────────────────────────

# Subdirectory names that indicate API/public surfaces
_API_DIR_NAMES = frozenset({"api", "public", "client", "handlers", "routes",
                             "controllers", "resources", "endpoints"})

# Filenames that indicate interface/contract definitions
_INTERFACE_FILE_NAMES = frozenset({"interface.py", "interfaces.py", "ports.py",
                                    "protocol.py", "protocols.py", "contract.py",
                                    "contracts.py", "abc.py", "abstract.py"})

# File patterns for CLI entry points (files that define click/argparse/typer usage)
_CLI_MARKERS = {"import click", "from click", "import argparse",
                "from argparse", "import typer", "from typer"}

# HTTP handler markers
_HTTP_MARKERS = {"@app.route", "def get(", "def post(", "def put(",
                 "def delete(", "def patch(", "from fastapi",
                 "from flask", "from aiohttp", "@router."}

# Top-level package boundary: check for __init__.py with __all__
_PACKAGE_BOUNDARY_MARKERS = {"__all__", "__version__", "get_version"}


def scan_boundary_candidates(root: Path) -> List[BoundaryCandidate]:
    """Scan *root* for structural boundary candidates.

    Uses these heuristics:
    1. **Package boundaries** — directories with ``__init__.py`` containing
       ``__all__`` or public API exports.
    2. **API surface directories** — subdirs named ``api/``, ``public/``,
       ``client/``, etc.
    3. **Interface/protocol files** — files named ``interface.py``, ``ports.py``,
       ``protocol.py``, etc.
    4. **CLI entry points** — files containing ``import click`` / ``import
       argparse`` / ``import typer``.
    5. **HTTP handlers** — files containing route definitions.

    Returns a list of ``BoundaryCandidate``, deduplicated by path.
    Returns an empty list for empty or non-Python projects.
    """
    candidates: list[BoundaryCandidate] = []
    seen_paths: set[str] = set()

    if not root.is_dir():
        return []

    src_dirs = _find_source_dirs(root)

    # Heuristic 1: Package boundaries (__init__.py with __all__)
    for src_dir in src_dirs:
        for init in src_dir.rglob("__init__.py"):
            rel = init.relative_to(root)
            parent_dir = init.parent
            try:
                content = init.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if any(marker in content for marker in _PACKAGE_BOUNDARY_MARKERS):
                name = parent_dir.name
                if rel.as_posix() not in seen_paths:
                    seen_paths.add(rel.as_posix())
                    candidates.append(BoundaryCandidate(
                        name=f"package:{name}",
                        path=rel.as_posix(),
                        boundary_type="package",
                        description=f"Package boundary at {rel.parent} with public API exports",
                    ))

    # Heuristic 2: API surface directories
    for src_dir in src_dirs:
        for subdir in src_dir.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name in _API_DIR_NAMES:
                rel = subdir.relative_to(root)
                if rel.as_posix() not in seen_paths:
                    seen_paths.add(rel.as_posix())
                    boundary_type = "api" if subdir.name in {"api", "public"} else "module"
                    name = subdir.name
                    candidates.append(BoundaryCandidate(
                        name=f"{boundary_type}:{name}",
                        path=rel.as_posix(),
                        boundary_type=boundary_type,
                        description=f"{boundary_type.title()} surface at {rel.as_posix()}",
                    ))

    # Heuristic 3: Interface/protocol files
    for src_dir in src_dirs:
        for f in src_dir.rglob("*.py"):
            if f.name in _INTERFACE_FILE_NAMES:
                rel = f.relative_to(root)
                if rel.as_posix() not in seen_paths:
                    seen_paths.add(rel.as_posix())
                    candidates.append(BoundaryCandidate(
                        name=f"interface:{f.stem}",
                        path=rel.as_posix(),
                        boundary_type="interface",
                        description=f"Interface definition at {rel.as_posix()}",
                    ))

    # Heuristic 4: CLI entry points
    for src_dir in src_dirs:
        for f in src_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if any(marker in content for marker in _CLI_MARKERS):
                rel = f.relative_to(root)
                if rel.as_posix() not in seen_paths:
                    seen_paths.add(rel.as_posix())
                    candidates.append(BoundaryCandidate(
                        name=f"cli:{f.stem}",
                        path=rel.as_posix(),
                        boundary_type="cli",
                        description=f"CLI entry point at {rel.as_posix()}",
                    ))

    # Heuristic 5: HTTP handlers
    for src_dir in src_dirs:
        for f in src_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if any(marker in content for marker in _HTTP_MARKERS):
                rel = f.relative_to(root)
                if rel.as_posix() not in seen_paths:
                    seen_paths.add(rel.as_posix())
                    candidates.append(BoundaryCandidate(
                        name=f"http:{f.stem}",
                        path=rel.as_posix(),
                        boundary_type="http",
                        description=f"HTTP handler at {rel.as_posix()}",
                    ))

    # Sort by path for deterministic output
    candidates.sort(key=lambda c: c.path)
    return candidates


def _find_source_dirs(root: Path) -> list[Path]:
    """Find the source directories to scan for boundaries.

    Looks for a top-level ``src/`` directory first. If none found,
    returns the root itself.
    """
    src_dir = root / "src"
    if src_dir.is_dir():
        # Scan all top-level packages under src/
        dirs = [src_dir] + [d for d in src_dir.iterdir() if d.is_dir()]
        return dirs
    return [root]


def present_and_confirm_boundaries(
    candidates: List[BoundaryCandidate],
) -> List[BoundaryCandidate]:
    """Present inferred boundaries to the user and let them confirm.

    Prints the candidates grouped by type, then prompts for:
    - Confirmation of the full list
    - Removal of individual boundaries by number
    - Adding custom boundaries

    Returns the final confirmed list of boundaries.

    If there are no candidates, still prompts for manual entry.
    """
    confirmed: list[BoundaryCandidate] = []

    if candidates:
        print("\n── Inferred Application Boundaries ──")
        print(f"  Found {len(candidates)} potential boundary candidate(s).\n")

        # Group by type
        by_type: dict[str, list[BoundaryCandidate]] = {}
        for c in candidates:
            by_type.setdefault(c.boundary_type, []).append(c)

        for btype in ("package", "api", "interface", "cli", "http", "module"):
            group = by_type.get(btype, [])
            if not group:
                continue
            print(f"  [{btype.upper()}]")
            for c in group:
                print(f"    {c.name:35s} {c.path}")
            print()

        # Ask about the full list

        while True:
            choice = input("\nAccept all inferred boundaries? [Y/n] ").strip().lower()
            if choice in ("", "y", "yes"):
                confirmed = list(candidates)
                break
            elif choice in ("n", "no"):
                confirmed = _interactive_select(candidates)
                break
            print("Please answer Y or n.")
    else:
        print("\nNo boundaries automatically inferred from project structure.")
        confirmed = _interactive_select([])

    # Allow adding custom boundaries
    _interactive_add(confirmed)

    # Deduplicate by path
    seen: set[str] = set()
    deduped: list[BoundaryCandidate] = []
    for c in confirmed:
        if c.path not in seen:
            seen.add(c.path)
            deduped.append(c)

    print(f"\n  ✅ Confirmed {len(deduped)} boundary(ies).")
    return deduped


def _interactive_select(candidates: list[BoundaryCandidate]) -> list[BoundaryCandidate]:
    """Let the user interactively select which boundaries to keep."""
    print("\n  Select boundaries to KEEP (by number, comma-separated):")
    for i, c in enumerate(candidates, 1):
        print(f"    {i:2d}. [{c.boundary_type}] {c.name:30s} {c.path}")
    print(f"    {len(candidates) + 1:2d}. Keep none")

    try:
        raw = input("  Enter numbers: ").strip()
        if not raw:
            return list(candidates)
        indices = [int(x.strip()) for x in raw.split(",") if x.strip()]
        selected = []
        for idx in indices:
            if 1 <= idx <= len(candidates):
                selected.append(candidates[idx - 1])
        return selected
    except (ValueError, EOFError):
        return list(candidates)


def _interactive_add(confirmed: list[BoundaryCandidate]) -> None:
    """Prompt the user to add custom boundaries."""

    print("\n  Add custom boundaries? Enter details or leave blank to skip.")

    while True:
        name = input("    Name (or blank to finish): ").strip()
        if not name:
            break

        path = input("    Path (relative to project root): ").strip()
        if not path:
            print("    Skipped (no path).")
            continue

        btype = input("    Type (module/api/cli/http/package/interface/protocol): ").strip()
        if not btype:
            btype = "module"

        desc = input("    Description (optional): ").strip()

        confirmed.append(BoundaryCandidate(
            name=name,
            path=path,
            boundary_type=btype,
            description=desc,
        ))
        print(f"    ✅ Added boundary: {name} ({path})")


def register_boundaries(
    boundaries: List[BoundaryCandidate],
    target_dir: Path,
) -> Path:
    """Write confirmed boundaries to ``.harness/boundaries.yaml``.

    *target_dir* should be the engagement directory
    (``.harness/engagements/<slug>/``) or project root.

    Returns the path to the written file.
    """
    import yaml

    data = {
        "version": 1,
        "boundaries": [
            {
                "name": b.name,
                "path": b.path,
                "type": b.boundary_type,
                "description": b.description,
            }
            for b in boundaries
        ],
    }

    out_path = target_dir / "boundaries.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return out_path


def read_boundary_registration(
    target_dir: Path,
) -> List[BoundaryCandidate]:
    """Read boundaries from ``.harness/boundaries.yaml``.

    Returns an empty list if the file doesn't exist or is malformed.
    """
    import yaml

    path = target_dir / "boundaries.yaml"
    if not path.is_file():
        return []

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return []

    boundaries = data.get("boundaries", [])
    if not isinstance(boundaries, list):
        return []

    result: list[BoundaryCandidate] = []
    for entry in boundaries:
        if not isinstance(entry, dict):
            continue
        try:
            result.append(BoundaryCandidate(
                name=str(entry.get("name", "")),
                path=str(entry.get("path", "")),
                boundary_type=str(entry.get("type", "module")),
                description=str(entry.get("description", "")),
            ))
        except Exception:
            continue

    return result
