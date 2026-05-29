"""Tests for workflow/model.py: Workflow dataclass."""

from __future__ import annotations

from harness.workflow.model import Workflow


class TestWorkflow:
    """Workflow dataclass tests."""

    def test_minimal_workflow(self) -> None:
        wf = Workflow(name="standard")
        assert wf.name == "standard"
        assert wf.phases == []

    def test_with_phases(self) -> None:
        wf = Workflow(
            name="standard",
            phases=["design", "build", "review", "test", "validate"],
        )
        assert wf.name == "standard"
        assert len(wf.phases) == 5
        assert wf.phases[0] == "design"
        assert wf.phases[-1] == "validate"

    def test_empty_name(self) -> None:
        wf = Workflow(name="")
        assert wf.name == ""

    def test_single_phase(self) -> None:
        wf = Workflow(name="quick-fix", phases=["fix"])
        assert len(wf.phases) == 1

    def test_immutability_of_default_factory(self) -> None:
        """Each workflow should have its own phases list."""
        wf1 = Workflow(name="a")
        wf2 = Workflow(name="b")
        wf1.phases.append("design")
        assert wf2.phases == []
