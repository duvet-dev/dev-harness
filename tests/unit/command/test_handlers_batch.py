"""Tests for Wave H handlers: batch creation + lower priority (6 handlers).

These handlers are delegation-thin — they delegate to real business components.
Pattern tests verify importability, registration, and handler interface compliance.
"""
from __future__ import annotations

import pytest

from harness.command.legacy_handlers import (
    AnnotateChangelogHandler,
    CreateWaveFromFindingHandler,
    CreateWavesFromAssessmentHandler,
    GenerateDocsHandler,
    ListWavesHandler,
    WaveStatusHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import CommandHandler

smoke = pytest.mark.smoke


class TestListWavesHandler:
    """Tests for ListWavesHandler — pattern verification."""

    def test_importable(self):
        handler = ListWavesHandler()
        assert isinstance(handler, ListWavesHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_list_waves_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "list_waves" in registry.list_registered()


class TestWaveStatusHandler:
    """Tests for WaveStatusHandler — pattern verification."""

    def test_importable(self):
        handler = WaveStatusHandler()
        assert isinstance(handler, WaveStatusHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_wave_status_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "wave_status" in registry.list_registered()


class TestCreateWaveFromFindingHandler:
    """Tests for CreateWaveFromFindingHandler — pattern verification."""

    def test_importable(self):
        handler = CreateWaveFromFindingHandler()
        assert isinstance(handler, CreateWaveFromFindingHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_create_wave_from_finding_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "create_wave_from_finding" in registry.list_registered()


class TestCreateWavesFromAssessmentHandler:
    """Tests for CreateWavesFromAssessmentHandler — pattern verification."""

    def test_importable(self):
        handler = CreateWavesFromAssessmentHandler()
        assert isinstance(handler, CreateWavesFromAssessmentHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_create_waves_from_assessment_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "create_waves_from_assessment" in registry.list_registered()


class TestGenerateDocsHandler:
    """Tests for GenerateDocsHandler — pattern verification."""

    def test_importable(self):
        handler = GenerateDocsHandler()
        assert isinstance(handler, GenerateDocsHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_generate_docs_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "generate_docs" in registry.list_registered()


class TestAnnotateChangelogHandler:
    """Tests for AnnotateChangelogHandler — pattern verification."""

    def test_importable(self):
        handler = AnnotateChangelogHandler()
        assert isinstance(handler, AnnotateChangelogHandler)
        assert isinstance(handler, CommandHandler)

    @smoke
    def test_annotate_changelog_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "annotate_changelog" in registry.list_registered()
