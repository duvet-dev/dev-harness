"""End-to-end integration tests for dev-harness.

These tests require real external dependencies (LLM APIs, live services,
Temporal server, etc.) and are marked with @pytest.mark.e2e.

They are excluded from default `pytest` runs. Run them explicitly with:

    pytest tests_e2e                    # all e2e tests
    pytest -m e2e                       # tests marked e2e anywhere
    pytest -m ''                        # ALL tests including e2e

CI runs `pytest tests` only (unit + functional tests).
CD/post-deployment runs `pytest -m e2e` for full integration validation.
"""
