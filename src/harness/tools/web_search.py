"""Web search tool for harness agents.

Provides duckduckgo-based web search via the lightweight HTML endpoint,
plus page-content fetching for deeper reading. No API key required.

Uses ``httpx`` for HTTP requests and Python's ``html.parser``
for lightweight HTML-to-text extraction (no external scraping deps).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResult:
    """A single search result from the web."""

    title: str
    url: str
    snippet: str
    rank: int


# User-agent string to avoid being blocked
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# DuckDuckGo Lite endpoint — returns simple HTML tables
_DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"

# Maximum content bytes to fetch from a single page
_MAX_CONTENT_BYTES = 50_000


class WebSearchTool:
    """Agent tool for searching the web and fetching page content.

    This tool provides two capabilities:

    1. **Search** — submit a query to DuckDuckGo Lite and get ranked
       results with titles, URLs, and snippets.
    2. **Fetch** — retrieve readable text content from a URL.

    No API keys are required. The tool is safe for agent use because
    it only reads (no write operations).
    """

    def __init__(
        self,
        max_results: int = 5,
        max_content_bytes: int = _MAX_CONTENT_BYTES,
    ):
        self._max_results = max_results
        self._max_content_bytes = max_content_bytes

    # ------------------------------------------------------------------
    # Agent-framework integration
    # ------------------------------------------------------------------

    @property
    def tool_name(self) -> str:
        """Canonical name used in tool registration and dispatch."""
        return "web_search"

    def tool_spec(self) -> dict[str, Any]:
        """Return a provider-agnostic tool specification for LLM APIs."""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web for information. You can either "
                    "submit a search query or fetch the content of a "
                    "specific URL. Results include titles, URLs, "
                    "and snippets."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The search query to submit. "
                                "Optional if fetch_url is provided."
                            ),
                        },
                        "fetch_url": {
                            "type": "string",
                            "description": (
                                "A URL to fetch and extract readable "
                                "content from. Optional if query is "
                                "provided."
                            ),
                        },
                        "max_results": {
                            "type": "integer",
                            "description": (
                                "Maximum number of search results "
                                "to return (1-10, default 5)."
                            ),
                        },
                    },
                    "required": [],
                },
            },
        }

    @staticmethod
    def to_openai_tools(tool_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert internal tool spec to OpenAI tools format."""
        return [tool_spec]

    @staticmethod
    def system_prompt_preamble(tool_name: str = "web_search") -> str:
        """Return a system-prompt preamble for non-function-calling APIs."""
        return (
            "\n\n--- Web Search Tool ---\n"
            f"You have access to a web search tool called `{tool_name}`. "
            "You can search the web for information or fetch the content "
            "of a specific URL. "
            "To invoke it, produce a JSON block with this format:\n"
            "\n"
            "```tool\n"
            '{"query": "python type hints best practices"}\n'
            "```\n"
            "\n"
            "```tool\n"
            '{"fetch_url": "https://example.com/article.html"}\n'
            "```\n"
            "\n"
            "```tool\n"
            '{"query": "fastapi dependencies", "max_results": 3}\n'
            "```\n"
            "\n"
            "Use this tool when you need external reference information, "
            "library documentation, best practices, or to verify facts "
            "against current sources.\n"
            "--- End Web Search Tool ---\n\n"
        )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[SearchResult]:
        """Search the web via DuckDuckGo Lite and return ranked results.

        Args:
            query: The search query string.
            max_results: Maximum results to return (defaults to
                ``self._max_results``).

        Returns:
            A list of :class:`SearchResult` objects.
        """
        import httpx

        limit = min(
            max_results or self._max_results,
            10,
        )

        params = {"q": query.strip()}

        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            response = client.get(
                _DDG_LITE_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()

        results = _parse_ddg_lite_results(response.text)
        return results[:limit]

    def fetch_content(self, url: str) -> str:
        """Fetch a URL and extract readable text content.

        Args:
            url: The URL to fetch.

        Returns:
            Extracted text content, truncated to
            ``self._max_content_bytes``.
        """
        import httpx

        with httpx.Client(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
        ) as client:
            response = client.get(
                url,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()

        text = response.text[: self._max_content_bytes]
        return _extract_readable_text(text)

    def execute(
        self,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool invocation from the LLM.

        Handles both search and fetch-content operations based on
        the arguments provided.

        Args:
            args: Tool arguments from the LLM. May contain ``query``
                and/or ``fetch_url``.

        Returns:
            A dict with tool results, suitable for returning to the LLM.
        """
        results: list[SearchResult] = []
        fetched_content: str | None = None

        query = args.get("query", "").strip()
        fetch_url = args.get("fetch_url", "").strip()
        max_results = args.get("max_results")

        # Fetch content from a URL
        if fetch_url:
            try:
                fetched_content = self.fetch_content(fetch_url)
            except Exception as exc:
                return {
                    "error": f"Failed to fetch URL '{fetch_url}': {exc}",
                    "type": type(exc).__name__,
                }

        # Search the web
        if query:
            try:
                results = self.search(query, max_results)
            except Exception as exc:
                return {
                    "error": f"Search failed: {exc}",
                    "type": type(exc).__name__,
                }

        # Build the response
        output_parts: list[str] = []

        if results:
            output_parts.append(f"Search results for '{query}':\n")
            for r in results:
                output_parts.append(f"{r.rank}. {r.title}")
                output_parts.append(f"   URL: {r.url}")
                output_parts.append(f"   {r.snippet}\n")

        if fetched_content:
            output_parts.append(
                f"\nContent from {fetch_url}:\n"
            )
            output_parts.append(fetched_content)

        if not output_parts:
            return {
                "info": (
                    "No results. Try a different query or provide "
                    "a fetch_url."
                )
            }

        return {"results": "\n".join(output_parts)}


# ------------------------------------------------------------------
# DuckDuckGo Lite HTML parser
# ------------------------------------------------------------------


def _parse_ddg_lite_results(html_text: str) -> list[SearchResult]:
    """Parse DuckDuckGo Lite HTML response into structured results.

    The Lite endpoint returns results in a table structure with
    ``result-snippet`` class rows. This parser extracts whatever
    it can find and gracefully handles missing fields.
    """
    import re

    results: list[SearchResult] = []

    # Find all result-snippet rows. Each row has the form:
    # <tr class="result-snippet">
    #   <td>
    #     <a href="URL"><b>TITLE</b></a>
    #   </td>
    #   <td class="snippet">SNIPPET</td>
    # </tr>
    #
    # We extract these with simple regex because the DDG lite
    # format is stable and this avoids full HTML parser complexity.

    snippet_rows = re.split(r'<tr[^>]*class="result-snippet"[^>]*>', html_text)
    # First chunk is before the first result; skip it
    for row_html in snippet_rows[1:]:
        # Close at </tr>
        row_end = row_html.find("</tr>")
        if row_end != -1:
            row_html = row_html[:row_end]

        # Extract URL
        url_match = re.search(r'<a\s+href="([^"]+)"', row_html)
        url = ""
        if url_match:
            url = html.unescape(url_match.group(1))

        # Extract title (between <b> and </b>)
        title_match = re.search(r'<b>([^<]*)</b>', row_html)
        title = ""
        if title_match:
            title = _clean_text(html.unescape(title_match.group(1)))

        # Extract snippet (text after class="snippet" or in the second td)
        snippet_match = re.search(r'class="snippet"[^>]*>([^<]*)<', row_html)
        snippet = ""
        if snippet_match:
            snippet = _clean_text(html.unescape(snippet_match.group(1)))

        if url and title:
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                rank=len(results) + 1,
            ))

    return results


def _clean_text(raw: str) -> str:
    """Clean whitespace and decode HTML entities."""
    text = html.unescape(raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_readable_text(html_text: str) -> str:
    """Extract readable text from HTML, stripping scripts and styles.

    Uses Python's ``html.parser`` to extract all visible text content
    from an HTML page. Strips script/style tags, whitespace-normalises,
    and deduplicates blank lines.
    """
    from html.parser import HTMLParser

    output: list[str] = []
    skip_tags = {"script", "style", "noscript", "header", "footer", "nav"}
    skip_depth = 0

    class TextExtractor(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            nonlocal skip_depth
            if tag in skip_tags:
                skip_depth += 1

        def handle_endtag(self, tag: str) -> None:
            nonlocal skip_depth
            if tag in skip_tags:
                skip_depth = max(0, skip_depth - 1)
            if tag in ("p", "br", "h1", "h2", "h3", "h4", "li", "div"):
                output.append("\n")

        def handle_data(self, data: str) -> None:
            if skip_depth == 0:
                text = _clean_text(data)
                if text:
                    output.append(text + " ")

    parser = TextExtractor()
    parser.feed(html_text)
    parser.close()

    raw = "".join(output)
    # Collapse repeated newlines
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()
