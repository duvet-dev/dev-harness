"""End-to-end tests for web search providers.

These tests require network access and are placed in tests/e2e/ to be
excluded from the default CI test run. Run with: make test-e2e
"""
from __future__ import annotations

import pytest

from harness.skills.builtin.web_search import (
    DuckDuckGoProvider,
    SearXNGProvider,
    WebSearchUnavailableError,
)


class TestDuckDuckGoE2E:
    """End-to-end tests against the live DuckDuckGo endpoint."""

    @pytest.mark.asyncio
    async def test_live_search(self) -> None:
        provider = DuckDuckGoProvider()
        result = await provider.search("python type hints", max_results=3)
        assert result.query == "python type hints"
        for item in result.results:
            assert item.title
            assert item.url


class TestSearXNGProviderE2E:
    """End-to-end tests against a SearXNG instance."""

    @pytest.mark.asyncio
    async def test_live_search_fails_when_unavailable(self) -> None:
        provider = SearXNGProvider(base_url="http://localhost:19999")
        with pytest.raises(WebSearchUnavailableError):
            await provider.search("test query")
