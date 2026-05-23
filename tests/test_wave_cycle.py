"""Tests for harness.wave.wave_cycle."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from harness.wave.wave_cycle import (
    WaveCycleConfig,
    WaveCycleResult,
    WaveCycleRunner,
    run_wave_via_cycle,
)


class TestWaveCycleConfig:
    def test_defaults(self):
        config = WaveCycleConfig()
        assert config.max_fix_iterations == 3
        assert config.auto_test is True
        assert config.test_timeout_seconds == 120
        assert config.agent_timeout_seconds == 120
        assert config.run_boundary_first is True

    def test_defaults_classmethod(self):
        config = WaveCycleConfig.defaults()
        assert config.max_fix_iterations == 3

    def test_custom_values(self):
        config = WaveCycleConfig(
            backend_name="deepseek",
            max_fix_iterations=5,
            auto_test=False,
            test_command="poetry run pytest",
        )
        assert config.backend_name == "deepseek"
        assert config.max_fix_iterations == 5
        assert config.test_command == "poetry run pytest"

    def test_boundary_test_command_default(self):
        config = WaveCycleConfig()
        assert "pytest" in config.boundary_test_command
        assert "test_refactor_boundaries" in config.boundary_test_command


class TestWaveCycleResult:
    def test_defaults(self):
        result = WaveCycleResult()
        assert result.success is False
        assert result.iterations == 0
        assert result.errors == []
        assert result.coder_artifacts == []

    def test_with_values(self):
        result = WaveCycleResult(
            wave_id="wave-01",
            title="Add auth",
            success=True,
            iterations=2,
            errors=[],
            committed=True,
        )
        assert result.wave_id == "wave-01"
        assert result.success is True
        assert result.committed is True


class TestWaveCycleRunner:
    @pytest.fixture
    def mock_plan_manager(self):
        with patch("harness.wave.wave_cycle.PlanManager") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_agent_runner(self):
        with patch("harness.wave.wave_cycle.AgentRunner") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_init(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        assert runner._root == tmp_path
        assert runner._slug == "test-engagement"

    def test_init_with_config(self, tmp_path):
        config = WaveCycleConfig(max_fix_iterations=5)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)
        assert runner._config.max_fix_iterations == 5

    @pytest.mark.asyncio
    async def test_run_wave_not_found(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        with patch.object(runner._plan_manager, "load", return_value=MagicMock(
            get_wave=MagicMock(return_value=None),
        )):
            result = await runner.run_wave("wave-01")
            assert result.success is False
            assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_run_wave_success_first_try(self, tmp_path):
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test wave")
        real_plan = RealPlan(waves=[real_wave])

        runner = WaveCycleRunner(tmp_path, "test-engagement")

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "save"),
            patch.object(runner._plan_manager, "sync_to_md"),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
            patch.object(runner, "_run_boundary_tests", new_callable=AsyncMock) as mock_boundary,
            patch.object(runner, "_run_test_suite", new_callable=AsyncMock) as mock_test,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={"file.py": "content"}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_boundary.return_value = {"exit_code": 0, "summary": "All passed"}
            mock_test.return_value = {"exit_code": 0, "summary": "3 passed in 0.1s"}

            result = await runner.run_wave("wave-01")
            assert result.success is True
            assert result.committed is True

    @pytest.mark.asyncio
    async def test_run_wave_coder_fails(self, tmp_path):
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        runner = WaveCycleRunner(tmp_path, "test-engagement")

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
        ):
            mock_coder.return_value = MagicMock(
                status="failure", artifacts={}, errors=["Coder error"]
            )

            result = await runner.run_wave("wave-01")
            assert result.success is False
            assert "Coder error" in result.errors

    @pytest.mark.asyncio
    async def test_run_wave_tester_fails(self, tmp_path):
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        runner = WaveCycleRunner(tmp_path, "test-engagement")

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(
                status="failure", artifacts={}, errors=["Tester error"]
            )

            result = await runner.run_wave("wave-01")
            assert result.success is False
            assert "Tester error" in result.errors

    @pytest.mark.asyncio
    async def test_run_wave_retries_on_failure(self, tmp_path):
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        config = WaveCycleConfig(max_fix_iterations=3, run_boundary_first=False)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)

        # First test run fails, second succeeds
        call_count = {"count": 0}

        async def test_side_effect():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return {"exit_code": 1, "summary": "2 failed"}
            return {"exit_code": 0, "summary": "5 passed"}

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner._plan_manager, "commit_wave"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
            patch.object(runner, "_run_test_suite", new_callable=AsyncMock) as mock_test,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_test.side_effect = test_side_effect

            result = await runner.run_wave("wave-01")
            assert result.success is True
            assert result.iterations == 2
            assert len(result.errors) == 1  # one failure recorded

    @pytest.mark.asyncio
    async def test_run_wave_exhausts_iterations(self, tmp_path):
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        config = WaveCycleConfig(max_fix_iterations=2, run_boundary_first=False)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
            patch.object(runner, "_run_test_suite", new_callable=AsyncMock) as mock_test,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_test.return_value = {"exit_code": 1, "summary": "Tests failing"}

            result = await runner.run_wave("wave-01")
            assert result.success is False
            assert result.iterations == 2
            assert "Max iterations" in result.errors[-1]

    @pytest.mark.asyncio
    async def test_run_wave_no_auto_test(self, tmp_path):
        """When auto_test=False, the wave should succeed without running tests."""
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        config = WaveCycleConfig(auto_test=False)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner._plan_manager, "commit_wave"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])

            result = await runner.run_wave("wave-01")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_run_wave_with_boundary_tests(self, tmp_path):
        """Boundary tests run before full suite."""
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        config = WaveCycleConfig(run_boundary_first=True, auto_test=True)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)

        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])
        # Mock only the plan_manager persistence, not the plan logic
        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "save"),
            patch.object(runner._plan_manager, "sync_to_md"),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
            patch.object(runner, "_run_boundary_tests", new_callable=AsyncMock) as mock_boundary,
            patch.object(runner, "_run_test_suite", new_callable=AsyncMock) as mock_test,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_boundary.return_value = {"exit_code": 0, "summary": "All boundary tests passed"}
            mock_test.return_value = {"exit_code": 0, "summary": "All tests passed"}

            result = await runner.run_wave("wave-01")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_boundary_tests_fail_but_still_retries(self, tmp_path):
        """Boundary test failure should trigger retry, not immediate failure."""
        from harness.plan.wave_model import Plan as RealPlan
        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = RealPlan(waves=[real_wave])

        config = WaveCycleConfig(max_fix_iterations=3, run_boundary_first=True)
        runner = WaveCycleRunner(tmp_path, "test-engagement", config=config)

        call_count = {"count": 0}

        async def boundary_side_effect():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return {"exit_code": 1, "summary": "Boundary failures"}
            return {"exit_code": 0, "summary": "All passed"}

        from harness.plan.wave_model import Wave as RealWave
        real_wave = RealWave(id="wave-01", title="Test")
        real_plan = MagicMock()
        real_plan.get_wave.return_value = real_wave

        with (
            patch.object(runner._plan_manager, "load", return_value=real_plan),
            patch.object(runner._plan_manager, "set_wave_state"),
            patch.object(runner._plan_manager, "commit_wave"),
            patch.object(runner, "_run_coder", new_callable=AsyncMock) as mock_coder,
            patch.object(runner, "_run_tester", new_callable=AsyncMock) as mock_tester,
            patch.object(runner, "_run_boundary_tests", new_callable=AsyncMock) as mock_boundary,
            patch.object(runner, "_run_test_suite", new_callable=AsyncMock) as mock_test,
        ):
            mock_coder.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_tester.return_value = MagicMock(status="success", artifacts={}, errors=[])
            mock_boundary.side_effect = boundary_side_effect
            mock_test.return_value = {"exit_code": 0, "summary": "All passed"}

            result = await runner.run_wave("wave-01")
            assert result.success is True
            assert result.iterations >= 2

    def test_extract_summary_line(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        summary = runner._extract_summary_line(
            "1 passed in 0.1s\n", "", 0
        )
        assert "passed" in summary

        summary2 = runner._extract_summary_line(
            "stdout text\n", "stderr with Error: failure", 1
        )
        assert "Error" in summary2

        summary3 = runner._extract_summary_line("", "", 1)
        assert "Exit code 1" in summary3

    @pytest.mark.asyncio
    async def test_run_boundary_tests_timeout(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                side_effect=asyncio.TimeoutError
            )
            mock_subprocess.return_value = mock_proc

            result = await runner._run_boundary_tests()
            assert result["completed"] is False
            assert "timed out" in result["summary"]

    def test_run_all_planned_with_no_waves(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        plan = MagicMock()
        plan.waves = []
        with patch.object(runner._plan_manager, "load", return_value=plan):
            results = asyncio.run(runner.run_all_planned())
            assert results == []

    def test_run_all_planned_skips_committed(self, tmp_path):
        runner = WaveCycleRunner(tmp_path, "test-engagement")
        committed_wave = MagicMock()
        committed_wave.is_committed.return_value = True
        committed_wave.id = "wave-01"
        plan = MagicMock()
        plan.waves = [committed_wave]

        with patch.object(runner._plan_manager, "load", return_value=plan):
            results = asyncio.run(runner.run_all_planned())
            assert results == []


class TestRunWaveViaCycle:
    @pytest.mark.asyncio
    async def test_runs_via_cycle_runner(self, tmp_path):
        from harness.agents.cycle import CycleResult

        mock_cycle_result = MagicMock(spec=CycleResult)
        mock_cycle_result.success = True

        with (
            patch("harness.wave.wave_cycle.PlanManager") as mock_pm_cls,
            patch("harness.wave.wave_cycle.CycleRunner") as mock_cr_cls,
        ):
            mock_pm = MagicMock()
            mock_pm_cls.return_value = mock_pm
            mock_pm.load.return_value.get_wave.return_value = MagicMock(title="Test")

            mock_cr_instance = MagicMock()
            mock_cr_instance.run = AsyncMock(return_value=mock_cycle_result)
            mock_cr_cls.return_value = mock_cr_instance

            result = await run_wave_via_cycle(tmp_path, "test-eng", "wave-01")
            assert mock_cr_instance.run.called
