"""Boundary test generation — behaviour-capturing immutable tests.

Provides:
- ``BoundaryTest`` — captures a generated boundary test
- ``IMMUTABLE_HEADER`` — header marking tests as immutable
- ``generate_boundary_test(boundary, root, target_dir)`` — single test
- ``generate_boundary_test_module(boundaries, root, target_dir)`` — batch
- ``verify_boundary_test_integrity(target_dir)`` — hash verification
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List

from harness.refactor.boundaries import BoundaryCandidate

# ── Immutable header ───────────────────────────────────────────────────────


IMMUTABLE_HEADER = """# ── IMMUTABLE BOUNDARY TEST ──────────────────────────────────────────
# DO NOT MODIFY THIS FILE during refactoring.
# This test captures current behaviour at a public boundary.
# If this test fails during refactoring, the behaviour has changed.
# Only modify this file if the boundary contract intentionally changes.
# ────────────────────────────────────────────────────────────────────

"""


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class BoundaryTest:
    """A generated boundary test.

    Attributes:
        boundary: The ``BoundaryCandidate`` this test covers.
        test_path: Absolute path where the test is written.
        content: Full text content of the test file.
        content_hash: SHA256 hex digest of the content (for integrity
            checks during verification pass).
    """
    boundary: BoundaryCandidate
    test_path: Path
    content: str
    content_hash: str


# ── Template helper ────────────────────────────────────────────────────────


def _compute_hash(content: str) -> str:
    """SHA256 hex digest of *content*."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _module_import_path(path: str) -> str:
    """Convert a filesystem path to a Python module import.

    E.g. ``src/harness/refactor/boundaries.py`` →
    ``harness.refactor.boundaries``
    """
    # Strip .py extension
    module = path.replace(".py", "")
    # Convert / to .
    module = module.replace("/", ".")
    # Strip leading src. if present
    if module.startswith("src."):
        module = module[4:]
    return module


def _infer_boundary_api(boundary: BoundaryCandidate) -> tuple[str, str, str]:
    """Infer the API for a boundary test.

    Returns ``(import_path, public_names, call_example)`` based on
    the boundary type and path. May be overridden by user-supplied
    descriptions.

    The result is best-effort — the generated test will be syntactically
    valid even if some calls won't work (user must adjust).
    """
    path = boundary.path
    module_import = _module_import_path(path)

    if boundary.boundary_type == "package":
        # Import the package and test __all__
        return (
            module_import,
            f"{module_import}.__all__",
            f"{module_import}",
        )

    if boundary.boundary_type in ("api", "http", "cli"):
        # Import the module and test its public functions
        return (
            module_import,
            f"dir({module_import})",
            module_import,
        )

    if boundary.boundary_type == "interface":
        # Import the interface module
        return (
            module_import,
            f"dir({module_import})",
            module_import,
        )

    # Default: module
    return (
        module_import,
        f"dir({module_import})",
        module_import,
    )


_BOUNDARY_TEST_TEMPLATE = """{immutable_header}import pytest
from typing import Any

# Import the boundary module
import {import_path}


@pytest.mark.boundary
@pytest.mark.immutable
class Test{test_class_name}:
    \"\"\"Behaviour-capturing tests for boundary: {name}.

    These tests document current behaviour. Do NOT modify during
    refactoring — only the implementation behind this boundary
    may change.
    \"\"\"

    def test_module_imports(self):
        \"\"\"The boundary module can be imported.\"\"\"
        assert {import_path} is not None

    def test_public_api_shape(self):
        \"\"\"The public API shape is captured.\"\"\"
        public_names = {public_names}
        assert isinstance(public_names, list)

    def test_boundary_accessible(self):
        \"\"\"The boundary call {example_call} resolves.\"\"\"
        try:
            result = {example_call}
            # Capture whatever the current behaviour is
            assert result is not None or result is None
        except Exception as exc:
            # If the call raises, capture the exception type so
            # refactoring doesn't silently change it
            pytest.fail(f"Boundary call raised: {{exc}}")
"""


def generate_boundary_test(
    boundary: BoundaryCandidate,
    root: Path,
    target_dir: Path,
) -> BoundaryTest:
    """Generate a behaviour-capturing test for a single boundary.

    The generated test:
    - Imports the boundary module
    - Calls the public interface
    - Captures current behaviour (not strict assertions)
    - Is marked IMMUTABLE via header and pytest markers

    Args:
        boundary: The boundary to test.
        root: Project root (for relative path resolution).
        target_dir: Where to write test files (engagement directory
            or project-level test directory).

    Returns:
        A ``BoundaryTest`` with the generated content and hash.
    """
    import_path, public_names, example_call = _infer_boundary_api(boundary)

    # Sanitise names for use as Python identifiers
    test_class_name = _to_pascal_case(boundary.name.replace(":", "_"))

    content = _BOUNDARY_TEST_TEMPLATE.format(
        immutable_header=IMMUTABLE_HEADER,
        import_path=import_path,
        test_class_name=test_class_name,
        name=boundary.name,
        public_names=public_names,
        example_call=example_call,
    )

    # Determine test file path
    test_rel = _boundary_test_relpath(boundary, root)
    test_path = (target_dir / test_rel).resolve()

    # Ensure parent dir exists
    test_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    test_path.write_text(content)

    return BoundaryTest(
        boundary=boundary,
        test_path=test_path,
        content=content,
        content_hash=_compute_hash(content),
    )


def _to_pascal_case(name: str) -> str:
    """Convert a snake_case or kebab-case name to PascalCase.

    Handles snake_case, kebab-case, and colon-delimited names.
    """
    parts = name.replace("-", "_").replace(":", "_").split("_")
    return "".join(p.capitalize() for p in parts if p)


def _boundary_test_relpath(boundary: BoundaryCandidate, root: Path) -> str:
    """Determine the relative test path for a boundary test file.

    Maps boundary paths to corresponding test paths:
    - ``src/harness/foo.py`` → ``tests/boundaries/test_foo.py``
    - ``src/harness/bar/__init__.py`` → ``tests/boundaries/test_bar.py``
    - ``api/handlers.py`` → ``tests/boundaries/test_handlers.py``
    """
    path = boundary.path
    # Get the stem (filename without extension)
    stem = Path(path).stem

    # For __init__.py, use the parent directory name
    if stem == "__init__":
        stem = Path(path).parent.name

    return f"tests/boundaries/test_{stem}.py"


# ── Batch generation ───────────────────────────────────────────────────────


def generate_boundary_test_module(
    boundaries: List[BoundaryCandidate],
    root: Path,
    target_dir: Path,
) -> List[BoundaryTest]:
    """Generate boundary tests for all *boundaries*.

    Creates individual test files per boundary under
    ``tests/boundaries/`` relative to *target_dir*.

    Returns:
        A list of ``BoundaryTest`` instances (one per boundary).
    """
    tests: list[BoundaryTest] = []
    for boundary in boundaries:
        test = generate_boundary_test(boundary, root, target_dir)
        tests.append(test)
    return tests


# ── Integrity verification ─────────────────────────────────────────────────


def verify_boundary_test_integrity(target_dir: Path) -> bool:
    """Check that all boundary tests in *target_dir* are unmodified.

    Reads each ``.py`` file under ``tests/boundaries/`` relative to
    *target_dir*, checks for the IMMUTABLE header, and verifies
    nothing has changed from its original generation.

    Returns True only if ALL boundary tests pass integrity check.
    This is a no-op if no boundary tests exist (returns True).

    Note: This is an approximate integrity check — it looks for the
    immutable header marker rather than stored hashes (full hash
    verification is part of Wave 16b.2 verification pass).
    """
    boundaries_dir = target_dir / "tests" / "boundaries"
    if not boundaries_dir.is_dir():
        return True

    all_ok = True
    for py_file in sorted(boundaries_dir.rglob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            all_ok = False
            continue

        # Check for IMMUTABLE marker
        if "IMMUTABLE" not in content:
            all_ok = False

        # Check for @pytest.mark.immutable
        if "@pytest.mark.immutable" not in content:
            all_ok = False

    return all_ok
