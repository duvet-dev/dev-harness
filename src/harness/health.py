"""Harness health and configuration validation.

Provides structured validation of harness state, configuration, and
environment. Used by the ``harness health`` CLI command and optionally
at shell start to catch issues early.

Checks are categorised by severity:

- ``CRITICAL`` — Problems that prevent operation. Harness should not proceed.
- ``BRANCH`` — Wrong branch warnings. Configurable to block or warn.
- ``WARN`` — Potential issues. Commands can proceed but should be reviewed.
- ``INFO`` — Informational. Silent unless ``--verbose``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


_CHECK_DESCRIPTIONS: dict[str, str] = {
    "harness-dir": "``.harness/`` directory exists with required structure",
    "providers-yaml": "``providers.yaml`` is valid YAML and has at least one provider",
    "api-keys": "All ``${VAR}`` references in providers.yaml resolve to environment variables",
    "engagement-fresh": "Active engagement state is not stale",
    "branch-match": "Current git branch matches engagement's stored branch",
    "git-clean": "Git working tree has no uncommitted changes",
    "plan-consistency": "``plan.yaml`` is consistent with engagement state",
    "agent-roles": "All agent roles referenced in fleet/phase configs exist in agent registry",
    "manifest-link": "Assessment manifest files referenced by engagement exist",
    "python-version": "Python version meets minimum requirements",
}


Status = Literal["pass", "warn", "fail"]


@dataclass
class HealthCheck:
    """Single validation check result.

    Attributes:
        name: Machine-readable check name (e.g. ``"harness-dir"``).
        description: Human-readable description of what was checked.
        status: ``"pass"``, ``"warn"``, or ``"fail"``.
        message: Human-readable result message.
        severity: ``"CRITICAL"``, ``"BRANCH"``, ``"WARN"``, or ``"INFO"``.
        fix: Optional suggested fix command or action.
    """

    name: str
    description: str
    status: Status
    message: str
    severity: str = "WARN"
    fix: str | None = None


@dataclass
class HealthReport:
    """Aggregated health check results.

    Attributes:
        checks: All individual check results.
        summary: Short human-readable summary.
        status: Overall status (``"pass"`` if all passed, ``"warn"`` if any
            warn or branch mismatch, ``"fail"`` if any critical fails).
    """

    checks: list[HealthCheck] = field(default_factory=list)
    summary: str = ""

    @property
    def status(self) -> str:
        failures = any(c.status == "fail" for c in self.checks)
        warnings = any(c.status == "warn" for c in self.checks)
        if failures:
            return "fail"
        if warnings:
            return "warn"
        return "pass"

    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")


# ═══════════════════════════════════════════════════════════════════════════════
# Check functions
# ═══════════════════════════════════════════════════════════════════════════════


def _result(
    name: str,
    status: Status,
    message: str,
    severity: str = "WARN",
    fix: str | None = None,
) -> HealthCheck:
    return HealthCheck(
        name=name,
        description=_CHECK_DESCRIPTIONS.get(name, name),
        status=status,
        message=message,
        severity=severity,
        fix=fix,
    )


# ── Check: .harness/ directory ────────────────────────────────────────────


def check_harness_dir(root: Path) -> HealthCheck:
    """Verify the ``.harness/`` directory exists with core structure."""
    harness_dir = root / ".harness"
    if not harness_dir.is_dir():
        return _result(
            "harness-dir", "fail",
            "``.harness/`` directory not found. Run ``harness init`` to set up the project.",
            severity="CRITICAL",
            fix="harness init",
        )

    required = [
        "config.yaml",
        "active-engagements.yaml",
        "engagements",
    ]
    missing = [r for r in required if not (harness_dir / r).exists()]
    if missing:
        return _result(
            "harness-dir", "fail",
            f"Missing required files/dirs in .harness/: {', '.join(missing)}",
            severity="CRITICAL",
            fix="harness init --force",
        )

    return _result("harness-dir", "pass", ".harness/ directory structure is intact")


# ── Check: providers.yaml ─────────────────────────────────────────────────


def check_providers_yaml(root: Path) -> HealthCheck:
    """Verify ``providers.yaml`` exists, is valid YAML, and has providers."""
    providers_path = root / ".harness" / "providers.yaml"
    if not providers_path.is_file():
        return _result(
            "providers-yaml", "fail",
            "``providers.yaml`` not found. The harness needs at least one LLM provider.",
            severity="CRITICAL",
            fix="Create .harness/providers.yaml with provider configuration",
        )

    try:
        import yaml
        with open(providers_path) as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        return _result(
            "providers-yaml", "fail",
            f"``providers.yaml`` is not valid YAML: {exc}",
            severity="CRITICAL",
            fix=f"Fix syntax errors in {providers_path}",
        )

    if not data or "providers" not in data or not data["providers"]:
        return _result(
            "providers-yaml", "fail",
            "``providers.yaml`` has no providers configured.",
            severity="CRITICAL",
            fix="Add at least one provider to .harness/providers.yaml",
        )

    provider_names = list(data["providers"].keys())
    return _result(
        "providers-yaml", "pass",
        f"``providers.yaml`` is valid with {len(provider_names)} provider(s): "
        f"{', '.join(provider_names)}",
    )


# ── Check: API keys ────────────────────────────────────────────────────────


def check_api_keys(root: Path) -> HealthCheck:
    """Verify all ``${VAR}`` references in providers.yaml resolve to env vars."""
    import re

    providers_path = root / ".harness" / "providers.yaml"
    if not providers_path.is_file():
        return _result(
            "api-keys", "warn",
            "No providers.yaml — skipping API key check.",
        )

    try:
        import yaml
        with open(providers_path) as f:
            data = yaml.safe_load(f)
    except Exception:
        return _result("api-keys", "warn", "Cannot parse providers.yaml — skipping API key check.")

    if not data or "providers" not in data:
        return _result("api-keys", "pass", "No providers configured — skip.")

    # Find all ${VAR} patterns in provider configs
    var_pattern = re.compile(r"\$\{(\w+)\}")
    missing: list[str] = []
    resolved_count = 0

    for provider_name, provider_config in data["providers"].items():
        if isinstance(provider_config, dict):
            api_key = provider_config.get("api_key", "")
            if isinstance(api_key, str):
                matches = var_pattern.findall(api_key)
                for var_name in matches:
                    if not os.environ.get(var_name):
                        missing.append(var_name)
                    else:
                        resolved_count += 1

    if missing:
        unique_missing = sorted(set(missing))
        return _result(
            "api-keys", "fail",
            f"Environment variables not set: {', '.join(unique_missing)}. "
            f"API keys will fail to resolve.",
            severity="CRITICAL",
            fix=f"export {unique_missing[0]}=*** (or set in .env file)",
        )

    return _result(
        "api-keys", "pass",
        f"All {resolved_count} API key reference(s) resolve to environment variables.",
    )


# ── Check: Branch matches engagement ──────────────────────────────────────


def check_branch_match(root: Path) -> HealthCheck:
    """Verify current git branch matches the active engagement's stored branch."""
    try:
        from harness.scm.git import GitRepo
        from harness.engagement.lifecycle import read_active_engagement
        from harness.paths import get_engagement_dir

        repo = GitRepo(root)
        current_branch = repo.branch()

        active = read_active_engagement(root)
        if active is None:
            return _result(
                "branch-match", "pass",
                "No active engagement — skipping branch check.",
            )

        # Get slug from active engagement
        slug = active.get("slug") if isinstance(active, dict) else str(active)

        # Read engagement.yaml to find the expected branch
        eng_yaml_path = get_engagement_dir(root, slug) / "engagement.yaml"
        if not eng_yaml_path.is_file():
            return _result(
                "branch-match", "warn",
                f"Engagement '{slug}' has no engagement.yaml — cannot verify branch.",
            )

        import yaml
        with open(eng_yaml_path) as f:
            eng_data = yaml.safe_load(f) or {}

        expected_branch = eng_data.get("branch", f"eng/{slug}")

        if current_branch != expected_branch:
            return _result(
                "branch-match", "warn",
                f"Current branch '{current_branch}' does not match engagement "
                f"'{slug}' branch '{expected_branch}'.",
                severity="BRANCH",
                fix=f"git checkout {expected_branch}",
            )

        return _result(
            "branch-match", "pass",
            f"On correct branch '{current_branch}' for engagement '{slug}'.",
        )

    except Exception as exc:
        return _result(
            "branch-match", "warn",
            f"Cannot verify branch match: {exc}",
        )


# ── Check: Git clean ──────────────────────────────────────────────────────


def check_git_clean(root: Path) -> HealthCheck:
    """Verify the git working tree has no uncommitted changes."""
    try:
        from harness.scm.git import GitRepo
        repo = GitRepo(root)
        status = repo.status()
        untracked = len(status.untracked) if hasattr(status, 'untracked') else 0
        unstaged = len(status.unstaged) if hasattr(status, 'unstaged') else 0
        total = untracked + unstaged

        if total == 0:
            return _result("git-clean", "pass", "Git working tree is clean.")
        return _result(
            "git-clean", "warn",
            f"Git working tree has {total} uncommitted change(s) "
            f"({untracked} untracked, {unstaged} unstaged).",
            fix="git add -A && git commit",
        )
    except Exception as exc:
        return _result("git-clean", "warn", f"Cannot check git state: {exc}")


# ── Check: Agent roles ────────────────────────────────────────────────────


def check_agent_roles(root: Path) -> HealthCheck:
    """Verify all agent roles referenced in fleet/phase configs exist."""
    try:
        from harness.agents.agent_registry import AGENTS, AgentSpec

        # Scan .harness/fleets.yaml and .harness/engagements/ for role references
        fleet_path = root / ".harness" / "fleets.yaml"
        referenced_roles: set[str] = set()

        if fleet_path.is_file():
            import yaml
            with open(fleet_path) as f:
                fleet_data = yaml.safe_load(f) or {}
            for fleet_name, fleet_def in fleet_data.items():
                if isinstance(fleet_def, dict):
                    for agent in fleet_def.get("agents", []):
                        if isinstance(agent, dict):
                            referenced_roles.add(agent.get("name", ""))
                        elif isinstance(agent, str):
                            referenced_roles.add(agent)

        # Validate each referenced role exists in the enum
        valid_values = set(spec.role for spec in AGENTS)
        missing = [r for r in referenced_roles if r and r not in valid_values]

        if missing:
            return _result(
                "agent-roles", "warn",
                f"Referenced agent roles not in agent registry: {', '.join(missing)}. "
                f"These agents may operate without tool access.",
                fix=f"Add to agent registry: {', '.join(missing)}",
            )

        return _result(
            "agent-roles", "pass",
            f"All {len(referenced_roles)} referenced agent roles exist in agent registry.",
        )
    except Exception as exc:
        return _result("agent-roles", "warn", f"Cannot check agent roles: {exc}")


# ── Check: Python version ─────────────────────────────────────────────────


def check_python_version(root: Path) -> HealthCheck:
    """Verify Python version meets minimum requirements."""
    _ = root  # root not needed for this check
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 9):
        return _result(
            "python-version", "warn",
            f"Python {major}.{minor} is below minimum 3.9. Some features may not work.",
        )
    return _result(
        "python-version", "pass",
        f"Python {major}.{minor}.{sys.version_info[2]} — meets minimum 3.9+ requirement.",
    )


# ── Engagement state freshness ────────────────────────────────────────────


def check_engagement_fresh(root: Path) -> HealthCheck:
    """Verify the active engagement state is not stale."""
    try:
        from harness.state.freshness import load_freshness

        freshness = load_freshness(root)
        if freshness is None:
            return _result(
                "engagement-fresh", "pass",
                "No freshness record — skipping staleness check.",
            )

        if freshness.stale:
            return _result(
                "engagement-fresh", "fail",
                "Engagement state is stale. Run ``harness catchup`` to reconcile.",
                severity="CRITICAL",
                fix="harness catchup",
            )

        return _result(
            "engagement-fresh", "pass",
            "Engagement state is fresh.",
        )
    except Exception as exc:
        return _result(
            "engagement-fresh", "warn",
            f"Cannot check engagement freshness: {exc}",
        )


# ── Plan consistency ──────────────────────────────────────────────────────


def check_plan_consistency(root: Path) -> HealthCheck:
    """Verify plan.md is in sync with plan.yaml."""
    try:
        from harness.engagement.lifecycle import read_active_engagement
        from harness.paths import get_engagement_dir

        active = read_active_engagement(root)
        if active is None:
            return _result("plan-consistency", "pass", "No active engagement — skipping plan check.")

        slug = active.get("slug") if isinstance(active, dict) else str(active)
        eng_dir = get_engagement_dir(root, slug)

        plan_yaml = eng_dir / "plan.yaml"
        plan_md = eng_dir / "plan.md"

        if not plan_yaml.is_file():
            return _result("plan-consistency", "pass", "No plan.yaml found — skip.")

        # Parse plan.yaml
        import yaml
        with open(plan_yaml) as f:
            plan_data = yaml.safe_load(f) or {}

        waves_in_yaml = len(plan_data.get("waves", []))

        if not plan_md.is_file() or plan_md.stat().st_size == 0:
            return _result(
                "plan-consistency", "warn",
                f"plan.yaml has {waves_in_yaml} wave(s) but plan.md is empty or missing. "
                "Run ``harness catchup`` to sync.",
                fix="harness catchup",
            )

        return _result(
            "plan-consistency", "pass",
            f"plan.yaml has {waves_in_yaml} wave(s), and plan.md exists.",
        )
    except Exception as exc:
        return _result("plan-consistency", "warn", f"Cannot check plan consistency: {exc}")


# ── Manifest link ──────────────────────────────────────────────────────────


def check_manifest_link(root: Path) -> HealthCheck:
    """Verify assessment manifest files referenced by engagement exist."""
    try:
        from harness.engagement.lifecycle import read_active_engagement
        from harness.paths import get_engagement_dir

        active = read_active_engagement(root)
        if active is None:
            return _result("manifest-link", "pass", "No active engagement — skipping manifest check.")

        slug = active.get("slug") if isinstance(active, dict) else str(active)
        eng_yaml_path = get_engagement_dir(root, slug) / "engagement.yaml"

        if not eng_yaml_path.is_file():
            return _result("manifest-link", "pass", "No engagement.yaml — skip.")

        import yaml
        with open(eng_yaml_path) as f:
            eng_data = yaml.safe_load(f) or {}

        baseline = eng_data.get("baseline_manifest")
        if not baseline:
            return _result("manifest-link", "pass", "No baseline manifest — skip (not a refactoring engagement).")

        manifest_path = get_engagement_dir(root, slug) / baseline
        if not manifest_path.is_file():
            return _result(
                "manifest-link", "warn",
                f"Baseline manifest '{baseline}' not found at {manifest_path}. "
                "Re-run assessment or remove the reference.",
                fix="harness assess . --deep",
            )

        return _result("manifest-link", "pass", "Baseline manifest exists and is accessible.")
    except Exception as exc:
        return _result("manifest-link", "warn", f"Cannot check manifest links: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════


def run_health_checks(root: Path) -> HealthReport:
    """Run all health checks and return a report.

    Args:
        root: Project root directory.

    Returns:
        Aggregated ``HealthReport`` with all check results.
    """
    report = HealthReport()

    # Critical checks
    report.checks.append(check_harness_dir(root))
    report.checks.append(check_providers_yaml(root))
    report.checks.append(check_api_keys(root))
    report.checks.append(check_engagement_fresh(root))

    # Branch check (separate category)
    report.checks.append(check_branch_match(root))

    # Warning checks
    report.checks.append(check_git_clean(root))
    report.checks.append(check_agent_roles(root))
    report.checks.append(check_plan_consistency(root))
    report.checks.append(check_manifest_link(root))

    # Info checks
    report.checks.append(check_python_version(root))

    # Build summary
    passed = report.pass_count()
    warned = report.warn_count()
    failed = report.fail_count()
    parts = []
    if passed:
        parts.append(f"{passed} passed")
    if warned:
        parts.append(f"{warned} warnings")
    if failed:
        parts.append(f"{failed} failures")
    report.summary = f"{', '.join(parts)}" if parts else "All checks passed"

    return report


def format_health_report(report: HealthReport, verbose: bool = False) -> str:
    """Format a health report for terminal output.

    Args:
        report: The ``HealthReport`` to format.
        verbose: If True, include INFO-level checks.

    Returns:
        Formatted string ready for ``click.echo()``.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("  Harness Health")
    lines.append("  " + "─" * 45)

    severity_order = ["CRITICAL", "BRANCH", "WARN", "INFO"]
    for sev in severity_order:
        checks = [c for c in report.checks if c.severity == sev]
        if not checks:
            continue
        if sev == "INFO" and not verbose:
            continue

        lines.append("")
        lines.append(f"  {sev}")
        for c in checks:
            icon = "✓" if c.status == "pass" else ("⚠" if c.status == "warn" else "✗")
            lines.append(f"    {icon} {c.message}")
            if c.fix and c.status != "pass":
                lines.append(f"       → Fix: {c.fix}")

    lines.append("")
    lines.append(f"  {'─' * 45}")
    lines.append(f"  Status: {report.status.upper()} — {report.summary}")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Auto-fix functions (--fix mode)
# ═══════════════════════════════════════════════════════════════════════════════


def fix_branch_match(root: Path) -> list[str]:
    """Fix branch mismatch by updating engagement.yaml with the current branch.

    Returns a list of fix messages describing what was changed.
    """
    messages: list[str] = []
    try:
        from harness.scm.git import GitRepo
        from harness.engagement.lifecycle import read_active_engagement
        from harness.paths import get_engagement_dir

        repo = GitRepo(root)
        current_branch = repo.branch()

        active = read_active_engagement(root)
        if active is None:
            messages.append("No active engagement — cannot fix branch.")
            return messages

        slug = active.get("slug") if isinstance(active, dict) else str(active)
        eng_yaml_path = get_engagement_dir(root, slug) / "engagement.yaml"

        if not eng_yaml_path.is_file():
            messages.append(f"Engagement '{slug}' has no engagement.yaml.")
            return messages

        import yaml
        with open(eng_yaml_path) as f:
            yaml_data = yaml.safe_load(f) or {}

        old_branch = yaml_data.get("branch", "(not set)")
        yaml_data["branch"] = current_branch

        with open(eng_yaml_path, "w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        messages.append(f"Branch updated: {old_branch} → {current_branch}")
    except Exception as exc:
        messages.append(f"Branch fix failed: {exc}")

    return messages


def fix_plan_consistency(root: Path) -> list[str]:
    """Fix plan.md by syncing it from plan.yaml via PlanManager."""
    messages: list[str] = []
    try:
        from harness.engagement.lifecycle import read_active_engagement
        slug = read_active_engagement(root)
        if slug is None:
            messages.append("No active engagement — cannot fix plan.")
            return messages

        slug_str = slug.get("slug") if isinstance(slug, dict) else str(slug)
        from harness.plan.plan_manager import PlanManager
        pm = PlanManager(root, slug_str)
        plan = pm.load()
        if plan is None or not plan.waves:
            from harness.paths import get_engagement_plan_yaml
            plan_yaml = get_engagement_plan_yaml(root, slug_str)
            if not plan_yaml.is_file():
                plan_yaml.write_text("waves: []\n")
                messages.append("Created empty plan.yaml.")

        pm.sync_to_md()
        messages.append("plan.md synced from plan.yaml.")
    except Exception as exc:
        messages.append(f"Plan fix failed: {exc}")

    return messages


def fix_git_state(root: Path) -> list[str]:
    """Fix stale engagement state by refreshing freshness record."""
    import subprocess

    messages: list[str] = []
    try:
        from harness.state.freshness import (
            FreshnessRecord, load_freshness, save_freshness,
        )
        from harness.scm.git import GitRepo

        repo = GitRepo(root)
        current_branch = repo.branch()

        # Get HEAD sha via git command
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        current_head = result.stdout.strip() if result.returncode == 0 else "unknown"

        freshness = load_freshness(root)
        if freshness and freshness.stale:
            new_record = FreshnessRecord(
                branch=current_branch,
                head_sha=current_head,
                last_reconciled="",
                stale=False,
            ).mark_fresh(current_head)
            save_freshness(new_record, root)
            messages.append("Engagement state refreshed (staleness cleared).")
        else:
            messages.append("Engagement state is already fresh.")
    except Exception as exc:
        messages.append(f"Git state fix failed: {exc}")

    return messages


def fix_missing_dir(root: Path) -> list[str]:
    """Fix missing engagement directories and metadata files."""
    messages: list[str] = []
    try:
        from harness.engagement.lifecycle import (
            read_active_engagement,
        )

        active = read_active_engagement(root)
        if active is None:
            messages.append("No active engagement — cannot fix metadata.")
            return messages

        slug = active.get("slug") if isinstance(active, dict) else str(active)
        eng_dir = root / ".harness" / "engagements" / slug

        if not eng_dir.exists():
            eng_dir.mkdir(parents=True, exist_ok=True)
            messages.append(f"Created engagement directory: {eng_dir}")

        eng_yaml = eng_dir / "engagement.yaml"
        if not eng_yaml.is_file():
            import yaml
            with open(eng_yaml, "w") as f:
                yaml.dump({"slug": slug}, f, default_flow_style=False, sort_keys=False)
            messages.append(f"Created engagement.yaml for '{slug}'.")

        # Ensure engagement.md exists (needed by set_active_engagement)
        eng_md = eng_dir / "engagement.md"
        if not eng_md.is_file():
            from harness.scm.git import GitRepo
            repo = GitRepo(root)
            branch = repo.branch()
            # Re-read engagement.yaml to get updated slug/branch
            import yaml
            with open(eng_yaml) as f:
                yaml_data = yaml.safe_load(f) or {}
            eng_slug = yaml_data.get("slug", slug)
            eng_branch = yaml_data.get("branch", branch)
            from harness.engagement.lifecycle import write_engagement_metadata
            write_engagement_metadata(
                eng_dir, name=eng_slug.replace("-", " ").title(),
                slug=eng_slug, branch=eng_branch,
            )
            messages.append(f"Created engagement.md for '{slug}'.")

        plan_yaml = eng_dir / "plan.yaml"
        if not plan_yaml.is_file():
            plan_yaml.write_text("waves: []\n")
            messages.append("Created empty plan.yaml.")

        assess_dir = eng_dir / "assessments"
        if not assess_dir.exists():
            assess_dir.mkdir(parents=True, exist_ok=True)
            messages.append("Created assessments directory.")

        if not messages:
            messages.append("Engagement metadata is already complete.")

    except Exception as exc:
        messages.append(f"Metadata fix failed: {exc}")

    return messages


def run_fixes(root: Path) -> list[str]:
    """Run all auto-fixes on engagement metadata and state.

    Args:
        root: Project root directory.

    Returns:
        List of human-readable fix messages.
    """
    messages: list[str] = []
    messages.append("Attempting auto-fixes...")
    messages.append("")

    messages.extend(fix_missing_dir(root))
    messages.append("")

    messages.extend(fix_plan_consistency(root))
    messages.append("")

    messages.extend(fix_branch_match(root))
    messages.append("")

    messages.extend(fix_git_state(root))
    messages.append("")

    messages.append("Auto-fixes complete. Run 'harness health' to verify.")
    return messages


def fix_engagement(root: Path, slug: str) -> list[str]:
    """Fix engagement metadata and state for a specific engagement.

    Args:
        root: Project root directory.
        slug: Engagement slug to fix.

    Returns:
        List of human-readable fix messages.
    """
    messages: list[str] = []
    messages.append(f"Fixing engagement '{slug}'...")
    messages.append("")

    eng_dir = root / ".harness" / "engagements" / slug

    if not eng_dir.exists():
        eng_dir.mkdir(parents=True, exist_ok=True)
        messages.append(f"Created engagement directory: {eng_dir}")

    import yaml
    from harness.scm.git import GitRepo

    eng_yaml = eng_dir / "engagement.yaml"
    if not eng_yaml.is_file():
        repo = GitRepo(root)
        with open(eng_yaml, "w") as f:
            yaml.dump({
                "slug": slug,
                "branch": repo.branch(),
            }, f, default_flow_style=False, sort_keys=False)
        messages.append(f"Created engagement.yaml for '{slug}'.")
    else:
        messages.append("engagement.yaml exists.")

    eng_md = eng_dir / "engagement.md"
    if not eng_md.is_file():
        repo = GitRepo(root)
        with open(eng_yaml) as f:
            yaml_data = yaml.safe_load(f) or {}
        eng_branch = yaml_data.get("branch", repo.branch())
        from harness.engagement.lifecycle import write_engagement_metadata
        write_engagement_metadata(
            eng_dir, name=slug.replace("-", " ").title(),
            slug=slug, branch=eng_branch,
        )
        messages.append(f"Created engagement.md for '{slug}'.")
    else:
        messages.append("engagement.md exists.")

    plan_yaml = eng_dir / "plan.yaml"
    if not plan_yaml.is_file():
        plan_yaml.write_text("waves: []\n")
        messages.append("Created empty plan.yaml.")
    else:
        messages.append("plan.yaml exists.")

    plan_md = eng_dir / "plan.md"
    if not plan_md.is_file() or plan_md.stat().st_size == 0:
        from harness.plan.plan_manager import PlanManager
        pm = PlanManager(root, slug)
        pm.sync_to_md()
        messages.append("Created plan.md from plan.yaml.")
    else:
        messages.append("plan.md exists.")

    assess_dir = eng_dir / "assessments"
    if not assess_dir.exists():
        assess_dir.mkdir(parents=True, exist_ok=True)
        messages.append("Created assessments directory.")
    else:
        messages.append("assessments directory exists.")

    messages.append("")
    messages.append(f"Fix complete for '{slug}'.")
    return messages
