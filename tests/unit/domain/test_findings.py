"""Tests for the Findings Registry — persistent, diffable issue tracker.

Covers:
- FindingsStore CRUD and persistence across runs
- Delta detection: new, resolved, regression, wont-fix regression
- Lifecycle transitions (valid and invalid)
- Human sign-off (pending_verification flow)
- Wave resolution linking from PlanManager
- Sync from assessment and scan results
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from harness.domain.engagement.findings import (
    FindingsStore,
    RegistryFinding,
    FindingReference,
    FindingResolution,
    FindingsDelta,
    InvalidTransitionError,
    FindingNotFoundError,
    ValidationError,
    create_finding_from_analysis,
    _map_severity,
    _now_iso,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def harness_root() -> Path:
    """Create a temporary harness project root with .harness dir."""
    tmp = Path(tempfile.mkdtemp())
    (tmp / ".harness").mkdir(exist_ok=True)
    return tmp


@pytest.fixture
def store(harness_root: Path) -> FindingsStore:
    """Create a FindingsStore for testing."""
    return FindingsStore(harness_root, "test-engagement")


@pytest.fixture
def populated_store(store: FindingsStore) -> FindingsStore:
    """A store with pre-populated findings."""
    f1 = RegistryFinding(
        source="architecture-critic",
        scope="observer",
        description="CLI god module — 2,408 lines, 17% coverage",
        severity="critical",
        references=FindingReference(file="src/harness/cli/main.py", line=1),
    )
    f2 = RegistryFinding(
        source="test-auditor",
        scope="observer",
        description="Coverage below threshold on 3 modules",
        severity="high",
        references=FindingReference(file="src/harness/cli/main.py"),
    )
    f3 = RegistryFinding(
        source="code-critic",
        scope="observer",
        description="Unused import detected",
        severity="low",
        references=FindingReference(file="src/utils.py", line=42),
    )
    store.add(f1)
    store.add(f2)
    store.add(f3)
    store.save()
    return store


# ── Test: CRUD ───────────────────────────────────────────────────────────────────


class TestFindingsStoreCRUD:
    """Basic create, read, update, delete operations."""

    def test_add_finding_generates_id(self, store: FindingsStore):
        f = RegistryFinding(
            source="architecture-critic",
            scope="observer",
            description="Test finding",
            severity="medium",
        )
        fid = store.add(f)
        assert fid.startswith("F-")
        assert len(fid) == 5  # F-001
        assert f.status == "open"  # Auto-set
        assert f.raised_at != ""  # Auto-timestamped

    def test_add_finding_with_explicit_id(self, store: FindingsStore):
        f = RegistryFinding(
            id="F-099",
            source="test",
            scope="observer",
            description="Explicit ID",
            severity="info",
        )
        fid = store.add(f)
        assert fid == "F-099"

    def test_get_finding(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Get me", severity="info")
        fid = store.add(f)
        found = store.get(fid)
        assert found is not None
        assert found.id == fid
        assert found.description == "Get me"

    def test_get_nonexistent_returns_none(self, store: FindingsStore):
        assert store.get("F-999") is None

    def test_list_by_status(self, populated_store: FindingsStore):
        open_findings = populated_store.list_by_status("open")
        assert len(open_findings) == 3

    def test_list_by_severity(self, populated_store: FindingsStore):
        severity_findings = populated_store.list_by_severity("critical")
        assert len(severity_findings) == 1
        assert severity_findings[0].description.startswith("CLI god module")

    def test_list_by_source(self, populated_store: FindingsStore):
        findings = populated_store.list_by_source("code-critic")
        assert len(findings) == 1
        assert findings[0].severity == "low"

    def test_delete_finding(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Delete me", severity="info")
        fid = store.add(f)
        assert store.delete(fid) is True
        assert store.get(fid) is None

    def test_delete_nonexistent(self, store: FindingsStore):
        assert store.delete("F-999") is False


# ── Test: Persistence Across Runs ────────────────────────────────────────────────


class TestFindingsStorePersistence:
    """Findings survive reloading the store."""

    def test_findings_persist_across_store_instances(self, harness_root: Path):
        store1 = FindingsStore(harness_root, "persist-test")
        f = RegistryFinding(source="test", scope="observer", description="Persist me", severity="medium")
        fid = store1.add(f)
        store1.save()

        # New store instance reads from disk
        store2 = FindingsStore(harness_root, "persist-test")
        found = store2.get(fid)
        assert found is not None
        assert found.description == "Persist me"
        assert found.status == "open"

    def test_save_only_flushes_when_dirty(self, store: FindingsStore):
        """save() is a no-op if no changes were made."""
        import os
        store.save()
        # File should NOT exist since nothing was added
        assert not store.findings_path.exists()

    def test_empty_store_creates_no_file(self, harness_root: Path):
        store = FindingsStore(harness_root, "empty-test")
        assert not store.findings_path.exists()

    def test_findings_dir_created_on_first_save(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Trigger save", severity="info")
        store.add(f)
        store.save()
        assert store.findings_dir.exists()
        assert store.findings_path.exists()


# ── Test: Delta Detection ────────────────────────────────────────────────────────


class TestFindingsDelta:
    """Delta detection: new, resolved, regression, wont-fix regression."""

    def test_new_finding_detected(self, populated_store: FindingsStore):
        scanned = [
            RegistryFinding(source="architecture-critic", scope="observer",
                            description="CLI god module — 2,408 lines, 17% coverage",
                            severity="critical",
                            references=FindingReference(file="src/harness/cli/main.py", line=1)),
            RegistryFinding(source="test-auditor", scope="observer",
                            description="Coverage below threshold on 3 modules",
                            severity="high",
                            references=FindingReference(file="src/harness/cli/main.py")),
            RegistryFinding(source="code-critic", scope="observer",
                            description="Unused import detected",
                            severity="low",
                            references=FindingReference(file="src/utils.py", line=42)),
            RegistryFinding(source="new-agent", scope="observer",
                            description="Brand new finding",
                            severity="medium"),
        ]
        delta = populated_store.compute_delta(scanned)
        assert len(delta.new) == 1
        assert delta.new[0].description == "Brand new finding"

    def test_resolved_finding_detected(self, populated_store: FindingsStore):
        """A previously open finding no longer in scan results is auto-resolved."""
        scanned = [
            RegistryFinding(source="architecture-critic", scope="observer",
                            description="CLI god module — 2,408 lines, 17% coverage",
                            severity="critical",
                            references=FindingReference(file="src/harness/cli/main.py", line=1)),
            RegistryFinding(source="test-auditor", scope="observer",
                            description="Coverage below threshold on 3 modules",
                            severity="high",
                            references=FindingReference(file="src/harness/cli/main.py")),
            # code-critic finding is MISSING — should auto-resolve
        ]
        delta = populated_store.compute_delta(scanned)
        assert len(delta.resolved) == 1
        assert delta.resolved[0].description == "Unused import detected"
        assert delta.resolved[0].status == "resolved"
        assert delta.resolved[0].resolved_at is not None

    def test_regression_detected(self, populated_store: FindingsStore):
        """A previously resolved finding that reappears is flagged as regression."""
        # First mark the code-critic finding as resolved
        populated_store.update_status("F-003", "resolved")
        populated_store.save()

        # Now rescan WITH the previously resolved finding
        scanned = [
            RegistryFinding(source="architecture-critic", scope="observer",
                            description="CLI god module — 2,408 lines, 17% coverage",
                            severity="critical",
                            references=FindingReference(file="src/harness/cli/main.py", line=1)),
            RegistryFinding(source="test-auditor", scope="observer",
                            description="Coverage below threshold on 3 modules",
                            severity="high",
                            references=FindingReference(file="src/harness/cli/main.py")),
            RegistryFinding(source="code-critic", scope="observer",
                            description="Unused import detected",
                            severity="low",
                            references=FindingReference(file="src/utils.py", line=42)),
        ]
        delta = populated_store.compute_delta(scanned)
        assert len(delta.regressions) == 1
        assert delta.regressions[0].id == "F-003"
        assert delta.regressions[0].status == "regression"

    def test_wont_fix_regression_detected(self, populated_store: FindingsStore):
        """A wont_fix finding that reappears is specially flagged."""
        populated_store.update_status("F-003", "wont_fix")
        populated_store.save()

        scanned = [
            RegistryFinding(source="architecture-critic", scope="observer",
                            description="CLI god module — 2,408 lines, 17% coverage",
                            severity="critical",
                            references=FindingReference(file="src/harness/cli/main.py", line=1)),
            RegistryFinding(source="test-auditor", scope="observer",
                            description="Coverage below threshold on 3 modules",
                            severity="high",
                            references=FindingReference(file="src/harness/cli/main.py")),
            RegistryFinding(source="code-critic", scope="observer",
                            description="Unused import detected",
                            severity="low",
                            references=FindingReference(file="src/utils.py", line=42)),
        ]
        delta = populated_store.compute_delta(scanned)
        assert len(delta.wont_fix_regressions) == 1
        assert delta.wont_fix_regressions[0].id == "F-003"

    def test_no_changes_when_unchanged(self, populated_store: FindingsStore):
        """When all findings match exactly, nothing changes."""
        scanned = [
            RegistryFinding(source="architecture-critic", scope="observer",
                            description="CLI god module — 2,408 lines, 17% coverage",
                            severity="critical",
                            references=FindingReference(file="src/harness/cli/main.py", line=1)),
            RegistryFinding(source="test-auditor", scope="observer",
                            description="Coverage below threshold on 3 modules",
                            severity="high",
                            references=FindingReference(file="src/harness/cli/main.py")),
            RegistryFinding(source="code-critic", scope="observer",
                            description="Unused import detected",
                            severity="low",
                            references=FindingReference(file="src/utils.py", line=42)),
        ]
        delta = populated_store.compute_delta(scanned)
        assert len(delta.new) == 0
        assert len(delta.resolved) == 0
        assert len(delta.regressions) == 0
        assert len(delta.wont_fix_regressions) == 0
        assert len(delta.unchanged) == 3
        assert not delta.has_changes

    def test_delta_summary_lines(self, populated_store: FindingsStore):
        delta = FindingsDelta(
            new=[RegistryFinding(source="t", scope="observer", description="n", severity="info")],
            resolved=[RegistryFinding(source="t", scope="observer", description="r", severity="info")],
        )
        lines = delta.summary_lines()
        assert any("new" in l for l in lines)
        assert any("resolved" in l for l in lines)


# ── Test: Lifecycle Transitions ──────────────────────────────────────────────────


class TestFindingsLifecycle:
    """Status lifecycle transitions (open → acknowledged → ... → regression)."""

    def test_valid_transition(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Lifecycle", severity="medium")
        fid = store.add(f)
        store.update_status(fid, "acknowledged")
        assert store.get(fid).status == "acknowledged"
        store.update_status(fid, "in_progress")
        assert store.get(fid).status == "in_progress"
        store.update_status(fid, "resolved")
        assert store.get(fid).status == "resolved"
        assert store.get(fid).resolved_at is not None

    def test_wont_fix_transition(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Wont fix", severity="medium")
        fid = store.add(f)
        store.update_status(fid, "wont_fix")
        assert store.get(fid).status == "wont_fix"

    def test_regression_transition_from_resolved(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Regression test", severity="medium")
        fid = store.add(f)
        store.update_status(fid, "resolved")
        rt = store.get(fid)
        assert rt.resolved_at is not None
        store.update_status(fid, "regression")
        assert store.get(fid).status == "regression"
        assert store.get(fid).resolved_at is None  # Cleared

    def test_invalid_transition_raises(self, store: FindingsStore):
        f = RegistryFinding(source="test", scope="observer", description="Invalid transition", severity="medium")
        fid = store.add(f)
        store.update_status(fid, "resolved")
        with pytest.raises(InvalidTransitionError):
            store.update_status(fid, "open")

    def test_nonexistent_finding_raises(self, store: FindingsStore):
        with pytest.raises(FindingNotFoundError):
            store.update_status("F-999", "resolved")


# ── Test: Human Sign-off ──────────────────────────────────────────────────────────


class TestHumanSignoff:
    """Human sign-off for auto-resolved findings requiring verification."""

    def test_is_pending_verification(self, store: FindingsStore):
        f = RegistryFinding(
            source="test", scope="observer",
            description="Needs sign-off",
            severity="critical",
            requires_human_signoff=True,
        )
        fid = store.add(f)
        store.update_status(fid, "resolved")
        finding = store.get(fid)
        assert finding.is_pending_verification

    def test_confirm_human_signoff(self, store: FindingsStore):
        f = RegistryFinding(
            source="test", scope="observer",
            description="Confirm me",
            severity="high",
            requires_human_signoff=True,
        )
        fid = store.add(f)
        store.update_status(fid, "resolved")
        result = store.confirm_human_signoff(fid)
        assert result is not None
        assert not result.is_pending_verification
        assert not result.requires_human_signoff

    def test_confirm_nonexistent_returns_none(self, store: FindingsStore):
        assert store.confirm_human_signoff("F-999") is None

    def test_confirm_non_pending_raises(self, store: FindingsStore):
        f = RegistryFinding(
            source="test", scope="observer",
            description="Not pending",
            severity="low",
            requires_human_signoff=False,
        )
        fid = store.add(f)
        store.update_status(fid, "resolved")
        # Should NOT raise since it doesn't require human sign-off
        result = store.confirm_human_signoff(fid)
        assert result is not None

    def test_resolve_findings_by_wave_respects_signoff(self, store: FindingsStore):
        f = RegistryFinding(
            source="test", scope="observer",
            description="Needs sign-off via wave",
            severity="critical",
            requires_human_signoff=True,
        )
        fid = store.add(f)
        store.save()

        store2 = FindingsStore(store._root, store._slug)
        resolved = store2.resolve_findings_by_wave([fid], wave_name="wave-01")
        assert fid in resolved
        finding = store2.get(fid)
        assert finding.status == "resolved"
        assert finding.is_pending_verification
        assert finding.resolution is not None
        assert finding.resolution.wave == "wave-01"


# ── Test: Wave Resolution Linking ────────────────────────────────────────────────


class TestWaveResolution:
    """Wave-completion resolution of findings."""

    def test_wave_resolves_findings(self, populated_store: FindingsStore):
        """Findings declared in wave.resolves are auto-resolved on commit."""
        from harness.plan.plan_manager import PlanManager
        from harness.plan.wave_model import Wave

        populated_store.save()

        pm = PlanManager(populated_store._root, populated_store._slug)
        plan = pm.load()
        wave = Wave(
            id="wave-01",
            title="Fix CLI god module",
            resolves=["F-001", "F-002"],
        )
        plan.add_wave(wave)
        pm.save(plan)

        # Commit the wave — should auto-resolve findings
        result = pm.commit_wave("wave-01")
        assert result is True

        # Verify findings were resolved
        store2 = FindingsStore(populated_store._root, populated_store._slug)
        f1 = store2.get("F-001")
        assert f1 is not None
        assert f1.status == "resolved"
        assert f1.resolution is not None
        assert f1.resolution.wave == "wave-01"
        assert f1.resolution.notes == "Fix CLI god module"

    def test_wave_without_resolves_no_side_effects(self, populated_store: FindingsStore):
        """A wave without resolves doesn't affect findings."""
        from harness.plan.plan_manager import PlanManager
        from harness.plan.wave_model import Wave

        populated_store.save()

        pm = PlanManager(populated_store._root, populated_store._slug)
        plan = pm.load()
        wave = Wave(id="wave-02", title="Add feature")
        plan.add_wave(wave)
        pm.save(plan)
        pm.commit_wave("wave-02")

        store2 = FindingsStore(populated_store._root, populated_store._slug)
        assert store2.get("F-001").status == "open"

    def test_wave_resolves_partial(self, populated_store: FindingsStore):
        """Only declared findings are resolved."""
        from harness.plan.plan_manager import PlanManager
        from harness.plan.wave_model import Wave

        populated_store.save()

        pm = PlanManager(populated_store._root, populated_store._slug)
        plan = pm.load()
        wave = Wave(id="wave-03", title="Partial fix", resolves=["F-001"])
        plan.add_wave(wave)
        pm.save(plan)
        pm.commit_wave("wave-03")

        store2 = FindingsStore(populated_store._root, populated_store._slug)
        assert store2.get("F-001").status == "resolved"
        assert store2.get("F-002").status == "open"
        assert store2.get("F-003").status == "open"


# ── Test: Severity Mapping ──────────────────────────────────────────────────────


class TestSeverityMapping:
    def test_map_from_analysis_severities(self):
        assert _map_severity("error") == "critical"
        assert _map_severity("warning") == "high"
        assert _map_severity("info") == "low"

    def test_map_from_registry_severities(self):
        assert _map_severity("critical") == "critical"
        assert _map_severity("high") == "high"
        assert _map_severity("medium") == "medium"
        assert _map_severity("low") == "low"

    def test_unknown_severity_defaults_to_medium(self):
        assert _map_severity("bogus") == "medium"

    def test_case_insensitive(self):
        assert _map_severity("ERROR") == "critical"
        assert _map_severity("Warning") == "high"


# ── Test: Validation ────────────────────────────────────────────────────────────


class TestValidation:
    def test_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            RegistryFinding(source="test", scope="observer", description="Bad", severity="invalid")

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            RegistryFinding(source="test", scope="observer", description="Bad", status="invalid")

    def test_invalid_scope_raises(self):
        with pytest.raises(ValidationError):
            RegistryFinding(source="test", scope="invalid", description="Bad", severity="info")


# ── Test: Serialization ─────────────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict_round_trip(self):
        original = RegistryFinding(
            id="F-042",
            source="architecture-critic",
            scope="observer",
            description="Test serialization",
            severity="high",
            status="in_progress",
            references=FindingReference(file="src/main.py", line=42),
            resolution=FindingResolution(wave="wave-01", notes="Fixed"),
            requires_human_signoff=True,
            raised_at="2026-01-01T00:00:00Z",
            resolved_at="2026-01-02T00:00:00Z",
        )
        data = original.to_dict()
        restored = RegistryFinding.from_dict(data)
        assert restored.id == original.id
        assert restored.source == original.source
        assert restored.description == original.description
        assert restored.severity == original.severity
        assert restored.status == original.status
        assert restored.requires_human_signoff == original.requires_human_signoff
        assert restored.references is not None
        assert restored.references.file == "src/main.py"
        assert restored.references.line == 42
        assert restored.resolution is not None
        assert restored.resolution.wave == "wave-01"
        assert restored.resolved_at == "2026-01-02T00:00:00Z"

    def test_to_dict_minimal(self):
        f = RegistryFinding(source="test", scope="observer", description="Minimal", severity="low")
        d = f.to_dict()
        assert d["id"] == ""
        assert d["description"] == "Minimal"
        assert "references" not in d
        assert "resolution" not in d

    def test_create_finding_from_analysis_convenience(self):
        rf = create_finding_from_analysis(
            source="architecture-critic",
            scope="observer",
            description="CLI god module",
            severity="critical",
            file_path="src/main.py",
            line=42,
            requires_human_signoff=True,
        )
        assert rf.source == "architecture-critic"
        assert rf.description == "CLI god module"
        assert rf.severity == "critical"
        assert rf.references is not None
        assert rf.references.file == "src/main.py"
        assert rf.references.line == 42
        assert rf.requires_human_signoff is True
        assert rf.raised_at != ""
        assert rf.status == "open"  # Will be set when added to store
