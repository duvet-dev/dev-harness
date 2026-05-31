"""Tests for domain/events/engagement_events.py."""

from __future__ import annotations

from datetime import datetime, timezone

from harness.domain.events.engagement_events import (
    EngagementCreated,
    EngagementStarted,
    EngagementStatusChanged,
    EngagementCompleted,
    EngagementAborted,
    PhaseTransitioned,
    WaveCommitted,
)
from harness.domain.events.event_bus import Event


class TestEngagementCreated:
    def test_fields(self):
        e = EngagementCreated(slug="test-eng", session_type="greenfield")
        assert isinstance(e, Event)
        assert e.slug == "test-eng"
        assert e.session_type == "greenfield"
        assert isinstance(e.created_at, datetime)

    def test_default_timestamp_is_utc(self):
        e = EngagementCreated(slug="s", session_type="t")
        assert e.created_at.tzinfo is timezone.utc


class TestEngagementStarted:
    def test_fields(self):
        e = EngagementStarted(slug="test-eng")
        assert e.slug == "test-eng"
        assert isinstance(e.started_at, datetime)


class TestEngagementStatusChanged:
    def test_fields(self):
        e = EngagementStatusChanged(slug="eng", old_status="a", new_status="b")
        assert e.old_status == "a"
        assert e.new_status == "b"

    def test_default_timestamp(self):
        e = EngagementStatusChanged(slug="eng", old_status="x", new_status="y")
        assert isinstance(e.changed_at, datetime)


class TestEngagementCompleted:
    def test_fields(self):
        e = EngagementCompleted(slug="eng")
        assert isinstance(e, Event)
        assert e.slug == "eng"


class TestEngagementAborted:
    def test_fields(self):
        e = EngagementAborted(slug="eng", reason="scope changed")
        assert e.reason == "scope changed"

    def test_default_reason_empty(self):
        e = EngagementAborted(slug="eng")
        assert e.reason == ""


class TestPhaseTransitioned:
    def test_fields(self):
        e = PhaseTransitioned(slug="eng", from_phase="design", to_phase="build")
        assert e.from_phase == "design"
        assert e.to_phase == "build"


class TestWaveCommitted:
    def test_fields(self):
        e = WaveCommitted(slug="eng", wave_id="w1", wave_name="Initial Setup")
        assert e.wave_id == "w1"
        assert e.wave_name == "Initial Setup"
