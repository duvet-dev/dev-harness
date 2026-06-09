"""Findings Registry — persistent, diffable issue tracker per engagement.

Each engagement maintains a ``findings.yaml`` file under
``.harness/engagements/<slug>/findings/findings.yaml``.  The
:class:`FindingsStore` class provides CRUD operations, lifecycle
management, and delta detection for the findings within a single
engagement.

Schema
------
Matches ``design/design.md §4.4``.

Each finding has:
- ``id`` — auto-generated ``F-001``, ``F-002``, … (persistent across runs)
- ``source`` — which agent/loop raised it (e.g. ``"architecture-critic"``)
- ``scope`` — ``observer`` / ``critic-loop`` / ``dev-test-loop`` / ``human``
- ``description`` — human-readable
- ``severity`` — ``critical`` / ``high`` / ``medium`` / ``low`` / ``info``
- ``status`` — ``open`` / ``acknowledged`` / ``in_progress`` / ``resolved`` / ``wont_fix`` / ``regression``
- ``references`` — optional dict with ``file`` and ``line``
- ``requires_human_signoff`` — bool, whether human must confirm resolution
- ``resolution`` — optional dict with ``wave`` and ``notes``
- ``raised_at`` / ``resolved_at`` — ISO-8601 timestamps

Lifecycle
---------
``open → acknowledged → in_progress → resolved``
   ``  ↓                          ↘ wont_fix
      regression ← ← ← ← ← ← ← ← ← ← ``

Delta detection
---------------
On each load + merge cycle, the store compares newly scanned findings
against the persisted registry and emits delta records for:
- **New**: previously unseen finding → added as ``open``
- **Resolved**: previously ``open`` finding no longer present → auto-``resolved``
- **Regression**: previously ``resolved`` finding reappears → ``regression``
- **Wont-fix regression**: previously ``wont_fix`` reappears → flagged
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


# ── Constants ──────────────────────────────────────────────────────────────

FINDINGS_DIR = "findings"
FINDINGS_FILE = "findings.yaml"

VALID_SEVERITIES = ("critical", "high", "medium", "low", "info")
VALID_STATUSES = ("open", "acknowledged", "in_progress", "resolved",
                  "wont_fix", "regression")
VALID_SCOPES = ("observer", "critic-loop", "dev-test-loop", "human")

# Transitions allowed per lifecycle
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"acknowledged", "in_progress", "resolved", "wont_fix"}),
    "acknowledged": frozenset({"in_progress", "resolved", "wont_fix"}),
    "in_progress": frozenset({"resolved", "wont_fix"}),
    "resolved": frozenset({"regression"}),
    "wont_fix": frozenset({"regression", "open"}),
    "regression": frozenset({"acknowledged", "in_progress", "wont_fix", "open"}),
}


# ── Exceptions ──────────────────────────────────────────────────────────────


class FindingsError(Exception):
    """Base exception for Findings Registry errors."""


class InvalidTransitionError(FindingsError):
    """Raised when a status transition is not allowed by the lifecycle."""


class FindingNotFoundError(FindingsError):
    """Raised when referring to a finding ID that does not exist."""


class ValidationError(FindingsError):
    """Raised when a finding field fails schema validation."""


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class FindingReference:
    """Reference to a specific location in the codebase."""
    file: str = ""
    line: Optional[int] = None


@dataclass
class FindingResolution:
    """How a finding was resolved."""
    wave: str = ""
    notes: str = ""


@dataclass
class RegistryFinding:
    """A single persisted finding in the Findings Registry.

    This is the durable, full-featured finding that lives in
    `findings.yaml`.  It is richer than the transient
    ``harness.analysis.base.Finding`` which is used for in-memory
    scan results.
    """

    id: str = ""
    source: str = ""
    scope: str = "observer"
    description: str = ""
    severity: str = "medium"
    status: str = "open"
    references: Optional[FindingReference] = None
    requires_human_signoff: bool = False
    resolution: Optional[FindingResolution] = None
    raised_at: str = ""
    resolved_at: Optional[str] = None

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ValidationError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(VALID_SEVERITIES)}"
            )
        if self.status not in VALID_STATUSES:
            raise ValidationError(
                f"Invalid status '{self.status}'. "
                f"Must be one of: {', '.join(VALID_STATUSES)}"
            )
        if self.scope not in VALID_SCOPES:
            raise ValidationError(
                f"Invalid scope '{self.scope}'. "
                f"Must be one of: {', '.join(VALID_SCOPES)}"
            )

    @property
    def is_open(self) -> bool:
        return self.status in ("open", "acknowledged", "in_progress")

    @property
    def is_resolved(self) -> bool:
        return self.status in ("resolved", "wont_fix")

    @property
    def is_pending_verification(self) -> bool:
        """True if auto-resolved but requires human sign-off."""
        return self.status == "resolved" and self.requires_human_signoff

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a YAML-friendly dict."""
        d: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "scope": self.scope,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "requires_human_signoff": self.requires_human_signoff,
            "raised_at": self.raised_at,
            "resolved_at": self.resolved_at,
        }
        if self.references and (self.references.file or self.references.line):
            d["references"] = asdict(self.references)
        if self.resolution and (self.resolution.wave or self.resolution.notes):
            d["resolution"] = asdict(self.resolution)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegistryFinding:
        """Deserialise from a YAML-parsed dict."""
        ref_data = data.pop("references", None) or {}
        res_data = data.pop("resolution", None) or {}
        f = cls(**data)
        if ref_data:
            f.references = FindingReference(**ref_data)
        if res_data:
            f.resolution = FindingResolution(**res_data)
        return f


@dataclass
class FindingsDelta:
    """Result of comparing scanned findings against the persisted registry."""

    new: list[RegistryFinding] = field(default_factory=list)
    """Findings that are newly detected (added as ``open``)."""

    resolved: list[RegistryFinding] = field(default_factory=list)
    """Previously open findings no longer detected (auto-resolved)."""

    regressions: list[RegistryFinding] = field(default_factory=list)
    """Previously resolved findings that reappeared."""

    wont_fix_regressions: list[RegistryFinding] = field(default_factory=list)
    """Previously wont_fix findings that reappeared."""

    unchanged: list[RegistryFinding] = field(default_factory=list)
    """Findings that remain in the same state."""

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.resolved or self.regressions
                    or self.wont_fix_regressions)

    def summary_lines(self) -> list[str]:
        """Human-readable summary of the delta."""
        lines: list[str] = []
        if self.new:
            lines.append(f"🆕 {len(self.new)} new finding(s)")
        if self.resolved:
            lines.append(f"✅ {len(self.resolved)} resolved")
        if self.regressions:
            lines.append(f"🔄 {len(self.regressions)} regression(s)")
        if self.wont_fix_regressions:
            lines.append(f"⚠️ {len(self.wont_fix_regressions)} wont-fix regression(s)")
        if not self.has_changes:
            lines.append("🔍 No changes — findings unchanged")
        return lines


# ── Store ─────────────────────────────────────────────────────────────────


class FindingsStore:
    """Persistent Findings Registry for a single engagement.

    Reads/writes ``findings.yaml`` at the engagement's findings directory.
    Provides CRUD, delta detection, and lifecycle management.
    """

    def __init__(self, root: Path, slug: str) -> None:
        self._root = root
        self._slug = slug
        self._findings: dict[str, RegistryFinding] = {}
        self._dirty = False
        self._load()

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def root(self) -> Path:
        return self._root

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def findings_path(self) -> Path:
        """Return the path to the engagement's findings.yaml."""
        return (self._engagement_dir / FINDINGS_DIR / FINDINGS_FILE)

    @property
    def findings_dir(self) -> Path:
        """Return the directory containing findings.yaml."""
        return (self._engagement_dir / FINDINGS_DIR)

    @property
    def _engagement_dir(self) -> Path:
        import harness.paths as hp
        return hp.get_engagement_dir(self._root, self._slug)

    @property
    def all_findings(self) -> list[RegistryFinding]:
        """Return all findings, sorted by ID."""
        return sorted(self._findings.values(), key=lambda f: f.id)

    def list_by_status(self, status: str) -> list[RegistryFinding]:
        """Return findings filtered by status."""
        return [f for f in self.all_findings if f.status == status]

    def list_by_severity(self, severity: str) -> list[RegistryFinding]:
        """Return findings filtered by severity."""
        return [f for f in self.all_findings if f.severity == severity]

    def list_by_source(self, source: str) -> list[RegistryFinding]:
        """Return findings filtered by source."""
        return [f for f in self.all_findings if f.source == source]

    # ── CRUD ────────────────────────────────────────────────────────────────

    def get(self, finding_id: str) -> Optional[RegistryFinding]:
        """Get a finding by its ID (e.g. ``F-001``)."""
        return self._findings.get(finding_id)

    def add(self, finding: RegistryFinding) -> str:
        """Add a new finding, auto-generating its ID if not set.

        Returns the assigned ID.
        """
        if not finding.id:
            finding.id = self._next_id()
        if not finding.raised_at:
            finding.raised_at = _now_iso()
        finding.status = "open"
        self._findings[finding.id] = finding
        self._dirty = True
        return finding.id

    def update_status(self, finding_id: str, new_status: str) -> RegistryFinding:
        """Update a finding's status, enforcing lifecycle transitions.

        Args:
            finding_id: Finding ID (``F-001``).
            new_status: Target status.

        Returns:
            The updated finding.

        Raises:
            FindingNotFoundError: If the finding does not exist.
            InvalidTransitionError: If the transition is not allowed.
        """
        finding = self._findings.get(finding_id)
        if finding is None:
            raise FindingNotFoundError(
                f"Finding '{finding_id}' not found in engagement '{self._slug}'"
            )
        allowed = _ALLOWED_TRANSITIONS.get(finding.status, frozenset())
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition finding '{finding_id}' from "
                f"'{finding.status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(sorted(allowed))}"
            )
        finding.status = new_status
        if new_status in ("resolved", "wont_fix"):
            finding.resolved_at = _now_iso()
        elif new_status == "regression":
            finding.resolved_at = None
        self._dirty = True
        return finding

    def delete(self, finding_id: str) -> bool:
        """Remove a finding from the registry. Returns True if deleted."""
        if finding_id in self._findings:
            del self._findings[finding_id]
            self._dirty = True
            return True
        return False

    # ── Persistence ─────────────────────────────────────────────────────────

    def save(self) -> None:
        """Flush findings to disk as YAML."""
        if not self._dirty:
            return
        self.findings_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "findings": [f.to_dict() for f in self.all_findings],
        }
        self.findings_path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)
        )
        self._dirty = False

    def _load(self) -> None:
        """Load findings from disk."""
        self._findings = {}
        path = self.findings_path
        if not path.exists():
            return
        raw = yaml.safe_load(path.read_text())
        if not raw or "findings" not in raw:
            return
        for item in raw["findings"]:
            finding = RegistryFinding.from_dict(item)
            self._findings[finding.id] = finding
        self._dirty = False

    # ── Delta detection ─────────────────────────────────────────────────────

    def compute_delta(
        self,
        scanned: list[RegistryFinding],
    ) -> FindingsDelta:
        """Compare scanned findings against the persisted registry.

        Args:
            scanned: Findings produced by the current analysis run.

        Returns:
            A ``FindingsDelta`` describing what changed.
        """
        delta = FindingsDelta()

        # Build a signature for each scanned finding for matching.
        # Two findings are "the same" if they share source, description,
        # and the same file reference.
        scanned_keys: set[str] = set()
        for sf in scanned:
            key = self._finding_key(sf)
            scanned_keys.add(key)

        persisted_keys: dict[str, RegistryFinding] = {}
        for pf in self._findings.values():
            key = self._finding_key(pf)
            persisted_keys[key] = pf

        # Determine new, resolved, regressed
        seen_persisted_keys: set[str] = set()

        for sf in scanned:
            key = self._finding_key(sf)
            existing = persisted_keys.get(key)
            if existing is None:
                # Brand new finding
                sf.id = ""
                sf.status = "open"
                delta.new.append(sf)
            else:
                seen_persisted_keys.add(key)
                if existing.status == "regression":
                    # Still present — keep it regressed until manually handled
                    delta.unchanged.append(existing)
                elif existing.status in ("resolved", "wont_fix"):
                    if existing.status == "resolved":
                        # Reappeared — regression
                        existing.status = "regression"
                        existing.resolved_at = None
                        self._dirty = True
                        delta.regressions.append(existing)
                    else:
                        # wont_fix finding reappeared
                        delta.wont_fix_regressions.append(existing)
                else:
                    # Still open — no change needed
                    delta.unchanged.append(existing)

        # Findings that were in the registry but no longer detected
        for pf in self._findings.values():
            key = self._finding_key(pf)
            if key not in seen_persisted_keys:
                if pf.status in ("open", "acknowledged", "in_progress"):
                    # No longer detected — auto-resolve
                    pf.status = "resolved"
                    pf.resolved_at = _now_iso()
                    self._dirty = True
                    delta.resolved.append(pf)
                # If already resolved/wont_fix/regression, leave as-is

        return delta

    def sync_from_assessment(
        self,
        assessment_findings: list[dict[str, Any]],
        source: str = "assessment",
        scope: str = "observer",
    ) -> FindingsDelta:
        """Sync findings from an assessment report into the registry.

        Converts assessment findings (dicts with keys like ``description``,
        ``severity``, ``category``) into ``RegistryFinding`` objects and
        runs delta detection against the persisted registry.

        Args:
            assessment_findings: List of finding dicts from an
                ``AssessmentReport`` or LLM agent output.
            source: Default source label (e.g. ``"architecture-critic"``).
            scope: Scope for all imported findings.

        Returns:
            A ``FindingsDelta`` describing what changed.
        """
        scanned: list[RegistryFinding] = []
        for item in assessment_findings:
            sev = _map_severity(item.get("severity", "medium"))
            file_path = item.get("file", "") or ""
            line = item.get("line", None)
            rf = RegistryFinding(
                source=item.get("source", source),
                scope=scope,
                description=item.get("description", "")
                          or item.get("message", ""),
                severity=sev,
                references=FindingReference(file=file_path, line=line)
                          if file_path else None,
                requires_human_signoff=_is_critical_or_high(sev),
                raised_at=_now_iso(),
            )
            scanned.append(rf)

        delta = self.compute_delta(scanned)
        self.save()
        return delta

    def sync_from_scan_results(
        self,
        scan_results: list,
        source_prefix: str = "scan",
        scope: str = "observer",
    ) -> FindingsDelta:
        """Sync findings from ``ScanResult`` objects into the registry.

        Converts ``harness.analysis.base.ScanResult`` (or any object with
        a ``.findings`` iterable of objects with ``.severity``, ``.message``,
        ``.file``, ``.line``) into registry findings and runs delta detection.

        Args:
            scan_results: List of ``ScanResult`` objects.
            source_prefix: Prefix for generating source labels.
            scope: Scope for all imported findings.

        Returns:
            A ``FindingsDelta`` describing what changed.
        """
        scanned: list[RegistryFinding] = []
        for i, sr in enumerate(scan_results):
            source_name = getattr(sr, "scan_name", f"{source_prefix}-{i}")
            for f in getattr(sr, "findings", []):
                sev = _map_severity(getattr(f, "severity", "info"))
                rf = RegistryFinding(
                    source=source_name,
                    scope=scope,
                    description=getattr(f, "message", ""),
                    severity=sev,
                    references=FindingReference(
                        file=getattr(f, "file", ""),
                        line=getattr(f, "line", None),
                    ) if getattr(f, "file", "") else None,
                    requires_human_signoff=_is_critical_or_high(sev),
                    raised_at=_now_iso(),
                )
                scanned.append(rf)

        delta = self.compute_delta(scanned)
        self.save()
        return delta

    def resolve_findings_by_wave(
        self,
        finding_ids: list[str],
        wave_name: str = "",
        notes: str = "",
        mark_pending: bool = True,
    ) -> list[str]:
        """Mark specified findings as resolved (or pending verification
        if they require human sign-off).

        Called when a wave completes and declares ``resolves:``.

        Args:
            finding_ids: List of finding IDs to resolve.
            wave_name: Name of the resolving wave.
            notes: Optional notes about the resolution.
            mark_pending: If True, findings with ``requires_human_signoff``
                stay as ``resolved/pending_verification``. If False,
                force fully resolved.

        Returns:
            List of finding IDs that were successfully resolved.
        """
        resolved: list[str] = []
        for fid in finding_ids:
            finding = self._findings.get(fid)
            if finding is None:
                continue
            if finding.is_resolved:
                continue  # Already resolved
            finding.status = "resolved"
            finding.resolved_at = _now_iso()
            if finding.resolution is None:
                finding.resolution = FindingResolution()
            finding.resolution.wave = wave_name
            if notes:
                finding.resolution.notes = notes
            self._dirty = True
            resolved.append(fid)
        if resolved:
            self.save()
        return resolved

    def confirm_human_signoff(self, finding_id: str) -> Optional[RegistryFinding]:
        """Confirm human sign-off for a resolved/pending finding.

        Sets the status from ``resolved`` to ``resolved`` (confirmed)
        and clears the pending-verification marker.

        Args:
            finding_id: Finding ID to confirm.

        Returns:
            The updated finding, or ``None`` if not found.
        """
        finding = self._findings.get(finding_id)
        if finding is None:
            return None
        if not finding.is_pending_verification:
            # Already confirmed or not in pending state
            if finding.status == "resolved" and not finding.requires_human_signoff:
                return finding  # Already fully resolved
            raise InvalidTransitionError(
                f"Finding '{finding_id}' is in status '{finding.status}' — "
                f"cannot confirm human sign-off"
            )
        # Clear the pending-verification marker
        finding.requires_human_signoff = False
        self._dirty = True
        self.save()
        return finding

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """Generate the next available finding ID."""
        existing = sorted(self._findings.keys())
        if not existing:
            return "F-001"
        max_num = 0
        for eid in existing:
            m = re.match(r"^F-(\d+)$", eid)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
        return f"F-{max_num + 1:03d}"

    @staticmethod
    def _finding_key(finding: RegistryFinding) -> str:
        """Generate a stable key for matching findings across runs.

        Uses source + description + file reference as the identity.
        """
        file_ref = ""
        if finding.references:
            file_ref = finding.references.file or ""
        return f"{finding.source}:::{finding.description}:::{file_ref}"


# ── Utility ─────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_finding_from_analysis(
    source: str,
    scope: str,
    description: str,
    severity: str = "medium",
    file_path: str = "",
    line: int | None = None,
    requires_human_signoff: bool = False,
) -> RegistryFinding:
    """Create a RegistryFinding from an analysis scan result.

    This is a convenience factory for converting transient
    ``harness.analysis.base.Finding`` objects into persistent
    registry findings.
    """
    ref = FindingReference(file=file_path, line=line) if file_path else None
    return RegistryFinding(
        source=source,
        scope=scope,
        description=description,
        severity=severity,
        references=ref,
        requires_human_signoff=requires_human_signoff,
        raised_at=_now_iso(),
    )


# ── Severity Mapping ────────────────────────────────────────────────────────

_SEVERITY_MAP: dict[str, str] = {
    # From harness.analysis.base.Finding severities
    "error": "critical",
    "warning": "high",
    "info": "low",
    # Direct mappings (identity)
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


_CRITICAL_OR_HIGH = frozenset({"critical", "high"})


def _map_severity(sev: str) -> str:
    """Map incoming severity strings to Findings Registry severities."""
    mapped = _SEVERITY_MAP.get(sev.lower(), "medium")
    if mapped not in VALID_SEVERITIES:
        return "medium"
    return mapped


def _is_critical_or_high(sev: str) -> bool:
    return sev in _CRITICAL_OR_HIGH
