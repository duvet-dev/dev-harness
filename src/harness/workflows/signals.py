"""
Signal definitions for Temporal workflows (§4.1).

Each dataclass represents a typed payload sent as a Temporal signal
or returned as a query result during engagement orchestration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FeedbackItem:
    """Structured feedback for a single finding in an artifact."""

    VALID_SEVERITIES = frozenset({"blocker", "major", "minor", "suggestion"})

    finding: str  # What's wrong
    severity: str  # "blocker" | "major" | "minor" | "suggestion"
    artifact_ref: str  # Which artifact this applies to (file path or section name)
    suggestion: str = ""  # Optional suggestion for improvement

    def __post_init__(self) -> None:
        if self.severity not in self.VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {self.severity!r}. "
                f"Must be one of {sorted(self.VALID_SEVERITIES)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict."""
        return {
            "finding": self.finding,
            "severity": self.severity,
            "artifact_ref": self.artifact_ref,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackItem":
        """Deserialize from a dict."""
        return cls(
            finding=data["finding"],
            severity=data["severity"],
            artifact_ref=data["artifact_ref"],
            suggestion=data.get("suggestion", ""),
        )


@dataclass
class ReviewVerdict:
    """Complete review outcome for an engagement phase."""

    decision: str  # "approved" | "rejected" | "request_changes"
    engagement_id: str
    phase: str
    feedback: list[FeedbackItem] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict."""
        return {
            "decision": self.decision,
            "engagement_id": self.engagement_id,
            "phase": self.phase,
            "feedback": [f.to_dict() for f in self.feedback],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewVerdict":
        """Deserialize from a dict."""
        feedback_list = [
            FeedbackItem.from_dict(f)
            for f in data.get("feedback", [])
        ]
        return cls(
            decision=data["decision"],
            engagement_id=data["engagement_id"],
            phase=data["phase"],
            feedback=feedback_list,
            notes=data.get("notes", ""),
        )


@dataclass
class IterationConfig:
    """Configuration for engagement iteration limits."""

    max_iterations: int = 5
    escalation_after_max: bool = True  # Surface for human decision when max hit
    partial_approval: bool = True  # Allow approving some artifacts, rejecting others

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict."""
        return {
            "max_iterations": self.max_iterations,
            "escalation_after_max": self.escalation_after_max,
            "partial_approval": self.partial_approval,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IterationConfig":
        """Deserialize from a dict."""
        return cls(
            max_iterations=data.get("max_iterations", 5),
            escalation_after_max=data.get("escalation_after_max", True),
            partial_approval=data.get("partial_approval", True),
        )


@dataclass
class GateReviewSignal:
    """Human approves/rejects a gate checkpoint."""

    VALID_DECISIONS = frozenset({"approved", "rejected", "request_changes"})

    engagement_id: str
    phase: str
    decision: str  # "approved" | "rejected" | "request_changes"
    notes: str = ""
    feedback: list[FeedbackItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.decision not in self.VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision {self.decision!r}. "
                f"Must be one of {sorted(self.VALID_DECISIONS)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for Temporal serialisation."""
        return {
            "engagement_id": self.engagement_id,
            "phase": self.phase,
            "decision": self.decision,
            "notes": self.notes,
            "feedback": [f.to_dict() for f in self.feedback],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateReviewSignal":
        """Deserialize from a dict returned by Temporal."""
        feedback_list = [
            FeedbackItem.from_dict(f)
            for f in data.get("feedback", [])
        ]
        return cls(
            engagement_id=data["engagement_id"],
            phase=data["phase"],
            decision=data["decision"],
            notes=data.get("notes", ""),
            feedback=feedback_list,
        )


@dataclass
class WorkDoneSignal:
    """Agent reports task completion."""

    engagement_id: str
    task_id: str
    status: str  # "completed" | "failed" | "partial"
    output_files: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for Temporal serialisation."""
        return {
            "engagement_id": self.engagement_id,
            "task_id": self.task_id,
            "status": self.status,
            "output_files": list(self.output_files),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkDoneSignal":
        """Deserialize from a dict returned by Temporal."""
        return cls(
            engagement_id=data["engagement_id"],
            task_id=data["task_id"],
            status=data["status"],
            output_files=list(data.get("output_files", [])),
            summary=data.get("summary", ""),
        )


@dataclass
class StateReconcileSignal:
    """Absorb manual edits to harness-state.yaml."""

    engagement_id: str
    corrected_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for Temporal serialisation."""
        return {
            "engagement_id": self.engagement_id,
            "corrected_fields": dict(self.corrected_fields),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateReconcileSignal":
        """Deserialize from a dict returned by Temporal."""
        return cls(
            engagement_id=data["engagement_id"],
            corrected_fields=dict(data.get("corrected_fields", {})),
        )


@dataclass
class EngagementQueryResult:
    """Response to summary/state queries."""

    engagement_id: str
    status: str
    phase: str
    description: str
    gate_mode: str
    pending_items: List[str] = field(default_factory=list)
    retry_count: int = 0
    phases: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for Temporal serialisation."""
        return {
            "engagement_id": self.engagement_id,
            "status": self.status,
            "phase": self.phase,
            "description": self.description,
            "gate_mode": self.gate_mode,
            "pending_items": list(self.pending_items),
            "retry_count": self.retry_count,
            "phases": list(self.phases),
            "tasks": list(self.tasks),
            "decisions": list(self.decisions),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EngagementQueryResult":
        """Deserialize from a dict returned by Temporal."""
        return cls(
            engagement_id=data["engagement_id"],
            status=data["status"],
            phase=data["phase"],
            description=data["description"],
            gate_mode=data["gate_mode"],
            pending_items=list(data.get("pending_items", [])),
            retry_count=data.get("retry_count", 0),
            phases=list(data.get("phases", [])),
            tasks=list(data.get("tasks", [])),
            decisions=list(data.get("decisions", [])),
        )
