"""Tests for WebSearchProvider protocol and implementations
(skills/builtin/web_search.py).

V7 §5.22 (W2) — WebSearchProvider ABC, DuckDuckGoProvider,
SearXNGProvider, data types.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from harness.errors import WebSearchUnavailableError
from harness.skills.builtin.web_search import (
    DuckDuckGoProvider,
    SearXNGProvider,
    SearchResultItem,
    WebSearchProvider,
    WebSearchResult,
    _clean_text,
    _parse_html_results,
)


# ── Data Types ─────────────────────────────────────────────────────────────


class TestSearchResultItem:
    """Tests for the SearchResultItem dataclass."""

    def test_minimal_creation(self) -> None:
        item = SearchResultItem(title="Test", url="https://example.com")
        assert item.title == "Test"
        assert item.url == "https://example.com"
        assert item.snippet == ""

    def test_full_creation(self) -> None:
        item = SearchResultItem(
            title="Test",
            url="https://example.com",
            snippet="A test result",
        )
        assert item.title == "Test"
        assert item.snippet == "A test result"

    def test_repr(self) -> None:
        item = SearchResultItem(title="T", url="https://x.com")
        assert "SearchResultItem" in repr(item)


class TestWebSearchResult:
    """Tests for the WebSearchResult dataclass."""

    def test_minimal_creation(self) -> None:
        result = WebSearchResult(query="test query")
        assert result.query == "test query"
        assert result.results == []
        assert isinstance(result.timestamp, datetime)

    def test_with_results(self) -> None:
        items = [SearchResultItem(title="A", url="https://a.com")]
        result = WebSearchResult(
            query="q", results=items, timestamp=datetime(2026, 1, 1)
        )
        assert len(result.results) == 1
        assert result.results[0].title == "A"
        assert result.timestamp.year == 2026


# ── Provider Protocol ──────────────────────────────────────────────────────


class TestWebSearchProvider:
    """Tests for the WebSearchProvider ABC."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            WebSearchProvider()  # type: ignore[abstract]

    def test_name_property(self) -> None:
        class TestProvider(WebSearchProvider):
            async def search(self, query, max_results=5):
                return WebSearchResult(query=query)

        provider = TestProvider()
        assert provider.name == "TestProvider"


# ── DuckDuckGo HTML Parser ────────────────────────────────────────────────


class TestHtmlParser:
    """Tests for _parse_html_results (DuckDuckGo Lite HTML parser)."""

    SAMPLE_HTML = (
        '<html><body>'
        '<div class="results">'
        '<tr class="result-snippet">'
        '<td><a href="https://example.com/1"><b>Result One</b></a></td>'
        '<td class="snippet">First snippet</td>'
        '</tr>'
        '<tr class="result-snippet">'
        '<td><a href="https://example.com/2"><b>Result Two</b></a></td>'
        '<td class="snippet">Second snippet</td>'
        '</tr>'
        '</div></body></html>'
    )

    def test_parses_all_results(self) -> None:
        results = _parse_html_results(self.SAMPLE_HTML)
        assert len(results) == 2

    def test_parses_titles(self) -> None:
        results = _parse_html_results(self.SAMPLE_HTML)
        assert results[0].title == "Result One"
        assert results[1].title == "Result Two"

    def test_parses_urls(self) -> None:
        results = _parse_html_results(self.SAMPLE_HTML)
        assert results[0].url == "https://example.com/1"
        assert results[1].url == "https://example.com/2"

    def test_parses_snippets(self) -> None:
        results = _parse_html_results(self.SAMPLE_HTML)
        assert results[0].snippet == "First snippet"
        assert results[1].snippet == "Second snippet"

    def test_empty_html(self) -> None:
        results = _parse_html_results("<html></html>")
        assert results == []

    def test_no_results(self) -> None:
        results = _parse_html_results(
            '<html><body><div>No results here</div></body></html>'
        )
        assert results == []

    def test_malformed_row(self) -> None:
        """Malformed rows without links or titles should be skipped."""
        html = (
            '<tr class="result-snippet">'
            '<td>No link here</td>'
            '</tr>'
        )
        results = _parse_html_results(html)
        assert results == []


class TestCleanText:
    """Tests for _clean_text utility."""

    def test_normalises_whitespace(self) -> None:
        assert _clean_text("  hello   world  ") == "hello world"

    def test_strips_whitespace(self) -> None:
        assert _clean_text("  \t\n  test  ") == "test"

    def test_empty_string(self) -> None:
        assert _clean_text("") == ""

    def test_no_change_for_clean_text(self) -> None:
        assert _clean_text("hello world") == "hello world"


# ── DuckDuckGoProvider (unit tests) ──────────────────────────────────────


class TestDuckDuckGoProvider:
    """Unit tests for DuckDuckGoProvider.

    These tests validate the provider's configuration and structure
    without making actual HTTP calls. Integration tests (hitting the
    live endpoint) are marked as e2e.
    """

    def test_default_initialization(self) -> None:
        provider = DuckDuckGoProvider()
        assert provider.name == "DuckDuckGoProvider"

    def test_custom_timeout(self) -> None:
        provider = DuckDuckGoProvider(timeout_seconds=30)
        assert provider._timeout == 30

    def test_is_web_search_provider(self) -> None:
        provider = DuckDuckGoProvider()
        assert isinstance(provider, WebSearchProvider)

    def test_name_property(self) -> None:
        provider = DuckDuckGoProvider()
        assert provider.name == "DuckDuckGoProvider"


# ── SearXNGProvider (unit tests) ──────────────────────────────────────────


class TestSearXNGProvider:
    """Unit tests for SearXNGProvider.

    These tests validate the provider's configuration without making
    actual HTTP calls. Integration tests are marked as e2e.
    """

    def test_default_initialization(self) -> None:
        provider = SearXNGProvider()
        assert provider.name == "SearXNGProvider"
        assert "localhost:8888" in provider._base_url

    def test_custom_url(self) -> None:
        provider = SearXNGProvider(
            base_url="https://search.example.com"
        )
        assert "search.example.com" in provider._base_url

    def test_custom_timeout(self) -> None:
        provider = SearXNGProvider(timeout_seconds=30)
        assert provider._timeout == 30

    def test_url_trailing_slash_stripped(self) -> None:
        provider = SearXNGProvider(
            base_url="http://localhost:8888/"
        )
        assert provider._search_url == "http://localhost:8888/search"

    def test_is_web_search_provider(self) -> None:
        provider = SearXNGProvider()
        assert isinstance(provider, WebSearchProvider)

    def test_name_property(self) -> None:
        provider = SearXNGProvider()
        assert provider.name == "SearXNGProvider"

    @pytest.mark.asyncio
    async def test_abstract_search_method_body(self) -> None:
        """Cover the abstract method body (line 100).

        Uses a concrete subclass that delegates to the ABC's
        ``...`` (Ellipsis) body of WebSearchProvider.search.
        """

        class _SearchBodyProvider(WebSearchProvider):
            """Concrete subclass calling ABC's search body."""
            async def search(self, query, max_results=5):  # type: ignore[override]
                return await WebSearchProvider.search(self, query, max_results)

        provider = _SearchBodyProvider()
        result = await provider.search("test query")
        assert result is None


# ── DuckDuckGo HTTP Error Handling ─────────────────────────────────────────


class TestDuckDuckGoErrorHandling:
    """Tests for DuckDuckGoProvider HTTP error paths."""

    @pytest.mark.asyncio
    async def test_http_error_raises_web_search_unavailable(self) -> None:
        """Covers httpx.HTTPError handler (lines 164-165)."""
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPError(
            "connection failed"
        )

        with patch(
            "httpx.AsyncClient",
            return_value=mock_client,
        ):
            provider = DuckDuckGoProvider()
            with pytest.raises(
                WebSearchUnavailableError, match="DuckDuckGo search failed"
            ):
                await provider.search("test query")


# ── SearXNG Error Handling + Success Paths ─────────────────────────────────


class TestSearXNGErrorHandling:
    """Tests for SearXNGProvider error and success paths."""

    @pytest.mark.asyncio
    async def test_http_error_raises_web_search_unavailable(self) -> None:
        """Covers httpx.HTTPError handler (line 298)."""
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPError(
            "connection refused"
        )

        with patch(
            "httpx.AsyncClient",
            return_value=mock_client,
        ):
            provider = SearXNGProvider()
            with pytest.raises(
                WebSearchUnavailableError,
                match="SearXNG search failed",
            ):
                await provider.search("test query")

    @pytest.mark.asyncio
    async def test_json_decode_error_raises_web_search_unavailable(
        self,
    ) -> None:
        """Covers JSON decode error handler (lines 304-307)."""
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_client.get.return_value = mock_response

        with patch(
            "httpx.AsyncClient",
            return_value=mock_client,
        ):
            provider = SearXNGProvider()
            with pytest.raises(
                WebSearchUnavailableError, match="invalid JSON"
            ):
                await provider.search("test query")

    @pytest.mark.asyncio
    async def test_successful_search_with_results(self) -> None:
        """Covers success path with result parsing (lines 298, 309-319)."""
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com/1",
                    "content": "Test content",
                },
            ]
        }
        mock_client.get.return_value = mock_response

        with patch(
            "httpx.AsyncClient",
            return_value=mock_client,
        ):
            provider = SearXNGProvider()
            result = await provider.search("test query")
            assert len(result.results) == 1
            assert result.results[0].title == "Test Title"
            assert result.results[0].url == "https://example.com/1"
            assert result.results[0].snippet == "Test content"
            assert result.query == "test query"

    @pytest.mark.asyncio
    async def test_successful_search_empty_results(self) -> None:
        """Covers success path with no results."""
        import httpx
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client

        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": []}
        mock_client.get.return_value = mock_response

        with patch(
            "httpx.AsyncClient",
            return_value=mock_client,
        ):
            provider = SearXNGProvider()
            result = await provider.search("test query")
            assert len(result.results) == 0


# ── E2E Tests (manual run only) ────────────────────────────────────────────

