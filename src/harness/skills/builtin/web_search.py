"""WebSearchProvider protocol — V7 §5.22 (W2).

Defines the abstract WebSearchProvider protocol and two concrete
implementations: DuckDuckGoProvider (default, no API key) and
SearXNGProvider (alternative, self-hosted).

All providers are local-only (W2 resolution): no external API keys
are required. Tavily, Brave, and other paid provider references have
been removed from this design.

Design principles (W2):
- Default: DuckDuckGo via curl (no configuration needed)
- Alternative: Self-hosted SearXNG (configurable URL)
- Protocol: WebSearchProvider ABC — swap implementation without
  changing the skill
"""

from __future__ import annotations

import json
import subprocess
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from harness.errors import WebSearchUnavailableError


# ── Data Types ─────────────────────────────────────────────────────────


@dataclass
class SearchResultItem:
    """A single search result item.

    Attributes:
        title: The result title.
        url: The result URL.
        snippet: A short text snippet describing the result.
    """

    title: str
    url: str
    snippet: str = ""


@dataclass
class WebSearchResult:
    """The response from a web search provider.

    Attributes:
        query: The original search query.
        results: List of SearchResultItem objects.
        timestamp: When the search was performed.
    """

    query: str
    results: list[SearchResultItem] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


# ── Provider Protocol ──────────────────────────────────────────────────


class WebSearchProvider(ABC):
    """Abstract base class for web search providers.

    All providers must implement the ``search`` method. Providers
    should raise :class:`WebSearchUnavailableError` when the search
    backend is unreachable.

    Usage::

        provider = DuckDuckGoProvider()
        result = await provider.search("python asyncio patterns")
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> WebSearchResult:
        """Execute a web search.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return
                (default 5).

        Returns:
            A WebSearchResult containing the search results.

        Raises:
            WebSearchUnavailableError: If the search backend is
                unreachable or returns an error.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return self.__class__.__name__


# ── DuckDuckGo Provider (Default) ──────────────────────────────────────


class DuckDuckGoProvider(WebSearchProvider):
    """Default web search provider using DuckDuckGo's HTML endpoint.

    Uses curl to query the DuckDuckGo Lite endpoint and parses the
    simple HTML table response. No API key is required.

    This is the default provider: zero configuration needed.
    """

    _DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout_seconds: int = 15) -> None:
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> WebSearchResult:
        """Search the web via DuckDuckGo Lite endpoint.

        Args:
            query: The search query.
            max_results: Maximum results to return (1-10, default 5).

        Returns:
            WebSearchResult with parsed results.

        Raises:
            WebSearchUnavailableError: If the DuckDuckGo endpoint is
                unreachable.
        """
        import httpx

        limit = min(max(max_results, 1), 10)
        params = {"q": query.strip()}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout)
            ) as client:
                response = await client.get(
                    self._DDG_LITE_URL,
                    params=params,
                    headers={"User-Agent": self._USER_AGENT},
                    follow_redirects=True,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WebSearchUnavailableError(
                f"DuckDuckGo search failed: {exc}"
            ) from exc

        results = _parse_html_results(response.text)
        return WebSearchResult(
            query=query,
            results=results[:limit],
            timestamp=datetime.now(),
        )


def _parse_html_results(html_text: str) -> list[SearchResultItem]:
    """Parse DuckDuckGo Lite HTML response into result items.

    The Lite endpoint returns results in a simple table structure.
    This parser extracts whatever it can find and gracefully handles
    missing fields.
    """
    import html
    import re

    results: list[SearchResultItem] = []

    # Split by result-snippet rows
    snippet_rows = re.split(
        r'<tr[^>]*class="result-snippet"[^>]*>', html_text
    )
    # First chunk is before the first result; skip it
    for row_html in snippet_rows[1:]:
        row_end = row_html.find("</tr>")
        if row_end != -1:
            row_html = row_html[:row_end]

        # Extract URL
        url_match = re.search(r'<a\s+href="([^"]+)"', row_html)
        url = html.unescape(url_match.group(1)) if url_match else ""

        # Extract title
        title_match = re.search(r'<b>([^<]*)</b>', row_html)
        title = ""
        if title_match:
            title = html.unescape(title_match.group(1))

        # Extract snippet
        snippet_match = re.search(
            r'class="snippet"[^>]*>([^<]*)<', row_html
        )
        snippet = ""
        if snippet_match:
            snippet = html.unescape(snippet_match.group(1))

        if url and title:
            results.append(
                SearchResultItem(
                    title=_clean_text(title),
                    url=url,
                    snippet=_clean_text(snippet),
                )
            )

    return results


def _clean_text(raw: str) -> str:
    """Normalise whitespace in text."""
    import re
    return re.sub(r"\s+", " ", raw).strip()


# ── SearXNG Provider (Alternative) ────────────────────────────────────


class SearXNGProvider(WebSearchProvider):
    """Alternative web search provider for self-hosted SearXNG instances.

    Requires a SearXNG instance URL. SearXNG is a privacy-respecting
    metasearch engine that can be self-hosted.

    The provider uses SearXNG's JSON API endpoint.

    Args:
        base_url: Base URL of the SearXNG instance
            (e.g. ``http://localhost:8888``).
        timeout_seconds: HTTP request timeout (default 15).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8888",
        timeout_seconds: int = 15,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._search_url = f"{self._base_url}/search"
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> WebSearchResult:
        """Search via SearXNG JSON API.

        Args:
            query: The search query.
            max_results: Maximum results to return (default 5).

        Returns:
            WebSearchResult with parsed results.

        Raises:
            WebSearchUnavailableError: If the SearXNG instance is
                unreachable.
        """
        import httpx

        limit = min(max(max_results, 1), 50)

        params: dict[str, Any] = {
            "q": query.strip(),
            "format": "json",
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout)
            ) as client:
                response = await client.get(
                    self._search_url,
                    params=params,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise WebSearchUnavailableError(
                f"SearXNG search failed at {self._search_url}: {exc}"
            ) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise WebSearchUnavailableError(
                f"SearXNG returned invalid JSON: {exc}"
            ) from exc

        results: list[SearchResultItem] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResultItem(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )

        return WebSearchResult(
            query=query,
            results=results,
            timestamp=datetime.now(),
        )


# ── Provider factory (V7 §7, Wave 8b) ──────────────────────────────────


def create_web_search_provider(
    provider_name: str = "duckduckgo",
    searxng_url: str = "http://localhost:8888",
    timeout_seconds: int = 15,
) -> WebSearchProvider:
    """Create a web search provider from configuration.

    Factory function that returns the appropriate provider based on
    the configured provider name. Designed to be called from settings
    loaded from ``.harness/settings.yaml``.

    Args:
        provider_name: "duckduckgo" (default) or "searxng".
        searxng_url: Base URL for SearXNG instance (only used when
            provider_name is "searxng").
        timeout_seconds: HTTP request timeout in seconds.

    Returns:
        A configured WebSearchProvider instance.

    Raises:
        ValueError: If provider_name is not "duckduckgo" or "searxng".

    Usage::

        # From settings.yaml:
        from harness.skills.builtin.web_search import create_web_search_provider

        provider = create_web_search_provider(
            provider_name="duckduckgo",
        )
        result = await provider.search("python type hints")
    """
    if provider_name == "duckduckgo":
        return DuckDuckGoProvider(timeout_seconds=timeout_seconds)
    elif provider_name == "searxng":
        return SearXNGProvider(
            base_url=searxng_url,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise ValueError(
            f"Unknown web search provider: '{provider_name}'. "
            f"Expected 'duckduckgo' or 'searxng'."
        )
