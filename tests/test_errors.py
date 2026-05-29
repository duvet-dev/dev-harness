"""Tests for errors.py: Full HarnessError hierarchy."""

from __future__ import annotations

import pytest

from harness.errors import (
    AggregatorError,
    AgentTimeoutError,
    BoundaryTestViolationError,
    CommandError,
    CommandValidationError,
    ConfigValidationError,
    EmptyTeamError,
    EngagementBranchMissingError,
    EngagementCorruptStateError,
    EngagementDirtyStateError,
    EngagementNotFoundError,
    ExecutionError,
    HandlerNotFoundError,
    HarnessError,
    LoopExecutionError,
    NLTranslationError,
    ParallelDispatchError,
    PhaseExecutionError,
    PhaseStateNotFoundError,
    StateError,
    StepDispatchError,
    StepMutualExclusionError,
    UnknownAgentError,
    UnknownCommandError,
    UnknownPhaseError,
    UnknownSkillError,
    UnknownTeamError,
    UnknownTemplateError,
    ValidationError,
    WebSearchUnavailableError,
)


def _all_error_classes() -> list[type[HarnessError]]:
    """Return all concrete error classes in the hierarchy."""
    return [
        HarnessError,
        ValidationError,
        UnknownTeamError,
        EmptyTeamError,
        UnknownPhaseError,
        UnknownAgentError,
        UnknownSkillError,
        UnknownTemplateError,
        StepMutualExclusionError,
        ConfigValidationError,
        ExecutionError,
        StepDispatchError,
        PhaseExecutionError,
        LoopExecutionError,
        ParallelDispatchError,
        AgentTimeoutError,
        AggregatorError,
        StateError,
        EngagementNotFoundError,
        EngagementCorruptStateError,
        EngagementBranchMissingError,
        EngagementDirtyStateError,
        PhaseStateNotFoundError,
        CommandError,
        UnknownCommandError,
        HandlerNotFoundError,
        CommandValidationError,
        NLTranslationError,
        WebSearchUnavailableError,
        BoundaryTestViolationError,
    ]


class TestHarnessErrorBase:
    """Tests for the HarnessError base class."""

    def test_base_error_subclasses_exception(self) -> None:
        assert issubclass(HarnessError, Exception)

    def test_base_error_with_message(self) -> None:
        err = HarnessError("something went wrong")
        assert err.message == "something went wrong"
        assert str(err) == "something went wrong"

    def test_base_error_default_message(self) -> None:
        err = HarnessError()
        assert err.message == ""


class TestErrorHierarchy:
    """Tests for the error hierarchy structure."""

    def test_all_errors_subclass_harness_error(self) -> None:
        for cls in _all_error_classes():
            assert issubclass(cls, HarnessError)

    def test_validation_hierarchy(self) -> None:
        assert issubclass(UnknownTeamError, ValidationError)
        assert issubclass(EmptyTeamError, ValidationError)
        assert issubclass(UnknownPhaseError, ValidationError)
        assert issubclass(UnknownAgentError, ValidationError)
        assert issubclass(UnknownSkillError, ValidationError)
        assert issubclass(UnknownTemplateError, ValidationError)
        assert issubclass(StepMutualExclusionError, ValidationError)
        assert issubclass(ConfigValidationError, ValidationError)

    def test_execution_hierarchy(self) -> None:
        assert issubclass(StepDispatchError, ExecutionError)
        assert issubclass(PhaseExecutionError, ExecutionError)
        assert issubclass(LoopExecutionError, ExecutionError)
        assert issubclass(ParallelDispatchError, ExecutionError)
        assert issubclass(AgentTimeoutError, ExecutionError)
        assert issubclass(AggregatorError, ExecutionError)

    def test_state_hierarchy(self) -> None:
        assert issubclass(EngagementNotFoundError, StateError)
        assert issubclass(EngagementCorruptStateError, StateError)
        assert issubclass(EngagementBranchMissingError, StateError)
        assert issubclass(EngagementDirtyStateError, StateError)
        assert issubclass(PhaseStateNotFoundError, StateError)

    def test_command_hierarchy(self) -> None:
        assert issubclass(UnknownCommandError, CommandError)
        assert issubclass(HandlerNotFoundError, CommandError)
        assert issubclass(CommandValidationError, CommandError)

    def test_standalone_errors(self) -> None:
        assert issubclass(NLTranslationError, HarnessError)
        assert issubclass(WebSearchUnavailableError, HarnessError)
        assert issubclass(BoundaryTestViolationError, HarnessError)


class TestErrorInstantiation:
    """Tests that all errors can be instantiated with a message."""

    @pytest.mark.parametrize("cls", _all_error_classes())
    def test_instantiate_with_message(self, cls: type) -> None:
        err = cls("test message")
        assert err.message == "test message"
        assert str(err) == "test message"

    @pytest.mark.parametrize("cls", _all_error_classes())
    def test_instantiate_without_message(self, cls: type) -> None:
        err = cls()
        assert err.message == ""


class TestErrorSpecificity:
    """Tests for specific error semantics."""

    def test_step_mutual_exclusion_error_format(self) -> None:
        err = StepMutualExclusionError(
            "Exactly one of 'agents', 'team', 'loop', or 'phase' "
            "must be specified. Found 2"
        )
        assert "Exactly one of" in err.message

    def test_unknown_team_error(self) -> None:
        err = UnknownTeamError("Team 'foo' not found")
        assert "foo" in err.message

    def test_isinstance_checks(self) -> None:
        """All ValidationErrors should be catchable as ValidationError."""
        for exc_type in [UnknownTeamError, StepMutualExclusionError]:
            err = exc_type("test")
            assert isinstance(err, ValidationError)

        for exc_type in [
            StepDispatchError,
            PhaseExecutionError,
        ]:
            err = exc_type("test")
            assert isinstance(err, ExecutionError)

        for exc_type in [
            EngagementNotFoundError,
            PhaseStateNotFoundError,
        ]:
            err = exc_type("test")
            assert isinstance(err, StateError)

        for exc_type in [
            UnknownCommandError,
            CommandValidationError,
        ]:
            err = exc_type("test")
            assert isinstance(err, CommandError)
