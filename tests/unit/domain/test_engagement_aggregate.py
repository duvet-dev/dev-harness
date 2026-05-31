"""Tests for domain/engagement_aggregate.py: Engagement aggregate root."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from harness.domain.engagement_aggregate import Engagement, HealthWarning, EngagementStatus
from harness.domain.enums import SessionType
from harness.domain.events.engagement_events import (
    EngagementStarted,
    EngagementCompleted,
    EngagementAborted,
    EngagementStatusChanged,
    PhaseTransitioned,
    WaveCommitted,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def engagement() -> Engagement:
    return Engagement(slug="test-eng", workflow_name="standard")


# ── Initial state ───────────────────────────────────────────────────────────


class TestEngagementInit:
    def test_default_status_is_created(self, engagement: Engagement):
        assert engagement.status == EngagementStatus.CREATED

    def test_default_workflow(self, engagement: Engagement):
        assert engagement.workflow_name == "standard"

    def test_default_session_type(self, engagement: Engagement):
        assert engagement.session_type == SessionType.GREENFIELD

    def test_created_at_set(self, engagement: Engagement):
        assert isinstance(engagement.created_at, datetime)
        assert engagement.created_at.tzinfo is timezone.utc

    def test_no_initial_warnings(self, engagement: Engagement):
        assert len(engagement.warnings) == 0

    def test_no_initial_events(self, engagement: Engagement):
        assert len(engagement._events) == 0

    def test_custom_init(self):
        e = Engagement(
            slug="custom",
            workflow_name="advanced",
            session_type=SessionType.REFACTORING,
            target_branch="main",
        )
        assert e.workflow_name == "advanced"
        assert e.session_type == SessionType.REFACTORING
        assert e.target_branch == "main"


# ── Lifecycle transitions ───────────────────────────────────────────────────


class TestEngagementLifecycle:
    def test_start_transitions_to_active(self, engagement: Engagement):
        engagement.start()
        assert engagement.status == EngagementStatus.ACTIVE
        assert isinstance(engagement.last_active, datetime)

    def test_start_publishes_event(self, engagement: Engagement):
        engagement.start()
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], EngagementStarted)
        assert events[0].slug == "test-eng"

    def test_start_raises_if_not_created(self, engagement: Engagement):
        engagement.start()
        with pytest.raises(ValueError, match="Cannot start"):
            engagement.start()

    def test_complete_transitions_to_completed(self, engagement: Engagement):
        engagement.status = EngagementStatus.ACTIVE
        engagement.complete()
        assert engagement.status == EngagementStatus.COMPLETED

    def test_complete_publishes_event(self, engagement: Engagement):
        engagement.status = EngagementStatus.ACTIVE
        engagement.complete()
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], EngagementCompleted)

    def test_abort_transitions_to_aborted(self, engagement: Engagement):
        engagement.abort(reason="cancelled")
        assert engagement.status == EngagementStatus.ABORTED

    def test_abort_publishes_event(self, engagement: Engagement):
        engagement.abort(reason="time")
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], EngagementAborted)
        assert events[0].reason == "time"

    def test_pause_requires_active(self, engagement: Engagement):
        with pytest.raises(ValueError, match="Cannot pause"):
            engagement.pause()

    def test_pause_transitions_to_paused(self, engagement: Engagement):
        engagement.start()
        engagement.pause()
        assert engagement.status == EngagementStatus.PAUSED

    def test_pause_publishes_event(self, engagement: Engagement):
        engagement.start()
        engagement.pop_events()  # clear start event
        engagement.pause()
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], EngagementStatusChanged)
        assert events[0].old_status == "active"
        assert events[0].new_status == "paused"

    def test_resume_requires_paused(self, engagement: Engagement):
        with pytest.raises(ValueError, match="Cannot resume"):
            engagement.resume()

    def test_resume_transitions_to_active(self, engagement: Engagement):
        engagement.start()
        engagement.pause()
        engagement.resume()
        assert engagement.status == EngagementStatus.ACTIVE

    def test_resume_publishes_event(self, engagement: Engagement):
        engagement.start()
        engagement.pause()
        engagement.pop_events()
        engagement.resume()
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], EngagementStatusChanged)
        assert events[0].new_status == "active"


# ── Phase transitions ───────────────────────────────────────────────────────


class TestPhaseTransition:
    def test_transition_phase(self, engagement: Engagement):
        engagement.transition_phase("design")
        assert engagement.current_phase == "design"

    def test_transition_publishes_event_when_phase_was_set(self, engagement: Engagement):
        engagement.current_phase = "design"
        engagement.pop_events()
        engagement.transition_phase("build")
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], PhaseTransitioned)
        assert events[0].from_phase == "design"
        assert events[0].to_phase == "build"

    def test_first_transition_no_event(self, engagement: Engagement):
        engagement.transition_phase("design")
        events = engagement.pop_events()
        # No from_phase -> no PhaseTransitioned
        assert len(events) == 0

    def test_wave_commit(self, engagement: Engagement):
        engagement.commit_wave("w1", "Initial")
        events = engagement.pop_events()
        assert len(events) == 1
        assert isinstance(events[0], WaveCommitted)
        assert events[0].wave_id == "w1"
        assert events[0].wave_name == "Initial"


# ── Health warnings ─────────────────────────────────────────────────────────


class TestHealthWarnings:
    def test_add_warning(self, engagement: Engagement):
        engagement.add_warning("high_error_rate", "Too many API errors")
        assert len(engagement.warnings) == 1
        assert engagement.warnings[0].type == "high_error_rate"

    def test_clear_warnings(self, engagement: Engagement):
        engagement.add_warning("w1", "msg")
        engagement.add_warning("w2", "msg")
        engagement.clear_warnings()
        assert len(engagement.warnings) == 0

    def test_health_warning_timestamp(self):
        hw = HealthWarning(type="test", message="msg")
        assert isinstance(hw.timestamp, datetime)

    def test_multiple_warnings(self, engagement: Engagement):
        engagement.add_warning("a", "first")
        engagement.add_warning("b", "second")
        assert len(engagement.warnings) == 2


# ── Event bus management ────────────────────────────────────────────────────


class TestEventBus:
    def test_event_bus_property(self, engagement: Engagement):
        """Can get and set the event bus."""
        from harness.domain.events.event_bus import EventBus
        assert isinstance(engagement.event_bus, EventBus)

        new_bus = EventBus()
        engagement.event_bus = new_bus
        assert engagement.event_bus is new_bus

    def test_pop_events_returns_and_clears(self, engagement: Engagement):
        engagement.add_warning("w", "m")  # this doesn't create events
        engagement.start()
        events = engagement.pop_events()
        assert len(events) == 1
        assert len(engagement._events) == 0

    def test_pop_events_empty(self, engagement: Engagement):
        events = engagement.pop_events()
        assert len(events) == 0


# ── String representation ───────────────────────────────────────────────────


class TestStringRepr:
    def test_str(self, engagement: Engagement):
        s = str(engagement)
        assert "Engagement" in s
        assert "test-eng" in s
        assert "created" in s
