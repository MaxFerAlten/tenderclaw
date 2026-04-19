"""Web Fetch tool — fetch and extract content from URLs.

Fetch HTML from arbitrary URLs, parse with BeautifulSoup, and extract:
- Raw HTML
- Text content (stripped)
- Main content (via article/main selector)
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from backend.schemas.tools import RiskLevel, ToolResult
from backend.tools.base import BaseTool, ToolContext

logger = logging.getLogger("tenderclaw.tools.web_fetch")

FETCH_TIMEOUT = 30
MAX_TEXT_LENGTH = 50000


class WebFetchTool(BaseTool):
    """Fetch a URL and extract its content."""

    name = "WebFetch"
    description = (
        "Fetch a URL and extract its content. Supports extracting raw HTML, "
        "text content, or main content (article body). Returns up to 50000 chars."
    )
    risk_level = RiskLevel.MEDIUM
    is_read_only = True
    concurrency_safe = True

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
                "extract": {
                    "type": "string",
                    "description": "What to extract: 'html' (raw), 'text' (cleaned), 'main' (article body)",
                    "enum": ["html", "text", "main"],
                    "default": "text",
                },
            },
            "required": ["url"],
        }

    async def execute(self, tool_input: dict[str, Any], context: ToolContext) -> ToolResult:
        url = tool_input.get("url", "")
        extract = tool_input.get("extract", "text")

        if not url.strip():
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content="Error: empty URL",
                is_error=True,
            )

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content="Error: URL must start with http:// or https://",
                is_error=True,
            )

        try:
            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")

            if extract == "html":
                content = html[:MAX_TEXT_LENGTH]
                output = f"<HTML length={len(html)} chars>\n\n{content}"
            elif extract == "main":
                content = _extract_main_content(soup)
                output = f"<MAIN CONTENT length={len(content)} chars>\n\n{content}"
            else:  # text
                # Remove script and style elements
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                text = re.sub(r"\n{3,}", "\n\n", text)
                content = text[:MAX_TEXT_LENGTH]
                output = f"<TEXT length={len(text)} chars>\n\n{content}"

            return ToolResult(tool_use_id=context.tool_use_id, content=output)

        except httpx.TimeoutException:
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content=f"Error: timeout fetching {url}",
                is_error=True,
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content=f"Error: HTTP {e.response.status_code} for {url}",
                is_error=True,
            )
        except Exception as exc:
            logger.error("Web fetch error: %s", exc)
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content=f"Error fetching {url}: {exc}",
                is_error=True,
            )


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Extract the main content from a page."""
    # Try common article/main selectors
    for selector in ["article", "main", "[role=main]", ".main-content", ".content", "#content"]:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator="\n", strip=True)
            if len(text) > 100:  # Reasonable content length
                return re.sub(r"\n{3,}", "\n\n", text)

    # Fallback: find the largest text block
    candidates = []
    for tag in soup.find_all(["div", "section"]):
        text = tag.get_text(separator="\n", strip=True)
        if len(text) > 200:
            candidates.append((len(text), text))

    if candidates:
        candidates.sort(reverse=True)
        return re.sub(r"\n{3,}", "\n\n", candidates[0][1])

    # Ultimate fallback: body
    body = soup.body
    if body:
        return body.get_text(separator="\n", strip=True)

    return soup.get_text(separator="\n", strip=True)
