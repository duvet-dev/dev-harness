"""Tests for harness.workflows.signals — signal dataclasses."""

from __future__ import annotations

import pytest

from harness.workflows.signals import (
    FeedbackItem,
    ReviewVerdict,
    IterationConfig,
    GateReviewSignal,
    WorkDoneSignal,
    StateReconcileSignal,
    EngagementQueryResult,
)


class TestFeedbackItem:
    """Tests for the FeedbackItem dataclass."""

    def test_valid_severities(self):
        item = FeedbackItem(
            finding="Missing error handling",
            severity="blocker",
            artifact_ref="src/main.py",
            suggestion="Add try/except",
        )
        assert item.finding == "Missing error handling"
        assert item.severity == "blocker"
        assert item.artifact_ref == "src/main.py"
        assert item.suggestion == "Add try/except"

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            FeedbackItem(
                finding="Something",
                severity="critical",  # not in valid set
                artifact_ref="file.py",
            )

    def test_to_dict(self):
        item = FeedbackItem(
            finding="Bug",
            severity="major",
            artifact_ref="src/lib.rs",
            suggestion="Refactor",
        )
        d = item.to_dict()
        assert d["finding"] == "Bug"
        assert d["severity"] == "major"
        assert d["artifact_ref"] == "src/lib.rs"
        assert d["suggestion"] == "Refactor"

    def test_from_dict(self):
        data = {
            "finding": "Poor naming",
            "severity": "minor",
            "artifact_ref": "src/utils.py",
            "suggestion": "Rename to snake_case",
        }
        item = FeedbackItem.from_dict(data)
        assert isinstance(item, FeedbackItem)
        assert item.finding == "Poor naming"
        assert item.severity == "minor"
        assert item.suggestion == "Rename to snake_case"

    def test_from_dict_without_suggestion(self):
        data = {
            "finding": "Typo",
            "severity": "suggestion",
            "artifact_ref": "README.md",
        }
        item = FeedbackItem.from_dict(data)
        assert item.suggestion == ""

    def test_all_valid_severities(self):
        for sev in FeedbackItem.VALID_SEVERITIES:
            item = FeedbackItem(
                finding="Test", severity=sev, artifact_ref="file.py"
            )
            assert item.severity == sev

    def test_valid_severities_set(self):
        assert FeedbackItem.VALID_SEVERITIES == frozenset(
            {"blocker", "major", "minor", "suggestion"}
        )

    def test_to_dict_roundtrip(self):
        original = FeedbackItem(
            finding="Missing tests",
            severity="blocker",
            artifact_ref="tests/",
            suggestion="Add unit tests",
        )
        restored = FeedbackItem.from_dict(original.to_dict())
        assert restored == original


class TestReviewVerdict:
    """Tests for the ReviewVerdict dataclass."""

    def test_create_approved(self):
        verdict = ReviewVerdict(
            decision="approved",
            engagement_id="eng-1",
            phase="build",
            notes="Great work",
        )
        assert verdict.decision == "approved"
        assert verdict.engagement_id == "eng-1"

    def test_to_dict(self):
        verdict = ReviewVerdict(
            decision="request_changes",
            engagement_id="eng-1",
            phase="design",
            feedback=[
                FeedbackItem(
                    finding="Fix logic",
                    severity="blocker",
                    artifact_ref="main.py",
                ),
            ],
            notes="See feedback",
        )
        d = verdict.to_dict()
        assert d["decision"] == "request_changes"
        assert len(d["feedback"]) == 1

    def test_from_dict(self):
        data = {
            "decision": "rejected",
            "engagement_id": "eng-1",
            "phase": "review",
            "feedback": [],
            "notes": "Not ready",
        }
        verdict = ReviewVerdict.from_dict(data)
        assert verdict.decision == "rejected"
        assert verdict.notes == "Not ready"


class TestIterationConfig:
    """Tests for the IterationConfig dataclass."""

    def test_defaults(self):
        config = IterationConfig()
        assert config.max_iterations == 5
        assert config.escalation_after_max is True
        assert config.partial_approval is True

    def test_custom_values(self):
        config = IterationConfig(
            max_iterations=3,
            escalation_after_max=False,
            partial_approval=False,
        )
        assert config.max_iterations == 3
        assert config.escalation_after_max is False
        assert config.partial_approval is False

    def test_to_dict(self):
        config = IterationConfig(max_iterations=2, partial_approval=False)
        d = config.to_dict()
        assert d["max_iterations"] == 2
        assert d["partial_approval"] is False

    def test_from_dict(self):
        config = IterationConfig.from_dict({
            "max_iterations": 10,
            "escalation_after_max": False,
            "partial_approval": True,
        })
        assert config.max_iterations == 10

    def test_from_dict_empty(self):
        config = IterationConfig.from_dict({})
        assert config.max_iterations == 5  # default


class TestGateReviewSignal:
    """Tests for the GateReviewSignal dataclass."""

    def test_valid_decisions(self):
        for decision in ("approved", "rejected", "request_changes"):
            signal = GateReviewSignal(
                engagement_id="eng-1",
                phase="build",
                decision=decision,
            )
            assert signal.decision == decision

    def test_invalid_decision_raises(self):
        with pytest.raises(ValueError, match="Invalid decision"):
            GateReviewSignal(
                engagement_id="eng-1",
                phase="build",
                decision="maybe",
            )

    def test_to_dict(self):
        signal = GateReviewSignal(
            engagement_id="eng-1",
            phase="build",
            decision="approved",
            notes="LGTM",
        )
        d = signal.to_dict()
        assert d["decision"] == "approved"
        assert d["engagement_id"] == "eng-1"

    def test_from_dict(self):
        data = {
            "engagement_id": "eng-1",
            "phase": "design",
            "decision": "request_changes",
            "notes": "Redo it",
            "feedback": [
                {
                    "finding": "Bad approach",
                    "severity": "blocker",
                    "artifact_ref": "arch.md",
                }
            ],
        }
        signal = GateReviewSignal.from_dict(data)
        assert signal.decision == "request_changes"
        assert len(signal.feedback) == 1
        assert signal.feedback[0].severity == "blocker"

    def test_from_dict_no_feedback(self):
        data = {
            "engagement_id": "eng-1",
            "phase": "build",
            "decision": "approved",
        }
        signal = GateReviewSignal.from_dict(data)
        assert signal.feedback == []


class TestWorkDoneSignal:
    """Tests for the WorkDoneSignal dataclass."""

    def test_minimal(self):
        signal = WorkDoneSignal(
            engagement_id="eng-1",
            task_id="task-1",
            status="completed",
        )
        assert signal.engagement_id == "eng-1"
        assert signal.summary == ""

    def test_full(self):
        signal = WorkDoneSignal(
            engagement_id="eng-1",
            task_id="task-1",
            status="partial",
            output_files=["out1.txt", "out2.txt"],
            summary="Two files produced",
        )
        assert len(signal.output_files) == 2
        assert signal.summary == "Two files produced"

    def test_to_dict(self):
        signal = WorkDoneSignal(
            engagement_id="eng-1",
            task_id="task-1",
            status="completed",
            output_files=["result.md"],
        )
        d = signal.to_dict()
        assert d["output_files"] == ["result.md"]

    def test_from_dict(self):
        data = {
            "engagement_id": "eng-1",
            "task_id": "task-1",
            "status": "failed",
            "output_files": [],
            "summary": "Crashed",
        }
        signal = WorkDoneSignal.from_dict(data)
        assert signal.status == "failed"
        assert signal.summary == "Crashed"


class TestStateReconcileSignal:
    """Tests for the StateReconcileSignal dataclass."""

    def test_create(self):
        signal = StateReconcileSignal(
            engagement_id="eng-1",
            corrected_fields={"status": "blocked", "phase": "review"},
        )
        assert signal.corrected_fields["status"] == "blocked"

    def test_empty_corrected_fields(self):
        signal = StateReconcileSignal(engagement_id="eng-1")
        assert signal.corrected_fields == {}

    def test_to_dict(self):
        signal = StateReconcileSignal(
            engagement_id="eng-1",
            corrected_fields={"status": "completed"},
        )
        d = signal.to_dict()
        assert d["corrected_fields"]["status"] == "completed"

    def test_from_dict(self):
        data = {
            "engagement_id": "eng-1",
            "corrected_fields": {"phase": "build", "status": "active"},
        }
        signal = StateReconcileSignal.from_dict(data)
        assert signal.engagement_id == "eng-1"
        assert signal.corrected_fields["phase"] == "build"


class TestEngagementQueryResult:
    """Tests for the EngagementQueryResult dataclass."""

    def test_create(self):
        result = EngagementQueryResult(
            engagement_id="eng-1",
            status="in_progress",
            phase="build",
            description="Test",
            gate_mode="auto",
        )
        assert result.engagement_id == "eng-1"

    def test_to_dict(self):
        result = EngagementQueryResult(
            engagement_id="eng-1",
            status="completed",
            phase="review",
            description="Done",
            gate_mode="full",
            pending_items=["item1"],
            retry_count=2,
            phases=[{"phase": "build", "status": "completed"}],
            tasks=[{"task_id": "t1", "status": "ok"}],
        )
        d = result.to_dict()
        assert d["retry_count"] == 2
        assert len(d["phases"]) == 1

    def test_from_dict(self):
        data = {
            "engagement_id": "eng-1",
            "status": "in_progress",
            "phase": "design",
            "description": "Building",
            "gate_mode": "auto",
            "pending_items": [],
            "retry_count": 0,
            "phases": [],
            "tasks": [],
            "decisions": [],
        }
        result = EngagementQueryResult.from_dict(data)
        assert result.status == "in_progress"

    def test_from_dict_with_missing_fields(self):
        data = {
            "engagement_id": "eng-1",
            "status": "active",
            "phase": "build",
            "description": "test",
            "gate_mode": "auto",
        }
        result = EngagementQueryResult.from_dict(data)
        assert result.pending_items == []
        assert result.retry_count == 0
