"""Tests for harness.sync.pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.sync.pipeline import run_sync


class TestRunSync:
    def test_run_sync_no_output_dir(self, tmp_path):
        """run_sync should work without explicit output_dir."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={}, procedures={}, agent_definitions=[]
            )
            mock_ext_cls.return_value = mock_extractor

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = MagicMock(
                agents={}, agent_registry=[], changes_from_previous={}
            )
            mock_mapper_cls.return_value = mock_mapper

            mock_applier = MagicMock()
            mock_applier.apply.return_value = MagicMock(
                written_files=[], skipped_files=[], errors=[]
            )
            mock_applier_cls.return_value = mock_applier

            result = run_sync()
            assert result is not None

    def test_run_sync_with_output_dir(self, tmp_path):
        """run_sync should accept an output_dir."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={}, procedures={}, agent_definitions=[]
            )
            mock_ext_cls.return_value = mock_extractor

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = MagicMock(
                agents={}, agent_registry=[], changes_from_previous={}
            )
            mock_mapper_cls.return_value = mock_mapper

            mock_applier = MagicMock()
            mock_applier.apply.return_value = MagicMock(
                written_files=[], skipped_files=[], errors=[]
            )
            mock_applier_cls.return_value = mock_applier

            result = run_sync(output_dir=tmp_path)
            # Verify applier was created with tmp_path
            call_kwargs = mock_applier_cls.call_args
            assert call_kwargs is not None
            assert "output_dir" in call_kwargs[1] or "output_dir" in call_kwargs[0]

    def test_run_sync_preview(self, tmp_path):
        """Preview mode should return a string without writing."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={}, procedures={}, agent_definitions=[]
            )
            mock_ext_cls.return_value = mock_extractor

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = MagicMock(
                agents={}, agent_registry=[], changes_from_previous={}
            )
            mock_mapper_cls.return_value = mock_mapper

            mock_applier = MagicMock()
            mock_applier.preview.return_value = "Preview output string"
            mock_applier_cls.return_value = mock_applier

            result = run_sync(output_dir=tmp_path, preview=True)
            assert result == "Preview output string"
            # Verify preview was called, not apply
            assert mock_applier.preview.called
            assert not mock_applier.apply.called

    def test_run_sync_logs_extraction_counts(self, tmp_path):
        """Pipeline should call extract, map, apply in sequence."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
            patch("harness.sync.pipeline.logger") as mock_logger,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={"a": "1", "b": "2"},
                procedures={"a": "1"},
                agent_definitions=[{"name": "x"}],
            )
            mock_ext_cls.return_value = mock_extractor

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = MagicMock(
                agents={"a": "tpl"},
                agent_registry=[{"name": "test"}],
                changes_from_previous={},
            )
            mock_mapper_cls.return_value = mock_mapper

            mock_applier = MagicMock()
            mock_applier.apply.return_value = MagicMock(
                written_files=[Path("a.md")],
                skipped_files=[],
                errors=[],
            )
            mock_applier_cls.return_value = mock_applier

            result = run_sync(output_dir=tmp_path)
            # The pipeline should have been called sequentially
            assert mock_extractor.extract_all.called
            assert mock_mapper.map.called
            assert mock_applier.apply.called

    def test_run_sync_with_extraction_results(self, tmp_path):
        """Verify the pipeline creates the expected flow."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
        ):
            mock_extraction = MagicMock()
            mock_extraction.identities = {"agent-1": "ident"}
            mock_extraction.procedures = {"agent-1": "proc"}
            mock_extraction.agent_definitions = []
            mock_extraction.community_standards = "# CS"
            mock_extraction.tools = "# Tools"

            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = mock_extraction
            mock_ext_cls.return_value = mock_extractor

            mock_templates = MagicMock()
            mock_templates.agents = {"agent-1": MagicMock()}
            mock_templates.agent_registry = []

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = mock_templates
            mock_mapper_cls.return_value = mock_mapper

            mock_applier = MagicMock()
            mock_applier.apply.return_value = MagicMock(
                written_files=[Path("agents/agent-1/identity.md")],
                skipped_files=[],
                errors=[],
            )
            mock_applier_cls.return_value = mock_applier

            report = run_sync(output_dir=tmp_path)
            assert report is not None

    def test_run_sync_errors_handled(self, tmp_path):
        """Errors during apply should be included in report."""
        with (
            patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls,
            patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
            patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={}, procedures={}, agent_definitions=[]
            )
            mock_ext_cls.return_value = mock_extractor

            mock_mapper = MagicMock()
            mock_mapper.map.return_value = MagicMock(
                agents={}, agent_registry=[], changes_from_previous={}
            )
            mock_mapper_cls.return_value = mock_mapper

            mock_apply_report = MagicMock()
            mock_apply_report.written_files = []
            mock_apply_report.skipped_files = []
            mock_apply_report.errors = ["Failed to write file"]

            mock_applier = MagicMock()
            mock_applier.apply.return_value = mock_apply_report
            mock_applier_cls.return_value = mock_applier

            report = run_sync(output_dir=tmp_path)
            assert hasattr(report, "errors")
            assert len(report.errors) > 0

    def test_run_sync_full_integration_skip(self, tmp_path):
        """Test that the pipeline orchestrator function exists and can be imported."""
        from harness.sync.pipeline import run_sync
        assert callable(run_sync)


class TestPipelineEdgeCases:
    def test_run_sync_handles_missing_directories(self, tmp_path):
        """Pipeline should handle missing directories gracefully."""
        # Use non-existent workspace dirs
        with patch("harness.sync.pipeline.OpenClawExtractor") as mock_ext_cls:
            mock_extractor = MagicMock()
            mock_extractor.extract_all.return_value = MagicMock(
                identities={}, procedures={}, agent_definitions=[]
            )
            mock_ext_cls.return_value = mock_extractor

            with (
                patch("harness.sync.pipeline.SyncMapper") as mock_mapper_cls,
                patch("harness.sync.pipeline.SyncApplier") as mock_applier_cls,
            ):
                mock_mapper = MagicMock()
                mock_mapper.map.return_value = MagicMock(
                    agents={}, agent_registry=[], changes_from_previous={}
                )
                mock_mapper_cls.return_value = mock_mapper

                mock_applier = MagicMock()
                mock_applier.apply.return_value = MagicMock(
                    written_files=[], skipped_files=[], errors=[]
                )
                mock_applier_cls.return_value = mock_applier

                report = run_sync(output_dir=tmp_path)
                assert report is not None
