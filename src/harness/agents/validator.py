"""Fast, deterministic validator for agent outputs.

Checks agent output against OutputContract using filesystem operations only.
No LLM calls. No analysis suite dependency. Runs in <1s on any reasonable tree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.context import OutputContract


@dataclass
class ValidationResult:
    """The outcome of validating agent output against a contract.

    Attributes:
        passed: True if every check succeeded, False otherwise.
        findings: Human-readable descriptions of what was checked and the
            result. A finding may be positive (e.g. "file X matches pattern Y")
            or negative (e.g. "required file matching pattern Z not found").
    """

    passed: bool
    findings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Convenience: a ValidationResult is truthy when passed."""
        return self.passed


class SpecValidator:
    """Fast, deterministic validator for agent outputs.

    Validates files produced by an agent against an OutputContract.  All
    checks are filesystem-only — no imports from analysis or LLM packages.
    """

    _SIZE_KEYS = frozenset({"min_lines", "max_lines", "min_bytes", "max_bytes"})

    @staticmethod
    def validate(target_directory: Path, contract: OutputContract) -> ValidationResult:
        """Validate files in *target_directory* against *contract*.

        Checks performed in order:

        1. **Required file existence** — glob each pattern in
           ``contract.required_files`` relative to *target_directory*.  Any
           pattern that matches zero files is reported as a missing-file
           finding.

        2. **File size rules** — for each entry in ``contract.file_rules``,
           match the ``pattern`` key against files in *target_directory* and
           verify every matched file satisfies every size constraint present
           in the rule (``min_lines``, ``max_lines``, ``min_bytes``,
           ``max_bytes``).

        3. **Interface stub check** — if ``contract.validate_interface`` is
           ``True``, scan all ``.py`` files under *target_directory* for
           ``def `` and ``class `` tokens.  At least one function **or** class
           definition must exist.

        Returns:
            A :class:`ValidationResult` summarising pass/fail and all
            individual findings.
        """
        findings: list[str] = []
        all_passed = True

        # ---------------------------------------------------------------
        # 1. Required file existence
        # ---------------------------------------------------------------
        for pattern in contract.required_files:
            matches = sorted(target_directory.glob(pattern))
            if matches:
                names = ", ".join(str(m.relative_to(target_directory)) for m in matches)
                findings.append(f"REQUIRED FILE — pattern {pattern!r} matched: {names}")
            else:
                findings.append(
                    f"REQUIRED FILE — pattern {pattern!r} matched NO files"
                )
                all_passed = False

        # ---------------------------------------------------------------
        # 2. File size rules
        # ---------------------------------------------------------------
        for rule_idx, rule in enumerate(contract.file_rules):
            pattern = rule.get("pattern")
            if not pattern:
                findings.append(
                    f"FILE RULE #{rule_idx} — missing 'pattern' key, skipped"
                )
                continue

            matched_files = sorted(target_directory.glob(pattern))
            if not matched_files:
                findings.append(
                    f"FILE RULE #{rule_idx} — pattern {pattern!r} matched NO files, skipped"
                )
                continue

            for matched_file in matched_files:
                rule_passed = SpecValidator._check_file_against_rule(
                    matched_file, target_directory, rule, rule_idx, findings
                )
                if not rule_passed:
                    all_passed = False

        # ---------------------------------------------------------------
        # 3. Interface stub check
        # ---------------------------------------------------------------
        if contract.validate_interface:
            py_files = sorted(target_directory.rglob("*.py"))
            defs_found = 0
            class_found = 0

            for py_file in py_files:
                try:
                    text = py_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # Count function definitions that are syntactic (skip comments/strings)
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("def ") and stripped.endswith(":"):
                        defs_found += 1
                    elif stripped.startswith("class ") and stripped.endswith(":"):
                        class_found += 1

            total_defs = defs_found + class_found
            if total_defs > 0:
                findings.append(
                    f"INTERFACE STUBS — {defs_found} def(s) + "
                    f"{class_found} class(es) found across {len(py_files)} .py file(s)"
                )
            else:
                findings.append(
                    "INTERFACE STUBS — no function or class definitions found "
                    f"in {len(py_files)} .py file(s)"
                )
                all_passed = False

        return ValidationResult(passed=all_passed, findings=findings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_file_against_rule(
        file_path: Path,
        base_dir: Path,
        rule: dict[str, Any],
        rule_idx: int,
        findings: list[str],
    ) -> bool:
        """Check a single file against one file-rule dict.

        Returns True if all constraints pass, False otherwise.
        Appends findings to *findings* in-place.
        """
        rel = str(file_path.relative_to(base_dir))
        passed = True

        stat = file_path.stat()
        byte_size = stat.st_size

        try:
            with file_path.open("rb") as f:
                line_count = sum(1 for _ in f)
        except OSError:
            line_count = 0

        # Build a friendly key list for the finding preamble
        constrained = [k for k in rule if k in SpecValidator._SIZE_KEYS]
        preamble = f"FILE RULE #{rule_idx} — {rel}"

        if "min_lines" in rule:
            min_l = int(rule["min_lines"])
            if line_count < min_l:
                findings.append(
                    f"{preamble} — FAIL min_lines: {line_count} < {min_l}"
                )
                passed = False

        if "max_lines" in rule:
            max_l = int(rule["max_lines"])
            if line_count > max_l:
                findings.append(
                    f"{preamble} — FAIL max_lines: {line_count} > {max_l}"
                )
                passed = False

        if "min_bytes" in rule:
            min_b = int(rule["min_bytes"])
            if byte_size < min_b:
                findings.append(
                    f"{preamble} — FAIL min_bytes: {byte_size} < {min_b}"
                )
                passed = False

        if "max_bytes" in rule:
            max_b = int(rule["max_bytes"])
            if byte_size > max_b:
                findings.append(
                    f"{preamble} — FAIL max_bytes: {byte_size} > {max_b}"
                )
                passed = False

        if passed and constrained:
            bits = []
            if "min_lines" in rule:
                bits.append(f"lines={line_count} >= {rule['min_lines']}")
            if "max_lines" in rule:
                bits.append(f"lines={line_count} <= {rule['max_lines']}")
            if "min_bytes" in rule:
                bits.append(f"bytes={byte_size} >= {rule['min_bytes']}")
            if "max_bytes" in rule:
                bits.append(f"bytes={byte_size} <= {rule['max_bytes']}")
            findings.append(f"{preamble} — PASS ({', '.join(bits)})")

        return passed
