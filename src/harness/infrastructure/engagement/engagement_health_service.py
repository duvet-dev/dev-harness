"""Engagement health check service.

Provides ``EngagementHealthChecker`` for validating engagement state,
plan consistency, manifest links, and fixing engagement metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from harness.domain.health import HealthCheck, _result
from harness.domain.interfaces.repositories import YamlReader
from harness.paths import (
    get_engagement_dir,
    get_engagement_plan_yaml,
    get_engagement_yaml,
)


class EngagementHealthChecker:
    """Health checks and fixes for engagement-related concerns.

    Args:
        engagement_reader: Callable that takes a root path and returns
            the active engagement dict or ``None``.
        yaml_reader: An object with ``read(path)`` for parsing YAML files.
        plan_manager_factory: Callable ``(root, slug)`` that returns an
            object with ``load()`` and ``sync_to_md()`` methods.
        git_repo_factory: Callable ``(root)`` that returns an object
            with ``branch()`` method.
        freshness_loader: Callable ``(root)`` that returns a freshness
            record with ``stale`` attribute, or ``None``.
    """

    def __init__(
        self,
        engagement_reader: Callable[[Path], Optional[dict[str, Any]]],
        yaml_reader: YamlReader,
        plan_manager_factory: Callable[[Path, str], Any],
        git_repo_factory: Callable[[Path], Any],
        freshness_loader: Callable[[Path], Any],
    ) -> None:
        self._engagement_reader = engagement_reader
        self._yaml = yaml_reader
        self._plan_factory = plan_manager_factory
        self._git_factory = git_repo_factory
        self._freshness = freshness_loader

    # ── Checks ──────────────────────────────────────────────────────────

    def check_engagement_fresh(self, root: Path) -> HealthCheck:
        """Verify the active engagement state is not stale."""
        try:
            freshness = self._freshness(root)
            if freshness is None:
                return _result(
                    "engagement-fresh", "pass",
                    "No freshness record — skipping staleness check.",
                )

            if getattr(freshness, "stale", False):
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

    def check_plan_consistency(self, root: Path) -> HealthCheck:
        """Verify plan.md is in sync with plan.yaml."""
        try:
            active = self._engagement_reader(root)
            if active is None:
                return _result(
                    "plan-consistency", "pass",
                    "No active engagement — skipping plan check.",
                )

            slug = active.get("slug") if isinstance(active, dict) else str(active)
            eng_dir = get_engagement_dir(root, slug)

            plan_yaml = eng_dir / "plan.yaml"
            plan_md = eng_dir / "plan.md"

            if not plan_yaml.is_file():
                return _result("plan-consistency", "pass", "No plan.yaml found — skip.")

            plan_data = self._yaml.read(plan_yaml) or {}
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

    def check_manifest_link(self, root: Path) -> HealthCheck:
        """Verify assessment manifest files referenced by engagement exist."""
        try:
            active = self._engagement_reader(root)
            if active is None:
                return _result(
                    "manifest-link", "pass",
                    "No active engagement — skipping manifest check.",
                )

            slug = active.get("slug") if isinstance(active, dict) else str(active)
            eng_yaml_path = get_engagement_yaml(root, slug)

            if not eng_yaml_path.is_file():
                return _result("manifest-link", "pass", "No engagement.yaml — skip.")

            eng_data = self._yaml.read(eng_yaml_path) or {}

            baseline = eng_data.get("baseline_manifest")
            if not baseline:
                return _result(
                    "manifest-link", "pass",
                    "No baseline manifest — skip (not a refactoring engagement).",
                )

            manifest_path = get_engagement_dir(root, slug) / baseline
            if not manifest_path.is_file():
                return _result(
                    "manifest-link", "warn",
                    f"Baseline manifest '{baseline}' not found at {manifest_path}. "
                    "Re-run assessment or remove the reference.",
                    fix="harness assess . --deep",
                )

            return _result(
                "manifest-link", "pass",
                "Baseline manifest exists and is accessible.",
            )
        except Exception as exc:
            return _result("manifest-link", "warn", f"Cannot check manifest links: {exc}")

    # ── Fixes ───────────────────────────────────────────────────────────

    def fix_plan_consistency(self, root: Path) -> list[str]:
        """Fix plan.md by syncing it from plan.yaml via PlanManager."""
        messages: list[str] = []
        try:
            slug = self._engagement_reader(root)
            if slug is None:
                messages.append("No active engagement — cannot fix plan.")
                return messages

            slug_str = slug.get("slug") if isinstance(slug, dict) else str(slug)
            pm = self._plan_factory(root, slug_str)
            plan = pm.load()
            if plan is None or not getattr(plan, "waves", []):
                plan_yaml = get_engagement_plan_yaml(root, slug_str)
                if not plan_yaml.is_file():
                    plan_yaml.write_text("waves: []\n")
                    messages.append("Created empty plan.yaml.")

            pm.sync_to_md()
            messages.append("plan.md synced from plan.yaml.")
        except Exception as exc:
            messages.append(f"Plan fix failed: {exc}")

        return messages

    def fix_missing_dir(self, root: Path) -> list[str]:
        """Fix missing engagement directories and metadata files."""
        messages: list[str] = []
        try:
            active = self._engagement_reader(root)
            if active is None:
                messages.append("No active engagement — cannot fix metadata.")
                return messages

            slug = active.get("slug") if isinstance(active, dict) else str(active)
            eng_dir = get_engagement_dir(root, slug)

            if not eng_dir.exists():
                eng_dir.mkdir(parents=True, exist_ok=True)
                messages.append(f"Created engagement directory: {eng_dir}")

            eng_yaml = get_engagement_yaml(root, slug)
            if not eng_yaml.is_file():
                with open(eng_yaml, "w") as f:
                    yaml.dump({"slug": slug}, f, default_flow_style=False, sort_keys=False)
                messages.append(f"Created engagement.yaml for '{slug}'.")

            eng_md = eng_dir / "engagement.md"
            if not eng_md.is_file():
                repo = self._git_factory(root)
                branch = repo.branch()
                with open(eng_yaml) as f:
                    yaml_data = yaml.safe_load(f) or {}
                eng_slug = yaml_data.get("slug", slug)
                eng_branch = yaml_data.get("branch", branch)
                from harness.domain.engagement.lifecycle import write_engagement_metadata
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

    def fix_engagement(self, root: Path, slug: str) -> list[str]:
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

        eng_dir = get_engagement_dir(root, slug)

        if not eng_dir.exists():
            eng_dir.mkdir(parents=True, exist_ok=True)
            messages.append(f"Created engagement directory: {eng_dir}")

        repo = self._git_factory(root)

        eng_yaml = get_engagement_yaml(root, slug)
        if not eng_yaml.is_file():
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
            with open(eng_yaml) as f:
                yaml_data = yaml.safe_load(f) or {}
            eng_branch = yaml_data.get("branch", repo.branch())
            from harness.domain.engagement.lifecycle import write_engagement_metadata
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
            pm = self._plan_factory(root, slug)
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


__all__ = [
    "EngagementHealthChecker",
]
